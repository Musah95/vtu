from .dev import *  # noqa

# Tests always run tasks inline, whatever your .env says.
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True