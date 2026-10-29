"""Read business rules from app.setting (docs 02 s.4.5). Defaults keep a fresh database usable."""
from __future__ import annotations

from typing import Any

from lozhka_api.core.models import Setting

DEFAULTS: dict[str, Any] = {
    "min_order_cents": 5000,
    "service_time_s": 180,
    "fuel_price_cents_per_l": 190,
    "driver_cost_cents_per_h": 2200,
    "reservation_ttl_min": 15,
    "cod_enabled": True,
    "delivery_horizon_days": 3,
    "staff_session_minutes": 60,
    "stock_cache_seconds": 60,
    "order_claim_minutes": 5,
    "cod_warn_minutes": 30,
}


def get_setting(key: str, default: Any = None) -> Any:
    value = Setting.objects.filter(key=key).values_list("value", flat=True).first()
    if value is None:
        return DEFAULTS.get(key, default) if default is None else default
    return value


def min_order_cents() -> int:
    return int(get_setting("min_order_cents"))


def horizon_days() -> int:
    return int(get_setting("delivery_horizon_days"))
