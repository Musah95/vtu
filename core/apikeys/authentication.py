from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

from .services import verify_key


class ApiKeyAuthentication(BaseAuthentication):
    """Authorization: Key <key_id>:<secret>"""
    keyword = "Key"

    def authenticate_header(self, request):
        return self.keyword

    def authenticate(self, request):
        parts = get_authorization_header(request).split(None, 1)
        if not parts or parts[0].decode("latin-1").lower() != self.keyword.lower():
            return None                        # not an API-key request: let other methods try
        if len(parts) != 2:
            raise AuthenticationFailed("Invalid API key.")
        try:
            key_id, secret = parts[1].decode("latin-1").split(":", 1)
        except ValueError:
            raise AuthenticationFailed("Invalid API key.")

        api_key = verify_key(key_id, secret)
        if api_key is None:
            # Same message for unknown key, wrong secret, revoked: tells an attacker nothing.
            raise AuthenticationFailed("Invalid API key.")
        return (api_key.user, api_key)         # request.auth is the ApiKey