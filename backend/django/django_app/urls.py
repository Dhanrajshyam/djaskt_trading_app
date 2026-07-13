"""URL configuration for django_app (Djaskt Ledger & Orchestrator)."""

from django.contrib import admin
from django.urls import path
from ninja_extra import NinjaExtraAPI

from ledger.api.router import LedgerController

api = NinjaExtraAPI(title="Djaskt Ledger API", version="1.0.0")
api.register_controllers(LedgerController)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", api.urls),
]
