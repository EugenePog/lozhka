"""Public API (customer web and later the apps). Mounted at /api/v1/ by config.urls_public."""
from django.http import JsonResponse
from ninja import NinjaAPI
from ninja.errors import HttpError

from .routers import account, cart, catalog, delivery, orders

api = NinjaAPI(
    title="Lozhka public API", version="1", urls_namespace="public",
    description="Catalogue, cart, delivery slots, checkout and customer account. Money is integer cents.",
)

for r in (catalog.router, cart.router, delivery.router, orders.router, orders.member, account.router, account.member):
    api.add_router("", r)


@api.exception_handler(HttpError)
def http_error(request, exc: HttpError):
    return JsonResponse({"code": str(exc.message), "detail": "", "extra": {}}, status=exc.status_code)


@api.get("/health", auth=None, include_in_schema=False)
def health(request):
    return {"ok": True}
