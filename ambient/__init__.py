"""The Ambient Layer (spec 8.2): always-on, deterministic context so the fan view is never
empty.

Pure functions over a match's delivered events (`contracts.event.Event`, coordinates in
the acting team's attacking frame). No model call, no randomness, no engine import; the
same events always give the same feed. The definitions live with their functions:

- `ambient.tags`: sprint and shot speed tags, pass difficulty and its badges.
- `ambient.strips`: the momentum strip and the control-vs-chaos gauge.
- `ambient.ticker`: localized one-liners from the templates in `ambient/i18n/`.

`build_feed` bundles them as the `contracts.ambient.AmbientFeed` that surfaces format.
"""

from ambient import strips, tags
from ambient.ticker import ticker
from contracts.ambient import AmbientFeed, AmbientRules
from contracts.event import Event
from contracts.meta import MatchMeta

RULES = AmbientRules(
    sprint_kmh=tags.SPRINT_TAG_KMH,
    shot_kmh=tags.SHOT_TAG_KMH,
    badge_difficulty=tags.BADGE_DIFFICULTY,
    momentum_half_life_min=strips.HALF_LIFE_MIN,
    control_window_min=strips.CONTROL_WINDOW_MIN,
    control_min_actions=strips.CONTROL_MIN_ACTIONS,
)


def build_feed(events: list[Event], meta: MatchMeta) -> AmbientFeed:
    """The whole ambient feed for one match's delivered events."""
    if any(e.match_id != meta.match_id for e in events):
        raise ValueError("events belong to a different match")
    home, away = meta.teams["home"].name, meta.teams["away"].name
    ordered = sorted(events, key=lambda e: e.clock.sort_key)
    badges = tags.pass_badges(ordered)
    return AmbientFeed(
        match_id=meta.match_id,
        home=home,
        away=away,
        rules=RULES,
        speed_tags=tags.speed_tags(ordered),
        pass_badges=badges,
        momentum=strips.momentum(ordered, home, away),
        control=strips.control(ordered),
        ticker=ticker(ordered, meta, badges),
    )
