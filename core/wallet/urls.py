from django.urls import path

from .api import BalanceView

urlpatterns = [
    path("balance/", BalanceView.as_view()),
]