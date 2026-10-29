from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST
from django.utils.http import url_has_allowed_host_and_scheme

from ..permissions import landing_for


def login_view(request):
    if request.user.is_authenticated and request.user.is_staff:
        return redirect("home")
    error = ""
    nxt = request.POST.get("next") or request.GET.get("next") or ""
    if request.method == "POST":
        user = authenticate(request, username=request.POST.get("username", "").strip().lower(), password=request.POST.get("password", ""))
        if user is not None and user.is_staff and user.is_active:
            login(request, user)
            safe = nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()})
            return redirect(nxt if safe else "home")
        # same message for a wrong password, an unknown account and a locked one
        error = "Email or password is not right, or the account is locked for a few minutes."
    return render(request, "backoffice/login.html", {"error": error, "next": nxt}, status=200)


@require_POST
def logout_view(request):
    logout(request)
    return redirect("login")


def home(request):
    target = landing_for(request.user)
    if target is None:
        return render(request, "backoffice/not_allowed.html", status=403)
    return redirect(target)
