"""Load providers."""

from .base import LoadProvider
from .builtin import BuiltinLoad
from .command import CommandLoad
from .external import ExternalLoad

BUILTIN = {"builtin": BuiltinLoad, "external": ExternalLoad, "command": CommandLoad}

__all__ = ["LoadProvider", "BuiltinLoad", "CommandLoad", "ExternalLoad", "BUILTIN"]
