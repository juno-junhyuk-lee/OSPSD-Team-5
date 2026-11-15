"""Optional provider spans; the consumer owns its telemetry setup."""

from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager

SpanFactory = Callable[[str], AbstractContextManager[None]]
_span_factory: SpanFactory | None = None


def set_span_factory(factory: SpanFactory | None) -> None:
    """Configure optional spans without installing a telemetry SDK."""
    global _span_factory
    _span_factory = factory


@contextmanager
def google_call(method: str) -> Iterator[None]:
    factory = _span_factory
    if factory is None:
        yield
    else:
        with factory(method):
            yield
