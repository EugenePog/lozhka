"""Seed loader. Reads db/seeds/manifest.toml and loads CSV files by NATURAL keys (never by numeric id).

Every file is an upsert: rows are found by the natural key columns and created or updated, so loading twice
changes nothing and a changed file updates the rows. Foreign keys are written in the CSV as the parent's natural
key (e.g. `category` = slug, `product` = sku) and resolved here. Composite parent keys use `a|b`.

Value conventions in the CSVs:
  empty cell                -> NULL for nullable fields, '' for text fields
  true / false              -> boolean
  JSON columns              -> JSON text, e.g. ["1000-1299"]
  +30d / -2d  (date fields) -> relative to today (demo stock must not expire the day after it is loaded)
  +2h / -1d   (datetime)    -> relative to now
"""
from __future__ import annotations

import csv
import json
import re
import tomllib
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import Any

from django.apps import apps
from django.db import connection, models, transaction
from django.utils import timezone

REL = re.compile(r"^([+-])(\d+)([dh])$")


@dataclass
class Report:
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    lines: list[str] = field(default_factory=list)


def seeds_dir() -> Path:
    from django.conf import settings

    return Path(settings.SEEDS_DIR)


def _convert(model, name: str, raw: str) -> Any:
    f = model._meta.get_field(name)
    raw = raw.strip() if isinstance(f, (models.IntegerField, models.DecimalField, models.BooleanField, models.DateField, models.TimeField)) else raw
    if raw == "":
        if f.null:
            return None
        if isinstance(f, (models.CharField, models.TextField)):
            return ""
        if f.has_default():
            return f.get_default()
        raise ValueError(f"{model.__name__}.{name}: empty value but field is required")
    if isinstance(f, models.JSONField):
        return json.loads(raw)
    if isinstance(f, models.BooleanField):
        return raw.lower() in ("1", "true", "yes", "y")
    m = REL.match(raw)
    if m and isinstance(f, (models.DateField,)):
        sign, n, unit = m.groups()
        delta = timedelta(days=int(n)) if unit == "d" else timedelta(hours=int(n))
        if isinstance(f, models.DateTimeField):
            moment = timezone.now() + (delta if sign == "+" else -delta)
            # whole days: midnight local time, so repeated loads do not rewrite the row
            return moment.astimezone(timezone.get_current_timezone()).replace(hour=8 if unit == "d" else moment.hour, minute=0, second=0, microsecond=0)
        return timezone.localdate() + (delta if sign == "+" else -delta)
    return f.to_python(raw)


def _resolve(spec: str, value: str):
    """spec 'app.Model:lookup' or 'app.Model:a__x|b'; value 'X' or 'X|Y'."""
    label, _, lookup = spec.partition(":")
    model = apps.get_model(label)
    fields_ = lookup.split("|")
    values = value.split("|")
    if len(fields_) != len(values):
        raise ValueError(f"{spec}: expected {len(fields_)} key part(s), got {value!r}")
    try:
        return model.objects.get(**dict(zip(fields_, values)))
    except model.DoesNotExist:
        raise ValueError(f"{label} with {lookup}={value!r} not found (load order or typo)") from None


def load_table(entry: dict, base: Path, report: Report) -> None:
    model = apps.get_model(entry["model"])
    path = base / entry["file"]
    fks: dict[str, str] = entry.get("fk", {})
    key: list[str] = entry["key"]
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    created = updated = unchanged = 0
    for n, row in enumerate(rows, start=2):
        try:
            values: dict[str, Any] = {}
            for col, raw in row.items():
                if col is None or col.startswith("#"):
                    continue
                if col in fks:
                    values[col] = _resolve(fks[col], raw) if raw.strip() else None
                else:
                    values[col] = _convert(model, col, raw)
            lookup = {k: values[k] for k in key}
            defaults = {k: v for k, v in values.items() if k not in key}
            obj = model.objects.filter(**lookup).first()
            if obj is None:
                model.objects.create(**lookup, **defaults)
                created += 1
            else:
                changed = [k for k, v in defaults.items() if getattr(obj, k) != v]
                if changed:
                    for k in changed:
                        setattr(obj, k, defaults[k])
                    obj.save()
                    updated += 1
                else:
                    unchanged += 1
        except Exception as exc:  # point at the file and line, then stop: a half-loaded set is rolled back
            raise ValueError(f"{entry['file']} line {n}: {exc}") from exc
    report.created += created
    report.updated += updated
    report.unchanged += unchanged
    report.lines.append(f"{entry['file']:<44} {created:>4} new {updated:>4} updated {unchanged:>4} same")


def load_sets(sets: list[str]) -> Report:
    base = seeds_dir()
    manifest = tomllib.loads((base / "manifest.toml").read_text(encoding="utf-8"))
    report = Report()
    with transaction.atomic():
        for name in sets:
            for step in manifest["set"][name]["step"]:
                if "hook" in step:
                    _HOOKS[step["hook"]](base, report)
                else:
                    load_table(step, base, report)
        _sync_order_sequence()
    return report


def _sync_order_sequence() -> None:
    """Seeded orders carry fixed numbers; keep the sequence ahead of them."""
    with connection.cursor() as cur:
        cur.execute(
            """select coalesce(max(substring(order_number from '[0-9]+$')::bigint), 0) from app."order" """
        )
        top = cur.fetchone()[0]
        cur.execute("select last_value, is_called from order_number_seq")
        last, called = cur.fetchone()
        if top >= (last if called else last - 1):
            cur.execute("select setval('order_number_seq', %s)", [top])


