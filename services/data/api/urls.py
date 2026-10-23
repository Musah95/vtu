from django.urls import path

from .views import OrderDetailView, PlanListView, PurchaseView

urlpatterns = [
    path("plans/", PlanListView.as_view()),
    path("purchase/", PurchaseView.as_view()),
    path("orders/<str:reference>/", OrderDetailView.as_view()),
]