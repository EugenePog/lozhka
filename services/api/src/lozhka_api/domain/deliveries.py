"""Delivery templates, occurrences and lazily created deliveries (docs 02 s.4.4a).

An *occurrence* is a template on a date: the delivery range on its delivery date. The delivery date is derived,
never stored on the template: the first date on which the delivery range starts at or after the end of the
collection range. Collection ranges of active templates tile the 24 hours, so exactly one template is
collecting at any moment.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from django.db import connection, transaction
from django.db.models import Count, Q

from lozhka_api.sales.models import (
    CAPACITY_EXCLUDED,
    Delivery,
    DeliveryFeeTier,
    DeliveryTemplate,
    DeliveryZone,
)

from .settings_store import horizon_days
from .timeutil import combine, local_today, now, plus_days


@dataclass(frozen=True)
class Occurrence:
    template: DeliveryTemplate
    delivery_date: date
    collect_starts_at: datetime
    collect_ends_at: datetime
    deliver_starts_at: datetime
    deliver_ends_at: datetime

    @property
    def key(self) -> str:
        return f"{self.template.code}:{self.delivery_date.isoformat()}"


def occurrence_from_collection_day(template: DeliveryTemplate, collect_day: date) -> Occurrence:
    """The occurrence whose collection range STARTS on `collect_day` (local time)."""
    starts = combine(collect_day, template.collect_from)
    # an end that is not later than the start runs through midnight; equal start and end = the whole day
    end_day = collect_day if template.collect_to > template.collect_from else plus_days(collect_day, 1)
    ends = combine(end_day, template.collect_to)
    # delivery day: first date on which the delivery range starts at or after the end of collection
    d = ends.date()
    while combine(d, template.deliver_from) < ends:
        d = plus_days(d, 1)
    deliver_starts = combine(d, template.deliver_from)
    deliver_end_day = d if template.deliver_to > template.deliver_from else plus_days(d, 1)
    deliver_ends = combine(deliver_end_day, template.deliver_to)
    return Occurrence(template, d, starts, ends, deliver_starts, deliver_ends)


def occurrence_for_delivery_date(template: DeliveryTemplate, delivery_date: date) -> Occurrence | None:
    """Occurrence of a template for a given delivery date (searches the few collection days that can map to it)."""
    for offset in range(-3, 2):
        occ = occurrence_from_collection_day(template, plus_days(delivery_date, offset))
        if occ.delivery_date == delivery_date:
            return occ
    return None


def count_orders(delivery_ids: list[int]) -> dict[int, int]:
    """Orders that hold a place (including those awaiting payment or confirmation)."""
    from lozhka_api.sales.models import Order

    rows = (
        Order.objects.filter(delivery_id__in=delivery_ids)
        .exclude(status__in=CAPACITY_EXCLUDED)
        .values("delivery_id")
        .annotate(n=Count("id"))
    )
    return {r["delivery_id"]: r["n"] for r in rows}


@dataclass
class Offer:
    occurrence: Occurrence
    delivery: Delivery | None
    orders: int
    capacity: int

    @property
    def is_full(self) -> bool:
        return self.orders >= self.capacity

    @property
    def places_left(self) -> int:
        return max(0, self.capacity - self.orders)


def upcoming_occurrences(at: datetime | None = None) -> list[Occurrence]:
    """Active-template occurrences from today up to the horizon whose collection has not ended."""
    at = at or now()
    today = local_today(at)
    last = plus_days(today, horizon_days())
    found: dict[str, Occurrence] = {}
    for template in DeliveryTemplate.objects.filter(is_active=True):
        for offset in range(-2, horizon_days() + 3):
            occ = occurrence_from_collection_day(template, plus_days(today, offset))
            if occ.collect_ends_at > at and today <= occ.delivery_date <= last:
                found[occ.key] = occ
    return sorted(found.values(), key=lambda o: (o.deliver_starts_at, o.template.sort))


def offers(at: datetime | None = None) -> list[Offer]:
    """What a customer can choose, with fill level. Existing deliveries keep the values they were created with."""
    at = at or now()
    result: list[Offer] = []
    occs = upcoming_occurrences(at)
    existing = {
        (d.template_id, d.delivery_date): d
        for d in Delivery.objects.filter(delivery_date__in={o.delivery_date for o in occs}, template__isnull=False)
    }
    counts = count_orders([d.id for d in existing.values()])
    for occ in occs:
        delivery = existing.get((occ.template.id, occ.delivery_date))
        if delivery is not None:
            # a delivery that is already approved or further no longer accepts orders
            if delivery.status != "open":
                continue
            result.append(Offer(occ, delivery, counts.get(delivery.id, 0), delivery.capacity_orders))
        else:
            result.append(Offer(occ, None, 0, occ.template.capacity_orders))
    return result


def asap_offer(all_offers: list[Offer], at: datetime | None = None) -> Offer | None:
    """The occurrence being collected now; if it is full, the next one in time with room."""
    at = at or now()
    ordered = sorted(all_offers, key=lambda o: o.occurrence.deliver_starts_at)
    current = [o for o in ordered if o.occurrence.collect_starts_at <= at < o.occurrence.collect_ends_at]
    start_index = ordered.index(current[0]) if current else 0
    for offer in ordered[start_index:]:
        if not offer.is_full:
            return offer
    return None


def find_offer(all_offers: list[Offer], template_code: str, delivery_date: date) -> Offer | None:
    for offer in all_offers:
        if offer.occurrence.template.code == template_code and offer.occurrence.delivery_date == delivery_date:
            return offer
    return None


def _lock(template_id: int, delivery_date: date) -> None:
    with connection.cursor() as cur:
        cur.execute("select pg_advisory_xact_lock(hashtext(%s))", [f"delivery:{template_id}:{delivery_date}"])


def delivery_values(template: DeliveryTemplate, occ: Occurrence) -> dict:
    return {
        "delivery_number": f"D-{occ.delivery_date:%m%d}-{template.code}",
        "template_code": template.code,
        "template_name": template.name,
        "collect_from": template.collect_from,
        "collect_to": template.collect_to,
        "deliver_from": template.deliver_from,
        "deliver_to": template.deliver_to,
        "capacity_orders": template.capacity_orders,
        "cod_confirmation_hours": template.cod_confirmation_hours,
        "collect_starts_at": occ.collect_starts_at,
        "collect_ends_at": occ.collect_ends_at,
        "deliver_starts_at": occ.deliver_starts_at,
        "deliver_ends_at": occ.deliver_ends_at,
    }


@transaction.atomic
def get_or_create_delivery(template: DeliveryTemplate, delivery_date: date) -> tuple[Delivery, bool]:
    """Lazy creation: the first order for a template and date creates the delivery with copied template values.
    Takes a lock on template and date so two simultaneous orders create one delivery."""
    _lock(template.id, delivery_date)
    existing = Delivery.objects.filter(template=template, delivery_date=delivery_date).first()
    if existing:
        return existing, False
    occ = occurrence_for_delivery_date(template, delivery_date)
    if occ is None:
        raise ValueError(f"template {template.code} has no occurrence on {delivery_date}")
    return Delivery.objects.create(template=template, delivery_date=delivery_date, **delivery_values(template, occ)), True


def order_count(delivery: Delivery) -> int:
    return count_orders([delivery.id]).get(delivery.id, 0)


def release_if_empty(delivery: Delivery | None) -> bool:
    """A delivery that loses its last order is deleted (a periodic sweep catches leftovers)."""
    if delivery is None or delivery.status != "open":
        return False
    if delivery.orders.exclude(status__in=CAPACITY_EXCLUDED).exists():
        return False
    # cancelled orders keep pointing at the delivery for history until it is deleted: detach them first
    delivery.orders.update(delivery=None)
    delivery.delete()
    return True


def effective_status(delivery: Delivery, at: datetime | None = None) -> str:
    """'open' turns into 'closed' once the collection range has ended and nobody approved it yet."""
    at = at or now()
    if delivery.status == "open" and at >= delivery.collect_ends_at:
        return "closed"
    return delivery.status


def can_accept_orders(delivery: Delivery, at: datetime | None = None) -> bool:
    return effective_status(delivery, at) == "open"


# ---- zones and fees --------------------------------------------------------------------------------------------

def normalise_postcode(value: str) -> str:
    compact = "".join(ch for ch in (value or "") if ch.isalnum()).upper()
    return f"{compact[:4]} {compact[4:6]}" if len(compact) >= 6 else compact


def postcode4(value: str) -> int | None:
    digits = "".join(ch for ch in (value or "") if ch.isdigit())[:4]
    return int(digits) if len(digits) == 4 else None


def zone_for_postcode(postcode: str) -> DeliveryZone | None:
    number = postcode4(postcode)
    if number is None:
        return None
    for zone in DeliveryZone.objects.filter(is_active=True):
        for rng in zone.postcode4_ranges:
            low, _, high = str(rng).partition("-")
            if int(low) <= number <= int(high or low):
                return zone
    return None


def fee_for(zone: DeliveryZone, subtotal_cents: int) -> int:
    tier = (
        DeliveryFeeTier.objects.filter(zone=zone, min_subtotal_cents__lte=subtotal_cents)
        .filter(Q(max_subtotal_cents__isnull=True) | Q(max_subtotal_cents__gte=subtotal_cents))
        .order_by("-min_subtotal_cents")
        .first()
    )
    return tier.fee_cents if tier else 0


def check_template_coverage(templates: list[dict]) -> int:
    """Number of minutes of the day not covered exactly once by the given collection ranges
    (same arithmetic as the database constraint trigger). dicts have collect_from / collect_to (time)."""
    minutes = [0] * 1440
    for t in templates:
        start = t["collect_from"].hour * 60 + t["collect_from"].minute
        end = t["collect_to"].hour * 60 + t["collect_to"].minute
        length = 1440 if end == start else (end - start) % 1440
        for i in range(length):
            minutes[(start + i) % 1440] += 1
    return sum(1 for m in minutes if m != 1)


def time_from_str(value: str) -> time:
    hours, _, minutes = value.partition(":")
    return time(int(hours) % 24, int(minutes or 0))


def timedelta_hours(hours: int) -> timedelta:
    return timedelta(hours=hours)
