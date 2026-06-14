from django.urls import path

from . import views


app_name = "filings"

urlpatterns = [
    path("", views.home, name="home"),
    path("companies/confirm/", views.confirm_company, name="confirm_company"),
    path("filings/select/", views.select_filing, name="select_filing"),
    path("filings/<int:pk>/", views.detail, name="detail"),
]
