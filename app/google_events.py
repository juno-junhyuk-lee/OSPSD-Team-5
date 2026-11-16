"""Compatibility import for the packaged Calendar implementation."""

import sys

from team5_calendar import google_events as _implementation
from team5_calendar.google_events import *  # noqa: F403

# Keep legacy imports and controlled-provider patches on the same module object.
sys.modules[__name__] = _implementation
