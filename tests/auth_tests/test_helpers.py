from django.contrib.auth import (
    get_permission_app_label, get_permission_codename, get_permission_model,
    get_permission_natural_key_string,
)
from django.test import TestCase
from django.utils.deprecation import RemovedInDjango31Warning

from .models import CustomUser


class PermissionHelpersDeprecationTests(TestCase):
    def test_get_permission_codename_warning(self):
        msg = (
            "Update django.contrib.auth.get_permission_codename() to receive a "
            "model class as second argument instead of model options."
        )
        with self.assertWarnsMessage(RemovedInDjango31Warning, msg):
            codename = get_permission_codename('add', CustomUser._meta)

        self.assertEqual(codename, 'add_customuser')


class PermissionHelpersTests(TestCase):
    def test_get_permission_app_label(self):
        app_label = get_permission_app_label(CustomUser)
        self.assertEqual(app_label, 'auth_tests')

    def test_get_permission_codename(self):
        codename = get_permission_codename('add', CustomUser)
        self.assertEqual(codename, 'add_customuser')

    def test_get_permission_model(self):
        self.assertEqual(get_permission_model(CustomUser), 'customuser')

    def test_get_permission_natural_key_string(self):
        natural_key_string = get_permission_natural_key_string('add', CustomUser)
        self.assertEqual(natural_key_string, 'auth_tests.add_customuser')
