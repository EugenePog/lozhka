
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.db import transaction
from django.http import Http404
from django.middleware.csrf import get_token
from ninja import Router
from ninja.errors import HttpError
from ninja.throttling import AnonRateThrottle

from lozhka_api.catalog.models import Product
from lozhka_api.customers.models import ConsentLog, Customer, CustomerAddress, Favourite
from lozhka_api.sales.models import Order

from ..deps import customer_auth, customer_of, fetch_all, lang_of, merge_guest_cart, public_auth
from ..schemas import AddressIn, AddressOut, LoginIn, MeIn, MeOut, ProductCard, RegisterIn

router = Router(tags=["account"], auth=public_auth)
member = Router(tags=["account"], auth=customer_auth)
User = get_user_model()


def me_out(c: Customer) -> dict:
    return {"email": c.email, "first_name": c.first_name, "last_name": c.last_name, "phone": c.phone, "language": c.language}


@router.get("/auth/csrf", response=dict, summary="Sets the CSRF cookie; call once when the app loads")
def csrf(request):
    return {"csrf": get_token(request)}


@router.get("/auth/me", response=MeOut, summary="Signed-in customer or 401")
def me(request):
    c = customer_of(request)
    if c is None:
        raise HttpError(401, "not_signed_in")
    return me_out(c)


@router.post("/auth/register", response={201: MeOut}, throttle=[AnonRateThrottle("20/h")], summary="Create an account")
@transaction.atomic
def register(request, body: RegisterIn):
    email = body.email.strip().lower()
    if "@" not in email or len(body.password) < 8:
        raise HttpError(422, "invalid_email_or_short_password")
    if Customer.objects.filter(is_guest=False, email__iexact=email).exists():
        raise HttpError(409, "email_taken")
    user = User(username=f"customer:{email}", email=email)
    user.set_password(body.password)
    user.save()
    customer = Customer.objects.create(email=email, first_name=body.first_name, last_name=body.last_name,
                                       phone=body.phone, language=lang_of(body.language), auth_user=user)
    # earlier guest orders with this e-mail address belong to the new account
    Order.objects.filter(customer__is_guest=True, contact_email__iexact=email).update(customer=customer)
    ConsentLog.objects.create(customer=customer, kind="terms", version="1", granted=True)
    if body.marketing_opt_in:
        ConsentLog.objects.create(customer=customer, kind="marketing", version="1", granted=True)
    old_cart = request.session.get("cart")
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    if old_cart:
        request.session["cart"] = old_cart
    merge_guest_cart(request, customer)
    return 201, me_out(customer)


@router.post("/auth/login", response=MeOut, throttle=[AnonRateThrottle("30/h")], summary="Sign in")
def do_login(request, body: LoginIn):
    email = body.email.strip().lower()
    user = authenticate(request, username=f"customer:{email}", password=body.password)
    if user is None:
        raise HttpError(401, "bad_credentials")
    customer = Customer.objects.filter(auth_user=user).first()
    if customer is None:
        raise HttpError(401, "bad_credentials")
    old_cart = request.session.get("cart")
    login(request, user)
    if old_cart:
        request.session["cart"] = old_cart
    merge_guest_cart(request, customer)
    return me_out(customer)


@router.post("/auth/logout", response={204: None}, summary="Sign out")
def do_logout(request):
    logout(request)
    return 204, None


@router.post("/auth/google", response={501: dict}, summary="STUB")
def google(request):
    return 501, {"code": "not_implemented", "detail": "Google sign-in arrives with the OAuth module"}


@router.post("/auth/apple", response={501: dict}, summary="STUB")
def apple(request):
    return 501, {"code": "not_implemented", "detail": "Apple sign-in arrives with the OAuth module"}


@member.patch("/me", response=MeOut, summary="Update my details")
def update_me(request, body: MeIn):
    c = customer_of(request)
    c.first_name, c.last_name, c.phone, c.language = body.first_name, body.last_name, body.phone, lang_of(body.language)
    c.save(update_fields=["first_name", "last_name", "phone", "language"])
    return me_out(c)


def address_out(a: CustomerAddress) -> dict:
    return {"id": a.id, "label": a.label, "first_name": a.first_name, "last_name": a.last_name, "street": a.street,
            "house_number": a.house_number, "addition": a.addition, "postcode": a.postcode, "city": a.city,
            "delivery_notes": a.delivery_notes, "is_default": a.is_default}


@member.get("/me/addresses", response=list[AddressOut], summary="My addresses")
def addresses(request):
    return [address_out(a) for a in customer_of(request).addresses.order_by("-is_default", "id")]


@member.post("/me/addresses", response={201: AddressOut}, summary="Add an address")
@transaction.atomic
def add_address(request, body: AddressIn):
    c = customer_of(request)
    if body.is_default or not c.addresses.exists():
        c.addresses.update(is_default=False)
    a = CustomerAddress.objects.create(customer=c, **{**body.dict(), "is_default": body.is_default or not c.addresses.exists()})
    return 201, address_out(a)


@member.put("/me/addresses/{address_id}", response=AddressOut, summary="Change an address")
@transaction.atomic
def edit_address(request, address_id: int, body: AddressIn):
    c = customer_of(request)
    a = c.addresses.filter(pk=address_id).first()
    if a is None:
        raise Http404()
    if body.is_default:
        c.addresses.exclude(pk=a.pk).update(is_default=False)
    for k, v in body.dict().items():
        setattr(a, k, v)
    a.save()
    return address_out(a)


@member.delete("/me/addresses/{address_id}", response={204: None}, summary="Delete an address")
def delete_address(request, address_id: int):
    customer_of(request).addresses.filter(pk=address_id).delete()
    return 204, None


@member.get("/me/favourites", response=list[str], summary="SKUs of my favourites")
def favourites(request):
    return list(Favourite.objects.filter(customer=customer_of(request)).values_list("product__sku", flat=True))


@member.get("/me/favourites/products", response=list[ProductCard], summary="My favourites as product cards")
def favourite_products(request, lang: str = "nl"):
    from .catalog import CARD_COLS, card

    skus = list(Favourite.objects.filter(customer=customer_of(request)).values_list("product__sku", flat=True))
    if not skus:
        return []
    rows = fetch_all(f"select {CARD_COLS} from gold.storefront_product where lang = %s and sku = any(%s) order by name",
                     [lang_of(lang), skus])
    return [card(r) | {"is_favourite": True} for r in rows]


@member.put("/me/favourites/{sku}", response={204: None}, summary="Add a favourite")
def add_favourite(request, sku: str):
    product = Product.objects.filter(sku=sku).first()
    if product is None:
        raise Http404()
    Favourite.objects.get_or_create(customer=customer_of(request), product=product)
    return 204, None


@member.delete("/me/favourites/{sku}", response={204: None}, summary="Remove a favourite")
def remove_favourite(request, sku: str):
    Favourite.objects.filter(customer=customer_of(request), product__sku=sku).delete()
    return 204, None
