"""
Creates permissions for all installed apps that need permissions.
"""
import getpass
import unicodedata

from django.apps import apps as global_apps
from django.contrib.auth import get_permission_codename
from django.contrib.contenttypes.management import create_contenttypes
from django.core import exceptions
from django.db import DEFAULT_DB_ALIAS, migrations, router
from django.db.utils import OperationalError


def _get_all_permissions(opts):
    """
    Return (codename, name) for all permissions in the given opts.
    """
    return [*_get_builtin_permissions(opts), *opts.permissions]


def _get_builtin_permissions(opts):
    """
    Return (codename, name) for all autogenerated permissions.
    By default, this is ('add', 'change', 'delete', 'view')
    """
    perms = []
    for action in opts.default_permissions:
        perms.append((
            get_permission_codename(action, opts),
            'Can %s %s' % (action, opts.verbose_name_raw)
        ))
    return perms


def create_permissions(app_config, verbosity=2, interactive=True, using=DEFAULT_DB_ALIAS, apps=global_apps, **kwargs):
    if not app_config.models_module:
        return

    # Ensure that contenttypes are created for this app. Needed if
    # 'django.contrib.auth' is in INSTALLED_APPS before
    # 'django.contrib.contenttypes'.
    create_contenttypes(app_config, verbosity=verbosity, interactive=interactive, using=using, apps=apps, **kwargs)

    app_label = app_config.label
    try:
        app_config = apps.get_app_config(app_label)
        ContentType = apps.get_model('contenttypes', 'ContentType')
        Permission = apps.get_model('auth', 'Permission')
    except LookupError:
        return

    if not router.allow_migrate_model(using, Permission):
        return

    # This will hold the permissions we're looking for as
    # (content_type, (codename, name))
    searched_perms = []
    # The codenames and ctypes that should exist.
    ctypes = set()
    for klass in app_config.get_models():
        # Force looking up the content types in the current database
        # before creating foreign keys to them.
        ctype = ContentType.objects.db_manager(using).get_for_model(klass, for_concrete_model=False)

        ctypes.add(ctype)
        for perm in _get_all_permissions(klass._meta):
            searched_perms.append((ctype, perm))

    # Find all the Permissions that have a content_type for a model we're
    # looking for.  We don't need to check for codenames since we already have
    # a list of the ones we're going to create.
    all_perms = set(Permission.objects.using(using).filter(
        content_type__in=ctypes,
    ).values_list(
        "content_type", "codename"
    ))

    perms = [
        Permission(codename=codename, name=name, content_type=ct)
        for ct, (codename, name) in searched_perms
        if (ct.pk, codename) not in all_perms
    ]
    Permission.objects.using(using).bulk_create(perms)
    if verbosity >= 2:
        for perm in perms:
            print("Adding permission '%s'" % perm)


class CreatePermission(migrations.RunPython):
    def __init__(self, app_label, model, codename, name):
        self.app_label = app_label
        self.model = model
        self.codename = codename
        self.name = name
        super().__init__(self.create_forward, self.noop)

    def create_forward(self, apps, schema_editor):
        try:
            ContentType = apps.get_model('contenttypes', 'ContentType')
            Permission = apps.get_model('auth', 'Permission')
        except LookupError:
            return

        db = schema_editor.connection.alias
        if not router.allow_migrate_model(db, Permission):
            return

        try:
            content_type = ContentType.objects.get_by_natural_key(self.app_label, self.model)
            Permission.objects.using(db).get_or_create(
                content_type=content_type,
                codename=self.codename,
                name=self.name,
            )
        except OperationalError:
            # We are trying to create a permission before all the migrations for
            # ContentType and Permission are applied.
            # TODO: Register post_migrate(defer_permission_creation)?
            pass


def inject_create_permissions(migration, operation, from_state, model_name):
    if ('auth', 'permission') not in from_state.models:
        return

    Model = global_apps.get_model(migration.app_label, model_name)
    opts = Model._meta

    for codename, name in _get_all_permissions(opts):
        yield CreatePermission(migration.app_label, model_name, codename, name)


def inject_create_permissions_for_created_contenttype(migration, operation, from_state, **kwargs):
    return inject_create_permissions(migration, operation, from_state, operation.model)


def inject_create_permissions_for_renamed_contenttype(migration, operation, from_state, **kwargs):
    return inject_create_permissions(migration, operation, from_state, operation.new_model)


def inject_create_permissions_for_altered_model(migration, operation, from_state, **kwargs):
    return inject_create_permissions(migration, operation, from_state, operation.name)


def get_system_username():
    """
    Return the current system user's username, or an empty string if the
    username could not be determined.
    """
    try:
        result = getpass.getuser()
    except (ImportError, KeyError):
        # KeyError will be raised by os.getpwuid() (called by getuser())
        # if there is no corresponding entry in the /etc/passwd file
        # (a very restricted chroot environment, for example).
        return ''
    return result


def get_default_username(check_db=True):
    """
    Try to determine the current system user's username to use as a default.

    :param check_db: If ``True``, requires that the username does not match an
        existing ``auth.User`` (otherwise returns an empty string).
    :returns: The username, or an empty string if no username can be
        determined.
    """
    # This file is used in apps.py, it should not trigger models import.
    from django.contrib.auth import models as auth_app

    # If the User model has been swapped out, we can't make any assumptions
    # about the default user name.
    if auth_app.User._meta.swapped:
        return ''

    default_username = get_system_username()
    try:
        default_username = (
            unicodedata.normalize('NFKD', default_username)
            .encode('ascii', 'ignore').decode('ascii')
            .replace(' ', '').lower()
        )
    except UnicodeDecodeError:
        return ''

    # Run the username validator
    try:
        auth_app.User._meta.get_field('username').run_validators(default_username)
    except exceptions.ValidationError:
        return ''

    # Don't return the default username if it is already taken.
    if check_db and default_username:
        try:
            auth_app.User._default_manager.get(username=default_username)
        except auth_app.User.DoesNotExist:
            pass
        else:
            return ''
    return default_username
