"""TerminalCrypt package."""

__version__ = "3.2.0"

from .app import CryptexApp
from .cli import main

__all__ = ["CryptexApp", "main"]
