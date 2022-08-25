import logging
from datetime import (
    datetime,
    timedelta,
)

import duo_client
import isodate
from celery import shared_task
from django.contrib.auth import get_user_model
from django.core.cache import caches
from django.core.cache.backends.base import InvalidCacheBackendError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_auth_ldap.backend import LDAPBackend
from ldap3 import (
    ALL,
    SAFE_SYNC,
    Connection,
    ObjectDef,
    Reader,
    Server,
)
from tenacity import (
    RetryError,
    Retrying,
    stop_after_attempt,
    wait_exponential,
)

from .conf import settings

logger = logging.getLogger(__name__)


class UserTasks:
    @shared_task(bind=True, ignore_result=True, name=f"{__name__}.User:synchronize")
    def synchronize(task, base, dry_run=False):
        from .models import LockedUser

        logger.info("Synchronizing users to DUO")

        if task.request.delivery_info:
            queue = task.request.delivery_info.get("routing_key")
        else:
            queue = None

        api = duo_client.Admin(
            ikey=settings.MFA_DUO_IKEY,
            skey=settings.MFA_DUO_SKEY,
            host=settings.MFA_DUO_API_HOST,
        )

        ldap = Connection(
            Server(settings.MFA_LDAP_HOST, get_info=ALL),
            settings.MFA_LDAP_BIND_DN,
            settings.MFA_LDAP_PASSWORD,
            auto_bind=True,
            auto_range=True,
            client_strategy=SAFE_SYNC,
        )

        duo_users = {u["username"]: u for u in api.get_users()}

        mfa_group = (
            Reader(ldap, ObjectDef("group", ldap), settings.MFA_LDAP_GROUP_USERS)
            .search_object()
            .entry_writable()
        )
        reader = Reader(
            ldap,
            ObjectDef("person", ldap),
            base,
            attributes=("cn", "distinguishedName"),
        )

        retry = Retrying(
            stop=stop_after_attempt(10),
            wait=wait_exponential(multiplier=1, min=4, max=10),
        )

        for c, u in enumerate(reader.search()):
            if queue:
                task.update_state(state="PROGRESS", meta={"progress": c})
            duo = duo_users.get(u.cn.value)
            if duo:
                logger.debug(f"User {u.cn.value} is already enabled for DUO")
                if duo.get("is_enrolled"):
                    try:
                        locked = LockedUser.objects.get(local__username=u.cn.value)
                    except LockedUser.DoesNotExist:
                        pass
                    else:
                        locked.delete()
                continue
            if u.distinguishedName.value not in mfa_group.member.values:
                mfa_group.member += u.distinguishedName.value
                if not dry_run:
                    if not mfa_group.entry_commit_changes():
                        logger.error(f"Could not add {u.cn.value} to mfa_group")
                        continue
                    if queue:
                        UserTasks.activate.apply_async((u.cn.value,), queue=queue)
                        continue
                    try:
                        for attempt in retry.copy():
                            with attempt:
                                logger.info(f"Activating user {u.cn.value} for DUO")
                                api.sync_user(
                                    u.cn.value, settings.MFA_DUO_DIRECTORY_KEY
                                )
                    except RetryError:
                        logger.error(f"Could not activate {u.cn.value} for DUO")

    @shared_task(
        bind=True, ignore_result=True, name=f"{__name__}.User:enrollment_timeout"
    )
    def enrollment_timeout(task, base, interval, dry_run=False):
        from .models import LockedUser

        User = get_user_model()

        logger.info("Locking users with expired DUO enrollment")

        api = duo_client.Admin(
            ikey=settings.MFA_DUO_IKEY,
            skey=settings.MFA_DUO_SKEY,
            host=settings.MFA_DUO_API_HOST,
        )

        ldap = Connection(
            Server(settings.MFA_LDAP_HOST, get_info=ALL),
            settings.MFA_LDAP_BIND_DN,
            settings.MFA_LDAP_PASSWORD,
            auto_bind=True,
            auto_range=True,
            client_strategy=SAFE_SYNC,
        )

        duo_users = {u["username"]: u for u in api.get_users()}

        mfa_locked_group = (
            Reader(ldap, ObjectDef("group", ldap), settings.MFA_LDAP_GROUP_USERS_LOCKED)
            .search_object()
            .entry_writable()
        )
        reader = Reader(
            ldap,
            ObjectDef("person", ldap),
            base,
            attributes=("cn", "distinguishedName"),
        )

        now = datetime.now()

        delta = isodate.parse_duration(interval)

        for c, u in enumerate(reader.search()):
            if task.request.delivery_info:
                task.update_state(state="PROGRESS", meta={"progress": c})
            duo = duo_users.get(u.cn.value)
            if not duo:
                logger.debug(f"User {u.cn.value} ist not activated for DUO")
                continue
            if duo.get("is_enrolled"):
                logger.debug(f"User {u.cn.value} is already enrolled in DUO")
                continue
            diff = now - datetime.fromtimestamp(duo.get("created"))
            if diff < delta:
                logger.debug(
                    f"User {u.cn.value} is within enrollment window {diff} for DUO"
                )
                continue

            try:
                user = LockedUser.objects.get(local__username=u.cn.value)
            except LockedUser.DoesNotExist:
                logger.debug(
                    f"User {u.cn.value} is locked but no local objects has been found"
                )
            else:
                logger.debug(f"User {u.cn.value} has local lock object")
                if u.distinguishedName.value in mfa_locked_group.member.values:
                    logger.debug(
                        f"User {u.cn.value} is already locked from enrollment window {diff} for DUO"
                    )
                    if user.unlocked:
                        user.locked = timezone.now()
                        user.unlocked = None
                        user.save()
                    continue
                if user.unlocked:
                    if now - user.unlocked < delta:
                        logger.debug(
                            f"User {u.cn.value} has local unlock and is within enrollment window"
                        )
                        continue

            if dry_run:
                continue
            try:
                local = User.objects.get(username=u.cn.value)
            except User.DoesNotExist:
                local = LDAPBackend().populate_user(u.cn.value)
                if local is None:
                    logger.error(
                        f"Could not populate local user {u.cn.value} from LDAP"
                    )
                    continue
            user, created = LockedUser.objects.get_or_create(local=local)
            if created or not user.locked:
                transaction.on_commit(lambda: UserTasks().lock.delay(user.pk))

    @shared_task(bind=True, ignore_result=True, name=f"{__name__}.User:lock")
    def lock(task, pk, dry_run=False):
        from .models import LockedUser

        user = LockedUser.objects.get(pk=pk)

        logger.info(f"Locking user {user} with expired DUO enrollment")

        ldap = Connection(
            Server(settings.MFA_LDAP_HOST, get_info=ALL),
            settings.MFA_LDAP_BIND_DN,
            settings.MFA_LDAP_PASSWORD,
            auto_bind=True,
            auto_range=True,
            client_strategy=SAFE_SYNC,
        )

        mfa_locked_group = (
            Reader(ldap, ObjectDef("group", ldap), settings.MFA_LDAP_GROUP_USERS_LOCKED)
            .search_object()
            .entry_writable()
        )

        reader = Reader(
            ldap,
            ObjectDef("person", ldap),
            settings.MFA_LDAP_BASE,
            f"(cn={user.local.username})",
            attributes=("cn", "distinguishedName"),
        )

        ad_user = next(iter(reader.search()), None)

        if ad_user.distinguishedName.value in mfa_locked_group.member.values:
            logger.debug(f"User {ad_user.cn.value} is already locked out from DUO")

            user.unlocked = None
            if not user.locked:
                user.locked = timezone.now()
        else:
            mfa_locked_group.member += ad_user.distinguishedName.value
            if not dry_run:
                if mfa_locked_group.entry_commit_changes():
                    user.locked = timezone.now()
                    user.unlocked = None
                else:
                    logger.error(
                        f"Could not add {ad_user.cn.value} to MFA locked group"
                    )
        if not dry_run:
            user.save()

    @shared_task(bind=True, ignore_result=True, name=f"{__name__}.User:unlock")
    def unlock(task, pk, dry_run=False):
        from .models import LockedUser

        user = LockedUser.objects.get(pk=pk)

        logger.info(f"Unlocking user {user} for DUO enrollment")

        ldap = Connection(
            Server(settings.MFA_LDAP_HOST, get_info=ALL),
            settings.MFA_LDAP_BIND_DN,
            settings.MFA_LDAP_PASSWORD,
            auto_bind=True,
            auto_range=True,
            client_strategy=SAFE_SYNC,
        )

        mfa_locked_group = (
            Reader(ldap, ObjectDef("group", ldap), settings.MFA_LDAP_GROUP_USERS_LOCKED)
            .search_object()
            .entry_writable()
        )

        reader = Reader(
            ldap,
            ObjectDef("person", ldap),
            settings.MFA_LDAP_BASE,
            f"(cn={user.local.username})",
            attributes=("cn", "distinguishedName"),
        )

        ad_user = next(iter(reader.search()), None)

        if not ad_user:
            logger.error(f"Could not find {user.local.username} through LDAP")
            user.delete()
            return

        if ad_user.distinguishedName.value not in mfa_locked_group.member.values:
            logger.warning(
                f"User {ad_user.cn.value} is no member of locked group in LDAP"
            )
            user.locked = None
            if not user.unlocked:
                user.unlocked = timezone.now()
        else:
            mfa_locked_group.member -= ad_user.distinguishedName.value
            if not dry_run:
                if mfa_locked_group.entry_commit_changes():
                    user.locked = None
                    user.unlocked = timezone.now()
                else:
                    logger.error(
                        f"Could not remove {ad_user.cn.value} from mfa_group_locked"
                    )
        if not dry_run:
            user.save()

    @shared_task(
        bind=True,
        ignore_result=True,
        name=f"{__name__}.User:activate",
        max_retries=10,
    )
    def activate(task, username):
        api = duo_client.Admin(
            ikey=settings.MFA_DUO_IKEY,
            skey=settings.MFA_DUO_SKEY,
            host=settings.MFA_DUO_API_HOST,
        )
        ldap = Connection(
            Server(settings.MFA_LDAP_HOST, get_info=ALL),
            settings.MFA_LDAP_BIND_DN,
            settings.MFA_LDAP_PASSWORD,
            auto_bind=True,
            auto_range=True,
            client_strategy=SAFE_SYNC,
        )

        ad_user = Reader(
            ldap,
            ObjectDef("person", ldap),
            settings.MFA_LDAP_BASE,
            f"(cn={username}",
            attributes=("cn", "distinguishedName"),
        ).search_object()

        if settings.MFA_LDAP_GROUP_USERS not in ad_user.memberOf.values:
            logger.error(f"User {username} not present in MFA LDAP group.")
            if task.request.delivery_info:
                task.retry(countdown=3 ** task.request.retries)
            return

        logger.info(f"Activating user {username} for DUO")

        try:
            api.sync_user(username, settings.MFA_DUO_DIRECTORY_KEY)
        except RuntimeError:
            logger.error(f"Could not activate {username} for DUO")
            if task.request.delivery_info:
                task.retry(countdown=3 ** task.request.retries)
