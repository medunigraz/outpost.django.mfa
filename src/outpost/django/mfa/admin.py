from django.contrib import admin
from django.contrib.auth import get_permission_codename
from django.utils.translation import gettext_lazy as _

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
        """Does the user have the publish permission?"""
        opts = self.opts
        codename = get_permission_codename("unlock", opts)
        return request.user.has_perm("%s.%s" % (opts.app_label, codename))

    def unlock(self, request, queryset):
        for user in queryset:
            tasks.UserTasks.unlock.delay(user.pk)
        self.message_user(
            request,
            "%i successfully queued for unlocking. Please check again in a moment to see if they are gone from the list."
            % queryset.count(),
        )

    unlock.short_description = _("Unlock selected users for new enrollment")
    unlock.allowed_permissions = ("unlock",)
