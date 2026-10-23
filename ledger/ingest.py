"""Turn feed messages into ledger documents and detector cases, a match at a time.

The detector judges each second-half minute once every event before it has arrived, as
batch detection does over a finished match, so streaming and batch open the same cases.
"""

from dataclasses import dataclass, field

from contracts.case import Case
from contracts.clock import MatchClock
from contracts.event import Event, EventType
from contracts.feed import FeedMessage
from detector.cusum import Detector
from ledger.store import Ledger, case_doc, event_doc, meta_doc

LAST_MINUTE = 90


@dataclass
class _Match:
    detector: Detector
    delivered: list[Event] = field(default_factory=list)
    next_minute: int = 46
    finished: bool = False


@dataclass
class Ingest:
    ledger: Ledger
    run_id: str
    matches: dict[str, _Match] = field(default_factory=dict)

    def take(self, batch: list[FeedMessage]) -> list[Case]:
        """Store one batch from the feed and return the cases it opened or added to."""
        opened: list[Case] = []
        events: dict[str, list[Event]] = {}
        for message in batch:
            if message.run_id != self.run_id:
                continue  # left on the hub by an earlier run
            if message.kind == "meta":
                self.matches[message.match_id] = _Match(Detector(message.meta))
                self.ledger.put("events", message.match_id, [meta_doc(message.meta)])
                continue
            match = self.matches.get(message.match_id)
            if match is None:
                raise ValueError(f"{message.match_id}: an event arrived before its metadata")
            opened += self._advance(match, message.event.clock, message.event)
            match.delivered.append(message.event)
            events.setdefault(message.match_id, []).append(message.event)
        for match_id, stored in events.items():
            self.ledger.put("events", match_id, [event_doc(e) for e in stored])
        unique = list({id(c): c for c in opened}.values())
        for case in unique:
            self.ledger.put("cases", case.match_id, [case_doc(case)])
        return unique

    def _advance(self, match: _Match, clock: MatchClock, event: Event) -> list[Case]:
        """Judge every minute this event's clock has passed, before it counts."""
        if event.type == EventType.PERIOD_END and clock.period == 2:
            match.finished = True
            last = LAST_MINUTE
        elif clock.period == 2:
            last = min(clock.minute, LAST_MINUTE)
        else:
            return []
        opened: list[Case] = []
        while match.next_minute <= last:
            minute = match.next_minute
            before = [e for e in match.delivered if e.clock < _minute(minute)]
            opened += match.detector.tick(before, minute)
            match.next_minute += 1
        return opened

    def finished(self, match_id: str) -> bool:
        match = self.matches.get(match_id)
        return match is not None and match.finished


def _minute(minute: int) -> MatchClock:
    return MatchClock(period=2, minute=minute, second=0)
