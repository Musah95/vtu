from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from .services import create_key, revoke_key


class ApiKeyTests(TestCase):
    url = "/api/v1/wallet/balance/"

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="r1", email="r1@example.com", password="pass12345", role="reseller"
        )
        self.key, self.secret = create_key(self.user, "production")

    def call(self, key_id=None, secret=None, header=None):
        client = APIClient()
        value = header or f"Key {key_id or self.key.key_id}:{secret or self.secret}"
        client.credentials(HTTP_AUTHORIZATION=value)
        return client.get(self.url)

    def test_valid_key_authenticates(self):
        self.assertEqual(self.call().status_code, 200)

    def test_secret_is_stored_hashed(self):
        self.assertNotEqual(self.key.secret_hash, self.secret)
        self.assertEqual(len(self.key.secret_hash), 64)

    def test_wrong_secret_is_rejected(self):
        self.assertEqual(self.call(secret="not-the-secret").status_code, 401)

    def test_unknown_key_is_rejected(self):
        self.assertEqual(self.call(key_id="vk_doesnotexist").status_code, 401)

    def test_revoked_key_is_rejected_but_others_still_work(self):
        second, second_secret = create_key(self.user, "staging")
        revoke_key(self.key)
        self.assertEqual(self.call().status_code, 401)
        self.assertEqual(self.call(second.key_id, second_secret).status_code, 200)

    def test_inactive_user_is_rejected(self):
        self.user.is_active = False
        self.user.save()
        self.assertEqual(self.call().status_code, 401)

    def test_malformed_headers_are_rejected(self):
        self.assertEqual(self.call(header="Key").status_code, 401)
        self.assertEqual(self.call(header="Key nonsense").status_code, 401)

    def test_other_schemes_are_ignored(self):
        self.assertEqual(self.call(header="Bearer abc").status_code, 401)

    def test_last_used_is_recorded(self):
        self.call()
        self.key.refresh_from_db()
        self.assertIsNotNone(self.key.last_used_at)

    def test_no_credentials_is_rejected(self):
        self.assertEqual(APIClient().get(self.url).status_code, 401)