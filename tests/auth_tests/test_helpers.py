from django.contrib.auth import get_permission_codename
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
