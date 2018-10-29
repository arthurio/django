from django.apps import AppConfig
from django.contrib.contenttypes.checks import (
    check_generic_foreign_keys, check_model_name_lengths,
)
from django.core import checks
from django.db import migrations
from django.db.models.signals import post_migrate, post_operation
from django.utils.translation import gettext_lazy as _

from .management import (
    create_contenttypes, inject_rename_contenttypes_operations,
)


class ContentTypesConfig(AppConfig):
    name = 'django.contrib.contenttypes'
    verbose_name = _("Content Types")

    def ready(self):
        post_operation.connect(inject_rename_contenttypes_operations, sender=migrations.RenameModel)
        post_migrate.connect(create_contenttypes)
        checks.register(check_generic_foreign_keys, checks.Tags.models)
        checks.register(check_model_name_lengths, checks.Tags.models)
