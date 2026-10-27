import hashlib
import hmac
import secrets
from datetime import timedelta

from django.utils import timezone

from .models import ApiKey

TOUCH_EVERY = timedelta(minutes=1)


def hash_secret(secret):
    # Secrets are 256 bits of randomness, so a fast hash is enough. Slow
    # hashing exists to protect guessable passwords, which these are not.
    return hashlib.sha256(secret.encode()).hexdigest()


def generate_credentials():
    key_id = "vk_" + secrets.token_hex(8)
    secret = secrets.token_urlsafe(32)
    return key_id, secret, hash_secret(secret)


def create_key(user, label=""):
    """Returns (api_key, secret). The secret exists only in this return value."""
    key_id, secret, secret_hash = generate_credentials()
    api_key = ApiKey.objects.create(
        user=user, label=label, key_id=key_id, secret_hash=secret_hash
    )
    return api_key, secret


def revoke_key(api_key):
    if api_key.revoked_at is None:
        api_key.revoked_at = timezone.now()
        api_key.save(update_fields=["revoked_at"])


def verify_key(key_id, secret):
    """Return the ApiKey if the pair is valid and usable, otherwise None."""
    try:
        api_key = ApiKey.objects.select_related("user").get(key_id=key_id)
    except ApiKey.DoesNotExist:
        return None
    if not hmac.compare_digest(api_key.secret_hash, hash_secret(secret)):
        return None
    if api_key.revoked_at is not None or not api_key.user.is_active:
        return None

    now = timezone.now()
    if api_key.last_used_at is None or now - api_key.last_used_at > TOUCH_EVERY:
        ApiKey.objects.filter(pk=api_key.pk).update(last_used_at=now)
    return api_key