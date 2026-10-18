from django.urls import path

from .views import NetworkListView, OrderDetailView, PurchaseView

urlpatterns = [
    path("networks/", NetworkListView.as_view()),
    path("purchase/", PurchaseView.as_view()),
    path("orders/<str:reference>/", OrderDetailView.as_view()),
]