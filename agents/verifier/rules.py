"""Support rules (spec §9.2, docs/support-rules.md): minimum samples and effect-size bands
per metric, from natural variation on the dev split only.

A band is the 90th percentile of the metric's absolute change from the first half over 40
dev matches with nothing planted, in the metric's threshold units, for 5- and 10-minute
windows. A change of at least one band is clear; of two bands, large.
"""

from contracts.taxonomy import Metric, SupportLevel

# (metric, subject level, window minutes) -> natural p90 of |change|
NATURAL_P90: dict[tuple[Metric, str, int], float] = {
    (Metric.PRESSURE_RATE, "team", 5): 0.204,
    (Metric.PRESSURE_RATE, "team", 10): 0.160,
    (Metric.LONG_BALL_SHARE, "team", 5): 0.145,
    (Metric.LONG_BALL_SHARE, "team", 10): 0.117,
    (Metric.SPRINT_COUNT, "team", 5): 0.491,
    (Metric.SPRINT_COUNT, "team", 10): 0.415,
    (Metric.SPRINT_COUNT, "unit", 5): 0.630,
    (Metric.SPRINT_COUNT, "unit", 10): 0.541,
    (Metric.SPRINT_COUNT, "player", 5): 1.000,
    (Metric.SPRINT_COUNT, "player", 10): 0.763,
    (Metric.SPRINT_SPEED, "team", 5): 1.666,
    (Metric.SPRINT_SPEED, "team", 10): 1.441,
    (Metric.SPRINT_SPEED, "unit", 5): 2.111,
    (Metric.SPRINT_SPEED, "unit", 10): 1.764,
    (Metric.SPRINT_SPEED, "player", 5): 2.693,
    (Metric.SPRINT_SPEED, "player", 10): 2.311,
    (Metric.CHANNEL_SHARE_LEFT, "team", 5): 0.348,
    (Metric.CHANNEL_SHARE_LEFT, "team", 10): 0.260,
    (Metric.CHANNEL_SHARE_CENTRE, "team", 5): 0.237,
    (Metric.CHANNEL_SHARE_CENTRE, "team", 10): 0.181,
    (Metric.CHANNEL_SHARE_RIGHT, "team", 5): 0.340,
    (Metric.CHANNEL_SHARE_RIGHT, "team", 10): 0.261,
}

# The sample a number rests on, at least: opponent actions in the zone, passes, sprints in
# the first half (a fall in sprints thins the window by design), sprints in the window, and
# on-ball actions for a channel share.
MIN_SAMPLE: dict[Metric, int] = {
    Metric.PRESSURE_RATE: 8,
    Metric.LONG_BALL_SHARE: 8,
    Metric.SPRINT_COUNT: 10,
    Metric.SPRINT_SPEED: 3,
    Metric.CHANNEL_SHARE_LEFT: 20,
    Metric.CHANNEL_SHARE_CENTRE: 20,
    Metric.CHANNEL_SHARE_RIGHT: 20,
}


def band(metric: Metric, level: str, window_minutes: float) -> float | None:
    return NATURAL_P90.get((metric, level, 5 if window_minutes <= 7.5 else 10))


def support(
    effect: float,
    metric: Metric,
    level: str,
    window_minutes: float,
    sample: int,
    weakened: bool,
    contradicted: bool,
) -> SupportLevel | None:
    """The support level for a primary cause's evidence, or None if it cannot be published."""
    p90, minimum = band(metric, level, window_minutes), MIN_SAMPLE.get(metric)
    if p90 is None or minimum is None or sample < minimum or contradicted:
        return None
    size = abs(effect)
    if size >= 2 * p90 and sample >= 2 * minimum and not weakened:
        return SupportLevel.STRONG
    if size >= p90 and sample >= 1.25 * minimum:
        return SupportLevel.MODERATE
    return SupportLevel.WEAK
