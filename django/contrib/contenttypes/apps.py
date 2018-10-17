from django.apps import AppConfig
from django.contrib.contenttypes.checks import (
    check_generic_foreign_keys, check_model_name_lengths,
)
from django.core import checks
from django.db.models.signals import post_migrate, pre_write_migration
from django.utils.translation import gettext_lazy as _

from .management import create_contenttypes, inject_contenttypes_operations


class ContentTypesConfig(AppConfig):
    name = 'django.contrib.contenttypes'
    verbose_name = _("Content Types")

    def ready(self):
        post_migrate.connect(create_contenttypes)
        pre_write_migration.connect(inject_contenttypes_operations)
        checks.register(check_generic_foreign_keys, checks.Tags.models)
        checks.register(check_model_name_lengths, checks.Tags.models)
