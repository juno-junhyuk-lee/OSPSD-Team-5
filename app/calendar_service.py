"""Compatibility import for the packaged Calendar implementation."""

import sys

from team5_calendar import calendar_service as _implementation
from team5_calendar.calendar_service import *  # noqa: F403

# Keep legacy imports and controlled-provider patches on the same module object.
sys.modules[__name__] = _implementation
