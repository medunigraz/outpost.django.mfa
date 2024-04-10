from django.contrib.auth import get_user_model
from django.db import models
from django.utils.translation import gettext_lazy as _
from netfields import (
    CidrAddressField,
    NetManager,
)
from outpost.django.base.utils import Uuid4Upload
from outpost.django.base.validators import FileValidator


class LockedUser(models.Model):
    local = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    locked = models.DateTimeField(null=True, blank=True)
    unlocked = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("local__last_name", "local__first_name")
        permissions = (("unlock", _("Can unlock users for enrollment")),)

    @property
    def username(self):
        return self.local.username

    @property
    def email(self):
        return self.local.email

    @property
    def first_name(self):
        return self.local.first_name

    @property
    def last_name(self):
        return self.local.last_name

    def __str__(self):
        return self.local.username


class UnlockEvent(models.Model):
    local = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True)
    image = models.ImageField(
        upload_to=Uuid4Upload,
        null=True,
        validators=(FileValidator(mimetypes=["image/png"]),),
    )

    def __str__(self):
        return f"{self.local}: {self.created}"


class UnlockNetwork(models.Model):
    name = models.CharField(max_length=256)
    inet = CidrAddressField()

    objects = NetManager()

    def __str__(self):
        return f"{self.name} ({self.inet})"
