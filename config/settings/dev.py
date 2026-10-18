from .base import *

DEBUG = True
ALLOWED_HOSTS = ["*"]
# Tasks run inline by default so you don't need Redis in development.
# To use a real worker, put CELERY_EAGER=False in your .env file.
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_EAGER", default=True)
CELERY_TASK_EAGER_PROPAGATES = True