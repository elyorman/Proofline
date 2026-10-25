"""Who hears a run's stages as they happen. The live API sets a listener for the question it
is answering and shows each stage to the viewer who asked; batch runs set none. A context
variable, so concurrent questions each hear only their own run."""

from collections.abc import Callable
from contextvars import ContextVar

listener: ContextVar[Callable[[str, str], None] | None] = ContextVar("listener", default=None)


def report(stage: str, note: str = "") -> None:
    if (hear := listener.get()) is not None:
        hear(stage, note)
