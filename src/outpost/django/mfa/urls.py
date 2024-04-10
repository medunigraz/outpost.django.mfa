from django.urls import path

from . import views

app_name = "mfa"

urlpatterns = [
    path(
        "enrollment/unlock/",
        views.EnrollmentUnlockView.as_view(),
        name="enrollment-unlock",
    ),
]
