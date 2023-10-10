from django.contrib import admin
from django.contrib.auth import get_permission_codename
from django.utils.translation import gettext_lazy as _
from django.contrib.admin.models import LogEntry, DELETION
from django.contrib.contenttypes.models import ContentType

from . import (
    models,
    tasks,
)


@admin.register(models.LockedUser)
class LockedUserAdmin(admin.ModelAdmin):
    list_display = (
        "pk",
        "username",
        "last_name",
        "first_name",
        "email",
        "locked",
    )
    search_fields = (
        "local__username",
        "local__email",
        "local__first_name",
        "local__last_name",
    )
    date_hierarchy = "locked"
    actions = ("unlock",)

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .exclude(unlocked__isnull=False)
            .select_related("local")
        )

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_unlock_permission(self, request):
        """Does the user have the unlock permission?"""
        return request.user.has_perm(f"{self.opts.app_label}.unlock")

    def unlock(self, request, queryset):
        for user in queryset:
            tasks.UserTasks().unlock.apply_async((user.pk,), queue="maintainance")
            LogEntry.objects.log_action(
                user_id=request.user.id,
                content_type_id=ContentType.objects.get_for_model(user.__class__).pk,
                object_id=user.id,
                object_repr=user.username,
                action_flag=DELETION,
            )
        self.message_user(
            request,
            "%i successfully queued for unlocking. Please check again in a moment to see if they are gone from the list."
            % queryset.count(),
        )

    unlock.short_description = _("Unlock selected users for new enrollment")
    unlock.allowed_permissions = ("unlock",)
