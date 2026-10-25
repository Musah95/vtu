from django.urls import path

from .views import OrderDetailView, PackageListView, PurchaseView, VerifyView

urlpatterns = [
    path("packages/", PackageListView.as_view()),
    path("verify/", VerifyView.as_view()),
    path("purchase/", PurchaseView.as_view()),
    path("orders/<str:reference>/", OrderDetailView.as_view()),
]