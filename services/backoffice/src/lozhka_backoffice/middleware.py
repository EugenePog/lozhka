"""Every staff page needs a login. Pages that are not login/static redirect to /login/ when anonymous."""
from django.conf import settings
from django.shortcuts import redirect

ADMIN_CAPABILITIES = ("edit_catalogue", "edit_content", "edit_suppliers", "edit_delivery_rules", "manage_staff")
OPEN_PREFIXES = ("/login/", "/static/", "/health")


class StaffAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        if not request.user.is_authenticated and not path.startswith(OPEN_PREFIXES):
            return redirect(f"{settings.LOGIN_URL}?next={path}")
        # customers share the user table but never get in here
        if request.user.is_authenticated and not request.user.is_staff and not path.startswith(OPEN_PREFIXES):
            from django.contrib.auth import logout

            logout(request)
            return redirect(settings.LOGIN_URL)
        if path.startswith("/admin/") and request.user.is_authenticated and not any(
                request.user.has_perm(f"core.{c}") for c in ADMIN_CAPABILITIES):
            from django.shortcuts import render

            return render(request, "backoffice/not_allowed.html", status=403)
        return self.get_response(request)
