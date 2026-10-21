"""Match clock with stoppage time, and windows over it.

Text forms:
  "12:30"     first half, 12 minutes 30 seconds
  "45+2:10"   first-half stoppage, 47 minutes 10 seconds into the half
  "63:12"     second half (any minute >= 45 without a '+' is second half)
  "90+3:05"   second-half stoppage
"""

from __future__ import annotations

import re
from functools import total_ordering
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

_CLOCK_RE = re.compile(r"^(?P<base>\d{1,3})(?:\+(?P<extra>\d{1,2}))?:(?P<sec>\d{2})$")
HALF_SECONDS = 45 * 60


@total_ordering
class MatchClock(BaseModel):
    """Period plus elapsed minute and second within that period's own numbering.

    `minute` is the on-screen minute: 0-45+ in the first half, 45-90+ in the second.
    """

    period: Literal[1, 2]
    minute: int = Field(ge=0, le=130)
    second: int = Field(ge=0, le=59)

    model_config = {"frozen": True}

    @model_validator(mode="before")
    @classmethod
    def _accept_text(cls, value: Any) -> Any:
        if isinstance(value, str):
            return cls.parse(value).model_dump()
        return value

    @model_validator(mode="after")
    def _minute_in_period(self) -> MatchClock:
        if self.period == 1 and self.minute > 60:
            raise ValueError("first-half minute cannot exceed 60")
        if self.period == 2 and self.minute < 45:
            raise ValueError("second-half minute cannot be below 45")
        return self

    @property
    def seconds_in_period(self) -> int:
        base = 0 if self.period == 1 else HALF_SECONDS
        return self.minute * 60 + self.second - base

    @property
    def sort_key(self) -> tuple[int, int]:
        return (self.period, self.seconds_in_period)

    @property
    def stoppage(self) -> bool:
        return (self.period == 1 and self.minute >= 45) or (self.period == 2 and self.minute >= 90)

    def __str__(self) -> str:
        if self.stoppage:
            base = 45 if self.period == 1 else 90
            return f"{base}+{self.minute - base}:{self.second:02d}"
        return f"{self.minute:02d}:{self.second:02d}"

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, MatchClock):
            return NotImplemented
        return self.sort_key < other.sort_key

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MatchClock):
            return NotImplemented
        return self.sort_key == other.sort_key

    def __hash__(self) -> int:
        return hash(self.sort_key)

    @classmethod
    def parse(cls, text: str) -> MatchClock:
        m = _CLOCK_RE.match(text.strip())
        if not m:
            raise ValueError(f"bad match clock {text!r}")
        base, extra, sec = int(m["base"]), m["extra"], int(m["sec"])
        if extra is not None:
            if base == 45:
                return cls(period=1, minute=45 + int(extra), second=sec)
            if base == 90:
                return cls(period=2, minute=90 + int(extra), second=sec)
            raise ValueError(f"stoppage must be 45+ or 90+, got {text!r}")
        return cls(period=1 if base < 45 else 2, minute=base, second=sec)


class Window(BaseModel):
    """Half-open match-clock window [start, end). Accepts "58:00-63:00"."""

    start: MatchClock
    end: MatchClock

    model_config = {"frozen": True}

    @model_validator(mode="before")
    @classmethod
    def _accept_text(cls, value: Any) -> Any:
        if isinstance(value, str):
            if "-" not in value:
                raise ValueError(f"bad window {value!r}")
            s, e = value.split("-", 1)
            return {"start": s, "end": e}
        return value

    @model_validator(mode="after")
    def _ordered(self) -> Window:
        if not self.start < self.end:
            raise ValueError(f"window start {self.start} must be before end {self.end}")
        return self

    def __str__(self) -> str:
        return f"{self.start}-{self.end}"

    def contains(self, clock: MatchClock) -> bool:
        return self.start <= clock < self.end
