"""Compatibility import for the packaged Calendar implementation."""

import sys
from pathlib import Path

from team5_calendar import google_auth as _implementation
from team5_calendar.google_auth import *  # noqa: F403

_implementation.ROOT = Path(__file__).resolve().parents[1]

# Keep legacy imports and controlled-provider patches on the same module object.
sys.modules[__name__] = _implementation
