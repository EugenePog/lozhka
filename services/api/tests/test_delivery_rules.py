import pytest

pytestmark = pytest.mark.django_db

from datetime import date, time

from lozhka_api.domain import deliveries
from lozhka_api.sales.models import DeliveryTemplate


def test_seeded_templates_tile_the_day():
    active = [{"collect_from": t.collect_from, "collect_to": t.collect_to} for t in DeliveryTemplate.objects.filter(is_active=True)]
    assert deliveries.check_template_coverage(active) == 0


def test_gap_and_overlap_are_detected():
    ok = [{"collect_from": time(0), "collect_to": time(12)}, {"collect_from": time(12), "collect_to": time(0)}]
    assert deliveries.check_template_coverage(ok) == 0
    gap = [{"collect_from": time(0), "collect_to": time(11)}, {"collect_from": time(12), "collect_to": time(0)}]
    assert deliveries.check_template_coverage(gap) == 60
    overlap = [{"collect_from": time(0), "collect_to": time(13)}, {"collect_from": time(12), "collect_to": time(0)}]
    assert deliveries.check_template_coverage(overlap) == 60


def test_delivery_day_is_first_range_after_collection_ends():
    a = DeliveryTemplate.objects.get(code="A")   # collect 22:00-10:00, deliver 13:00-17:00
    occ = deliveries.occurrence_from_collection_day(a, date(2026, 11, 2))
    assert occ.delivery_date == date(2026, 11, 3)       # collection runs past midnight, delivery that afternoon
    b = DeliveryTemplate.objects.get(code="B")   # collect 10:00-16:00, deliver 17:00-21:00
    assert deliveries.occurrence_from_collection_day(b, date(2026, 11, 2)).delivery_date == date(2026, 11, 2)
    c = DeliveryTemplate.objects.get(code="C")   # collect 16:00-22:00, deliver 10:00-14:00 -> next morning
    assert deliveries.occurrence_from_collection_day(c, date(2026, 11, 2)).delivery_date == date(2026, 11, 3)


def test_exactly_one_template_is_collecting_at_any_moment():
    from lozhka_api.domain.timeutil import now

    offers = deliveries.offers()
    at = now()
    collecting = [o for o in offers if o.occurrence.collect_starts_at <= at < o.occurrence.collect_ends_at]
    assert len(collecting) == 1


def test_postcode_zone_matching():
    assert deliveries.zone_for_postcode("1053 EC").name.startswith("Amsterdam")
    assert deliveries.zone_for_postcode("3511AB").name == "Utrecht"
    assert deliveries.zone_for_postcode("9999ZZ") is None
