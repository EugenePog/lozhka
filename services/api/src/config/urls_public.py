from django.urls import path

from lozhka_api.api.main import api

urlpatterns = [path("api/v1/", api.urls)]
