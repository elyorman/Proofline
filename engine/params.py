"""Team and player parameter values at any match time, with linear ramps."""

from contracts.clock import MatchClock
from engine.script import Intervention, MatchScript, Side

PLAYER_DEFAULTS = {"stamina_decay": 1.0}


def _progress(start: MatchClock, ramp_s: int, period: int, s: float) -> float:
    """0 before the intervention starts, then linear to 1 over the ramp."""
    if period != start.period:
        return 1.0 if period > start.period else 0.0
    elapsed = s - start.seconds_in_period
    if elapsed < 0:
        return 0.0
    return 1.0 if ramp_s == 0 else min(1.0, elapsed / ramp_s)


class ParamTimeline:
    """Values at (period, s), where s is seconds since that period's kick-off.

    That is `MatchClock.seconds_in_period`, not minute * 60: 60:00 is (2, 900).
    """

    def __init__(self, script: MatchScript) -> None:
        self._base = {
            side: {"press_height": t.press_height, "directness": t.directness, "quality": t.quality}
            for side, t in script.teams.items()
        }
        self._interventions = sorted(script.scripts, key=lambda iv: iv.at.sort_key)
        # When each intervention started: its `at`, or, for a score-triggered one, the
        # moment the simulator saw its condition hold (None until then).
        self.started: dict[str, MatchClock | None] = {
            iv.id: None if iv.when else iv.at for iv in self._interventions
        }

    def pending(self) -> list[Intervention]:
        """Score-triggered interventions that have not started yet."""
        return [iv for iv in self._interventions if self.started[iv.id] is None]

    def start(self, iv: Intervention, at: MatchClock) -> None:
        self.started[iv.id] = at

    def _active(self) -> list[Intervention]:
        """Started interventions in the order they started, so a later start wins."""
        started = [iv for iv in self._interventions if self.started[iv.id] is not None]
        return sorted(started, key=lambda iv: self.started[iv.id].sort_key)

    def team(self, side: Side, period: int, s: float) -> dict[str, float]:
        values = dict(self._base[side])
        for iv in self._active():
            if iv.team == side and iv.player is None and iv.unit is None:
                self._apply(values, iv, period, s)
        return values

    def player(
        self, side: Side, player_id: str, period: int, s: float, unit: str | None = None
    ) -> dict[str, float]:
        values = dict(PLAYER_DEFAULTS)
        for iv in self._active():
            if iv.team == side and (iv.player == player_id or (unit and iv.unit == unit)):
                self._apply(values, iv, period, s)
        return values

    def _apply(self, values: dict[str, float], iv: Intervention, period: int, s: float) -> None:
        p = _progress(self.started[iv.id], iv.ramp_seconds, period, s)
        for key, target in iv.set.items():
            values[key] += (target - values[key]) * p
