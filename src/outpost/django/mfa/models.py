from django.contrib.auth import get_user_model
from django.db import models

from .tasks import UserTasks


class LockedUser(models.Model):
    local = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    locked = models.DateTimeField(null=True, blank=True)
    unlocked = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("local__last_name", "local__first_name")

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
