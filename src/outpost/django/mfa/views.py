from urllib.request import urlopen

from braces.views import LoginRequiredMixin
from django.core.files.base import ContentFile
from django.http import HttpResponseRedirect
from django.views.generic import FormView

from . import (
    forms,
    models,
)
from .conf import settings
from .tasks import UserTasks


class EnrollmentUnlockView(LoginRequiredMixin, FormView):
    template_name = "mfa/enrollment/form.html"
    form_class = forms.EnrollmentUnlockForm
    success_url = settings.MFA_ENROLLMENT_URL

    def dispatch(self, request, *args, **kwargs):
        remote = request.META.get("REMOTE_ADDR")
        if not remote:
            return HttpResponseRedirect(self.get_success_url())
        if not models.UnlockNetwork.objects.filter(
            inet__net_contains_or_equals=remote
        ).exists():
            return HttpResponseRedirect(self.get_success_url())
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        try:
            models.LockedUser.objects.get(local=request.user)
        except models.LockedUser.DoesNotExist:
            return HttpResponseRedirect(self.get_success_url())
        return super().get(request, *args, **kwargs)

    def form_valid(self, form):
        try:
            user = models.LockedUser.objects.get(local=self.request.user)
            UserTasks().unlock(user.pk)
        except models.LockedUser.DoesNotExist:
            return HttpResponseRedirect(self.get_success_url())
        with urlopen(form.cleaned_data.get("image")) as response:
            data = response.read()
        image = ContentFile(data, "cam.png")
        models.UnlockEvent.objects.create(local=self.request.user, image=image)
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        kwargs[
            "MFA_ENROLLMENT_PHOTO_EXPIRATION_DAYS"
        ] = settings.MFA_ENROLLMENT_PHOTO_EXPIRATION_DAYS
        kwargs["MFA_ENROLLMENT_WINDOW_DAYS"] = settings.MFA_ENROLLMENT_WINDOW_DAYS
        kwargs["MFA_ENROLLMENT_HELP_URL"] = settings.MFA_ENROLLMENT_HELP_URL
        return super().get_context_data(**kwargs)