# ---- hooks: parts that are not plain tables ----------------------------------------------------------------------

def _hook_customer_accounts(base: Path, report: Report) -> None:
    """demo/customer_account.csv: email, password, first_name, last_name, phone, language. Natural key: email."""
    from django.contrib.auth import get_user_model

    from lozhka_api.customers.models import Customer

    User = get_user_model()
    path = base / "demo" / "customer_account.csv"
    n = 0
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            email = row["email"].strip().lower()
            user = User.objects.filter(username=f"customer:{email}").first()
            if user is None:
                user = User(username=f"customer:{email}", email=email, is_active=True, is_staff=False)
                user.set_password(row["password"])
                user.save()
            _upsert_customer(Customer, email, row, user)
            n += 1
    report.lines.append(f"{'demo/customer_account.csv':<44} {n:>4} accounts")


def _upsert_customer(Customer, email: str, row: dict, user) -> None:
    c = Customer.objects.filter(is_guest=False, email__iexact=email).first() or Customer(is_guest=False)
    c.email, c.first_name, c.last_name = email, row["first_name"], row["last_name"]
    c.phone, c.language, c.auth_user = row["phone"], row["language"] or "nl", user
    c.email_verified_at = c.email_verified_at or timezone.now()
    c.save()


def _hook_demo_orders(base: Path, report: Report) -> None:
    """demo/order.csv: order_number, customer, items (sku:qty;sku:qty), payment_method, template, day_offset, status.
    Orders are created through the real checkout service so every rule applies, then renamed to the seed number."""
    from lozhka_api.customers.models import Cart, Customer
    from lozhka_api.domain import checkout, orders
    from lozhka_api.sales.models import DeliveryTemplate, Order

    path = base / "demo" / "order.csv"
    made = 0
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if Order.objects.filter(order_number=row["order_number"]).exists():
                continue
            customer = Customer.objects.get(is_guest=False, email__iexact=row["customer"])
            cart, _ = Cart.objects.get_or_create(customer=customer)
            cart.lines.all().delete()
            for part in row["items"].split(";"):
                sku, qty = part.split(":")
                from lozhka_api.catalog.models import Product

                cart.lines.create(product=Product.objects.get(sku=sku), qty=qty)
            address = customer.addresses.filter(is_default=True).first() or customer.addresses.first()
            from lozhka_api.domain import deliveries

            offer = next((o for o in deliveries.offers() if o.occurrence.template.code == row["template"] and not o.is_full), None)
            if offer is None:
                continue
            offer_day = offer.occurrence.delivery_date
            order = checkout.place_order(checkout.CheckoutInput(
                cart=cart, customer=customer, email=customer.email, phone=customer.phone,
                first_name=address.first_name, last_name=address.last_name, street=address.street,
                house_number=address.house_number, addition=address.addition, postcode=address.postcode,
                city=address.city, notes=address.delivery_notes, delivery_choice="time_range",
                template_code=row["template"], delivery_date=offer_day, payment_method=row["payment_method"],
                language=customer.language, terms_accepted=True,
            ))
            order.order_number = row["order_number"]
            order.save(update_fields=["order_number"])
            if row["status"] == "paid":
                orders.mark_paid(order, actor="seed")
            made += 1
    report.lines.append(f"{'demo/order.csv':<44} {made:>4} orders placed")


def _hook_staff_roles(base: Path, report: Report) -> None:
    """essential/staff_role.csv: role, permission (capability codename on core.StaffCapability)."""
    from django.contrib.auth.models import Group, Permission

    wanted: dict[str, set[str]] = {}
    with (base / "essential" / "staff_role.csv").open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            wanted.setdefault(row["role"], set()).add(row["permission"])
    for role, codes in wanted.items():
        group, _ = Group.objects.get_or_create(name=role)
        perms = list(Permission.objects.filter(content_type__app_label="core", content_type__model="staffcapability", codename__in=codes))
        missing = codes - {p.codename for p in perms}
        if missing:
            raise ValueError(f"unknown capability permission(s) for role {role}: {sorted(missing)}")
        group.permissions.set(perms)
    report.lines.append(f"{'essential/staff_role.csv':<44} {len(wanted):>4} roles")


def _hook_staff_users(base: Path, report: Report) -> None:
    """demo/staff_user.csv: email, password, first_name, roles (a;b;c). Natural key: email (= username)."""
    from django.contrib.auth import get_user_model
    from django.contrib.auth.models import Group

    User = get_user_model()
    n = 0
    with (base / "demo" / "staff_user.csv").open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            email = row["email"].strip().lower()
            user = User.objects.filter(username=email).first()
            if user is None:
                user = User(username=email, email=email)
                user.set_password(row["password"])
            user.first_name, user.is_staff, user.is_active = row["first_name"], True, True
            user.save()
            user.groups.set(Group.objects.filter(name__in=[r for r in row["roles"].split(";") if r]))
            n += 1
    report.lines.append(f"{'demo/staff_user.csv':<44} {n:>4} staff accounts")


_HOOKS = {"staff_roles": _hook_staff_roles, "staff_users": _hook_staff_users, "customer_accounts": _hook_customer_accounts, "demo_orders": _hook_demo_orders}
