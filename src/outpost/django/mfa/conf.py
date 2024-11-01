from appconf import AppConf
from django.conf import settings


class MFAAppConf(AppConf):
    DUO_IKEY = None
    DUO_SKEY = None
    DUO_API_HOST = None
    DUO_DIRECTORY_KEY = None
    LDAP_HOST = None
    LDAP_BASE = None
    LDAP_BIND_DN = None
    LDAP_PASSWORD = None
    LDAP_GROUP_USERS = None
    LDAP_GROUP_USERS_LOCKED = None
    ENROLLMENT_URL = "http://localhost"
    ENROLLMENT_PHOTO_EXPIRATION_DAYS = 14
    ENROLLMENT_WINDOW_DAYS = 3
    ENROLLMENT_HELP_URL = "http://localhost"

    class Meta:
        prefix = "mfa"
