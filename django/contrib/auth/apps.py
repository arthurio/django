from django.apps import AppConfig
from django.contrib.contenttypes.management import (
    CreateContentType, RenameContentType,
)
from django.core import checks
from django.db.migrations.operations import AlterModelOptions
from django.db.models.query_utils import DeferredAttribute
from django.db.models.signals import post_migrate, post_operation
from django.utils.translation import gettext_lazy as _

from . import get_user_model
from .checks import check_models_permissions, check_user_model
from .management import (
    create_permissions, inject_create_permissions_for_altered_model,
    inject_create_permissions_for_created_contenttype,
    inject_create_permissions_for_renamed_contenttype,
)
from .signals import user_logged_in


class AuthConfig(AppConfig):
    name = 'django.contrib.auth'
    verbose_name = _("Authentication and Authorization")

    def ready(self):
        post_operation.connect(
            inject_create_permissions_for_altered_model, sender=AlterModelOptions
        )
        post_operation.connect(
            inject_create_permissions_for_created_contenttype, sender=CreateContentType
        )
        post_operation.connect(
            inject_create_permissions_for_renamed_contenttype, sender=RenameContentType
        )
        post_migrate.connect(
            create_permissions,
            dispatch_uid="django.contrib.auth.management.create_permissions"
        )
        last_login_field = getattr(get_user_model(), 'last_login', None)
        # Register the handler only if UserModel.last_login is a field.
        if isinstance(last_login_field, DeferredAttribute):
            from .models import update_last_login
            user_logged_in.connect(update_last_login, dispatch_uid='update_last_login')
        checks.register(check_user_model, checks.Tags.models)
        checks.register(check_models_permissions, checks.Tags.models)
