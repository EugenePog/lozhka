from .permissions import menu_for


def staff(request):
    if not request.user.is_authenticated:
        return {}
    match = request.resolver_match
    return {"menu": menu_for(request.user), "active": match.view_name if match else ""}
