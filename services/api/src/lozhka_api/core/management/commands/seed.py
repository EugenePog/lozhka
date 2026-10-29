"""python manage.py seed [--set essential] [--set demo]

essential = what the shop needs to start (VAT, allergens, categories, settings, delivery templates, zones...).
demo      = products, stock, prices, customers and sample orders so every screen has something to show.
"""
from django.core.management.base import BaseCommand, CommandError

from lozhka_api.core.seeding import load_sets


class Command(BaseCommand):
    help = "Load seed files (natural keys, idempotent)."

    def add_arguments(self, parser):
        parser.add_argument("--set", action="append", choices=["essential", "demo"], dest="sets",
                            help="seed set to load (repeatable). Default: essential")

    def handle(self, *args, **opts):
        sets = opts["sets"] or ["essential"]
        if "demo" in sets and "essential" not in sets:
            sets.insert(0, "essential")
        try:
            report = load_sets(sets)
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        for line in report.lines:
            self.stdout.write(line)
        self.stdout.write(self.style.SUCCESS(
            f"done: {report.created} created, {report.updated} updated, {report.unchanged} unchanged"))
