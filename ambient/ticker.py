"""The event ticker: templated, localized one-liners, never model text.

Templates live in `ambient/i18n/<locale>.json`, and every locale must have every key.
The ticker writes a line for kick-off, each goal (with the score after it), each shot that
did not score (with its speed, rounded to whole km/h), fouls, free kicks, cards,
substitutions, half-time, the start of the second half, full time, and each standout pass
from `ambient.tags.pass_badges`. Throw-ins, goal kicks and the kick-offs after goals are
left out: they are too frequent to be news.

Minutes are football minutes: an event at 66:49 is in the 67th minute, written 67', and
stoppage reads 45+2' or 90+3'.
"""

import json
from functools import cache
from pathlib import Path

from contracts.ambient import LocalizedText, PassBadge, TickerLine
from contracts.clock import MatchClock
from contracts.event import Event, EventType, Outcome
from contracts.meta import MatchMeta

LOCALES = ("en", "es")
I18N = Path(__file__).resolve().parent / "i18n"
# Lines about the match as a whole name no team.
MATCH_LINES = {"kick_off", "second_half", "half_time", "full_time"}


@cache
def templates() -> dict[str, dict[str, str]]:
    """Every locale's templates; a key missing from any locale is an error."""
    loaded = {
        locale: json.loads((I18N / f"{locale}.json").read_text(encoding="utf-8"))
        for locale in LOCALES
    }
    keys = set(loaded[LOCALES[0]])
    for locale, table in loaded.items():
        if set(table) != keys:
            raise ValueError(f"ambient/i18n/{locale}.json does not have every template")
    return loaded


def football_minute(clock: MatchClock, locale: str) -> str:
    """66:49 is 67'; a minute past the half's 45 or 90 is stoppage, 45+2'."""
    table = templates()[locale]
    shown = clock.minute + 1
    base = 45 if clock.period == 1 else 90
    if shown > base:
        return table["stoppage"].format(base=base, extra=shown - base)
    return table["minute"].format(minute=shown)


def _text(key: str, clock: MatchClock, **values) -> LocalizedText:
    return LocalizedText(
        **{
            locale: templates()[locale][key].format(minute=football_minute(clock, locale), **values)
            for locale in LOCALES
        }
    )


def ticker(
    events: list[Event], meta: MatchMeta, badges: list[PassBadge] | None = None
) -> list[TickerLine]:
    """The ticker for `events` in feed order; each badge sits at its own pass."""
    home, away = meta.teams["home"].name, meta.teams["away"].name
    names = {p.player_id: p.name for team in meta.teams.values() for p in team.players}
    score = {home: 0, away: 0}
    badge_at = {b.event_id: b for b in badges or []}
    lines: list[TickerLine] = []

    def add(e: Event, kind: str, key: str | None = None, **values) -> None:
        player = names.get(e.player_id, e.player_id) if e.player_id else e.team
        values |= dict(home=home, away=away, team=e.team, player=player)
        values |= dict(home_score=score[home], away_score=score[away])
        text = _text(key or kind, e.clock, **values)
        team = None if kind in MATCH_LINES else e.team
        lines.append(TickerLine(event_id=e.event_id, at=e.clock, kind=kind, team=team, text=text))

    for e in events:
        if e.type == EventType.PERIOD_START:
            add(e, "kick_off" if e.clock.period == 1 else "second_half")
        elif e.type == EventType.PERIOD_END:
            add(e, "half_time" if e.clock.period == 1 else "full_time")
        elif e.type == EventType.GOAL:
            score[e.team] = score.get(e.team, 0) + 1
            add(e, "goal")
        elif e.type == EventType.SHOT and e.outcome != Outcome.GOAL:
            key = f"shot.{e.outcome.value}"
            key = key if key in templates()["en"] else "shot"
            add(e, "shot", key, speed=round(e.shot_q.shot_speed_kmh))
        elif e.type == EventType.FOUL:
            add(e, "foul")
        elif e.type == EventType.SET_PIECE and e.qualifiers.get("kind") == "free_kick":
            add(e, "free_kick")
        elif e.type == EventType.CARD:
            add(e, "card")
        elif e.type == EventType.SUBSTITUTION:
            add(e, "substitution")
        elif e.event_id in badge_at:
            add(e, "pass_badge", difficulty=badge_at[e.event_id].difficulty)
    return lines
