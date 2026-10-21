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

    def team(self, side: Side, period: int, s: float) -> dict[str, float]:
        values = dict(self._base[side])
        for iv in self._interventions:
            if iv.team == side and iv.player is None:
                _apply(values, iv, period, s)
        return values

    def player(self, side: Side, player_id: str, period: int, s: float) -> dict[str, float]:
        values = dict(PLAYER_DEFAULTS)
        for iv in self._interventions:
            if iv.team == side and iv.player == player_id:
                _apply(values, iv, period, s)
        return values


def _apply(values: dict[str, float], iv: Intervention, period: int, s: float) -> None:
    p = _progress(iv.at, iv.ramp_seconds, period, s)
    for key, target in iv.set.items():
        values[key] += (target - values[key]) * p
