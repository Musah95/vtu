class ServiceError(Exception):
    """A business-rule error any service can raise, with a stable machine code."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message