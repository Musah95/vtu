_registry = {}


class ProviderNotFound(Exception):
    pass


def register(cls):
    """Class decorator: makes an adapter available by its `name`."""
    _registry[cls.name] = cls
    return cls


def get_adapter(name):
    try:
        return _registry[name]()
    except KeyError:
        raise ProviderNotFound(name)