"""Compatibility import for the packaged Calendar implementation."""

import sys
from pathlib import Path

from team5_calendar import google_create_events as _implementation
from team5_calendar.google_create_events import *  # noqa: F403

_implementation.TOKEN_PATH = Path(__file__).resolve().parents[1] / "token.json"

# Keep legacy imports and controlled-provider patches on the same module object.
sys.modules[__name__] = _implementation
