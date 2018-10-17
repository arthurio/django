from django.apps import apps as global_apps
from django.contrib import contenttypes
from django.db import DEFAULT_DB_ALIAS, migrations, router, transaction
from django.db.migrations.migration import migration_names
from django.db.utils import IntegrityError


class RenameContentType(migrations.RunPython):
    def __init__(self, app_label, old_model, new_model):
        self.app_label = app_label
        self.old_model = old_model
        self.new_model = new_model
        super().__init__(self.rename_forward, self.rename_backward)

    def _rename(self, apps, schema_editor, old_model, new_model):
        ContentType = apps.get_model('contenttypes', 'ContentType')
        db = schema_editor.connection.alias
        if not router.allow_migrate_model(db, ContentType):
            return

        try:
            content_type = ContentType.objects.db_manager(db).get_by_natural_key(self.app_label, old_model)
        except ContentType.DoesNotExist:
            pass
        else:
            content_type.model = new_model
            try:
                with transaction.atomic(using=db):
                    content_type.save(update_fields={'model'})
            except IntegrityError:
                # Gracefully fallback if a stale content type causes a
                # conflict as remove_stale_contenttypes will take care of
                # asking the user what should be done next.
                content_type.model = old_model
            else:
                # Clear the cache as the `get_by_natual_key()` call will cache
                # the renamed ContentType instance by its old model name.
                ContentType.objects.clear_cache()

    def rename_forward(self, apps, schema_editor):
        self._rename(apps, schema_editor, self.old_model, self.new_model)

    def rename_backward(self, apps, schema_editor):
        self._rename(apps, schema_editor, self.new_model, self.old_model)

    def describe(self):
        return "Rename contenttype from {}.{} to {}.{}".format(
            self.app_label,
            self.old_name,
            self.new_name,
        )


class CreateOrDeleteContentTypeMixin:
    def create_content_type(self, apps, schema_editor):
        ContentType = apps.get_model("contenttypes", "ContentType")
        db = schema_editor.connection.alias
        if not router.allow_migrate_model(db, ContentType):
            return

        try:
            ContentType.objects.db_manager(db).create(
                app_label=self.app_label, model=self.model_name
            )
        except IntegrityError:
            # XXX(arthurio): Do something about it?
            pass

    def delete_content_type(self, apps, schema_editor):
        ContentType = apps.get_model("contenttypes", "ContentType")
        db = schema_editor.connection.alias
        if not router.allow_migrate_model(db, ContentType):
            return

        try:
            ContentType.objects.db_manager(db).get(
                app_label=self.app_label, model=self.model_name
            ).delete()
            ContentType.objects.clear_cache()
        except ContentType.DoesNotExist:
            # XXX(arthurio): Do something about it?
            pass


class CreateContentType(migrations.RunPython, CreateOrDeleteContentTypeMixin):
    def __init__(self, app_label, model_name):
        self.app_label = app_label
        self.model_name = model_name
        super().__init__(self.create_content_type, self.delete_content_type)

    def describe(self):
        return "Create content type {}.{}".format(
            self.app_label,
            self.model_name,
        )

    def deconstruct(self):
        kwargs = {
            'app_label': self.app_label,
            'model_name': self.model_name,
        }
        return (
            self.__class__.__qualname__,
            [],
            kwargs
        )


class DeleteContentType(migrations.RunPython, CreateOrDeleteContentTypeMixin):
    def __init__(self, app_label, model_name):
        self.app_label = app_label
        self.model_name = model_name
        super().__init__(self.delete_content_type, self.create_content_type)

    def describe(self):
        return "Delete content type {}.{}".format(
            self.app_label,
            self.model_name,
        )


def get_contenttypes_and_models(app_config, using, ContentType):
    if not router.allow_migrate_model(using, ContentType):
        return None, None

    ContentType.objects.clear_cache()

    content_types = {
        ct.model: ct
        for ct in ContentType.objects.using(using).filter(app_label=app_config.label)
    }
    app_models = {
        model._meta.model_name: model
        for model in app_config.get_models()
    }
    return content_types, app_models


def inject_contenttypes_operations(app_label, app_migrations, using=DEFAULT_DB_ALIAS, **kwargs):
    try:
        ContentType = global_apps.get_model('contenttypes', 'ContentType')
    except LookupError:
        return
    else:
        if not router.allow_migrate_model(using, ContentType):
            return

    for migration in app_migrations:
        inserts = []

        contenttypes_operations_inserted = False
        for index, operation in enumerate(migration.operations):
            contenttypes_operation = None
            if isinstance(operation, migrations.RenameModel):
                contenttypes_operation = RenameContentType(
                    migration.app_label, operation.old_name_lower, operation.new_name_lower,
                )

            if isinstance(operation, migrations.CreateModel):
                contenttypes_operation = CreateContentType(
                    migration.app_label, operation.name_lower,
                )

            if isinstance(operation, migrations.DeleteModel):
                contenttypes_operation = DeleteContentType(
                    migration.app_label, operation.name_lower,
                )

            if contenttypes_operation:
                inserts.append((index + 1, contenttypes_operation))
                contenttypes_operations_inserted = True

        for inserted, (index, operation) in enumerate(inserts):
            migration.operations.insert(inserted + index, operation)

        if contenttypes_operations_inserted:
            last_migration = sorted(migration_names(contenttypes.migrations), reverse=True)[0]
            migration.dependencies.append(('contenttypes', last_migration))
            # TODO(arthurio): Emit post_insert_contenttypes_operations
