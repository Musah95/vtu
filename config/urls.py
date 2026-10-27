from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/airtime/", include("services.airtime.api.urls")),
    path("api/v1/data/", include("services.data.api.urls")),
    path("api/v1/cable/", include("services.cable.api.urls")),
    path("api/v1/wallet/", include("core.wallet.urls")),
]