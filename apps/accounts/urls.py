from django.urls import path

from apps.accounts import views

app_name = "accounts"

urlpatterns = [
    path("signup/", views.signup, name="signup"),
]
