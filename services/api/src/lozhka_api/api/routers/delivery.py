from __future__ import annotations

from ninja import Router

from lozhka_api.domain import deliveries
from lozhka_api.domain.timeutil import AMS, hhmm, now
from lozhka_api.sales.models import DeliveryFeeTier

from ..deps import public_auth
from ..schemas import DeliveryOffersOut

router = Router(tags=["delivery"], auth=public_auth)


def slot_out(offer) -> dict:
    occ = offer.occurrence
    return {
        "template_code": occ.template.code, "name": occ.template.name, "delivery_date": occ.delivery_date,
        "deliver_from": hhmm(occ.template.deliver_from), "deliver_to": hhmm(occ.template.deliver_to),
        "deliver_starts_at": occ.deliver_starts_at, "order_by": occ.collect_ends_at,
        "orders_left": max(0, offer.capacity - offer.orders), "is_full": offer.is_full,
    }


@router.get("/delivery/offers", response=DeliveryOffersOut, summary="Zone check and delivery slots for a postcode")
def offers(request, postcode: str = ""):
    zone = deliveries.zone_for_postcode(postcode) if postcode else None
    at = now()
    all_offers = deliveries.offers(at)
    asap = deliveries.asap_offer(all_offers, at)
    tiers = []
    if zone:
        tiers = list(DeliveryFeeTier.objects.filter(zone=zone).values("min_subtotal_cents", "max_subtotal_cents", "fee_cents"))
    return {
        "postcode": deliveries.normalise_postcode(postcode), "in_zone": zone is not None,
        "zone": zone.name if zone else None, "fee_tiers": tiers,
        "asap": slot_out(asap) if asap and zone else None,
        "slots": [slot_out(o) for o in all_offers] if zone else [],
    }
