from .choice import Choice
from .distribution import Distribution
from .numeric import Numeric
from .text import Text

_REGISTRY = {cls.name: cls() for cls in (Choice, Numeric, Distribution, Text)}


def get(name):
    try:
        return _REGISTRY[name]
    except KeyError:
        raise ValueError(f"unknown interaction type '{name}' (known: {', '.join(sorted(_REGISTRY))})")


def validate(name, config):
    get(name).validate_config(config)


def all_types():
    return list(_REGISTRY)
