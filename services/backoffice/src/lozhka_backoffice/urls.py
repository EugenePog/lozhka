from django.contrib import admin
from django.http import JsonResponse
from django.urls import path

from .permissions import staff_view  # noqa: F401
from .views import admin_area, auth, operator, storekeeper
from django.contrib.auth.decorators import login_required

urlpatterns = [
    path("health", lambda request: JsonResponse({"ok": True}), name="health"),
    path("login/", auth.login_view, name="login"),
    path("logout/", auth.logout_view, name="logout"),
    path("", login_required(auth.home), name="home"),
    # operator
    path("deliveries/", operator.deliveries, name="deliveries"),
    path("deliveries/counters/", operator.tab_counters, name="tab_counters"),
    path("deliveries/<int:pk>/", operator.delivery_detail, name="delivery_detail"),
    path("deliveries/<int:pk>/assign/", operator.delivery_assign, name="delivery_assign"),
    path("deliveries/<int:pk>/plan/", operator.delivery_plan, name="delivery_plan"),
    path("deliveries/<int:pk>/approve/", operator.delivery_approve, name="delivery_approve"),
    path("deliveries/<int:pk>/packing-list/", operator.packing_list, name="packing_list"),
    path("deliveries/<int:pk>/packed/", operator.delivery_packed, name="delivery_packed"),
    path("deliveries/<int:pk>/dispatch/", operator.delivery_dispatch, name="delivery_dispatch"),
    path("deliveries/<int:pk>/close/", operator.close, name="close"),
    path("orders/<int:pk>/move/", operator.order_move, name="order_move"),
    path("orders/<int:pk>/remove/", operator.order_remove, name="order_remove"),
    path("ready/", operator.ready, name="ready"),
    path("confirm/", operator.confirm, name="confirm"),
    path("confirm/<int:pk>/", operator.confirm_detail, name="confirm_detail"),
    path("confirm/<int:pk>/<slug:action>/", operator.confirm_action, name="confirm_action"),
    # storekeeper
    path("incoming/", storekeeper.incoming, name="incoming"),
    path("incoming/upload/", storekeeper.incoming_upload, name="incoming_upload"),
    path("incoming/<int:pk>/save/", storekeeper.incoming_save, name="incoming_save"),
    path("stock/", storekeeper.stock, name="stock"),
    path("stock/<int:lot_id>/adjust/", storekeeper.stock_adjust, name="stock_adjust"),
    # admin
    path("templates/", admin_area.templates, name="templates"),
    path("templates/preview/", admin_area.templates_preview, name="templates_preview"),
    path("rules/", admin_area.rules, name="rules"),
    path("return-reasons/", admin_area.return_reasons, name="return_reasons"),
    path("suppliers/", admin_area.suppliers, name="suppliers"),
    path("suppliers/<int:pk>/", admin_area.supplier_detail, name="supplier_detail"),
    path("suppliers/<int:pk>/credentials/", admin_area.supplier_credential, name="supplier_credential"),
    path("admin/", admin.site.urls),
]
