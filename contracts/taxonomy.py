"""Cause taxonomy, support and language levels, lifecycle states, shared enums.

Scripts in `engine/` never use these names; only the sealed ground-truth
mapping (readable by `eval/` alone) links a script to a cause class.
"""

from enum import StrEnum


class Cause(StrEnum):
    # Tactical
    PRESS_INTENSITY_UP = "tactical.press_intensity_up"
    PRESS_INTENSITY_DOWN = "tactical.press_intensity_down"
    BLOCK_DEEPER = "tactical.block_deeper"
    BLOCK_HIGHER = "tactical.block_higher"
    FORMATION_CHANGE = "tactical.formation_change"
    FLANK_OVERLOAD = "tactical.flank_overload"
    # Physical
    UNIT_FATIGUE = "physical.unit_fatigue"
    PLAYER_FATIGUE = "physical.player_fatigue"
    FRESH_LEGS_SUBSTITUTION = "physical.fresh_legs_substitution"
    # Game state
    PROTECTING_LEAD = "game_state.protecting_lead"
    CHASING_RESULT = "game_state.chasing_result"
    NUMERICAL_CHANGE = "game_state.numerical_change"
    # Fallback
    OTHER = "other"
    NONE = "none"

    @property
    def domain(self) -> str:
        return self.value.split(".", 1)[0] if "." in self.value else "fallback"


class AgentRole(StrEnum):
    TACTICS = "tactics"
    PHYSICAL = "physical"
    GAME_STATE = "game_state"
    SYNTHESIS = "synthesis"


DOMAIN_OF_AGENT: dict[AgentRole, str] = {
    AgentRole.TACTICS: "tactical",
    AgentRole.PHYSICAL: "physical",
    AgentRole.GAME_STATE: "game_state",
}


class SupportLevel(StrEnum):
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"


class LanguageLevel(StrEnum):
    ASSERTIVE = "assertive"
    MEASURED = "measured"
    TENTATIVE = "tentative"


LANGUAGE_FOR_SUPPORT: dict[SupportLevel, LanguageLevel] = {
    SupportLevel.STRONG: LanguageLevel.ASSERTIVE,
    SupportLevel.MODERATE: LanguageLevel.MEASURED,
    SupportLevel.WEAK: LanguageLevel.TENTATIVE,
}


class CardStatus(StrEnum):
    PROPOSED = "proposed"
    INVESTIGATING = "investigating"
    CROSS_EXAMINED = "cross_examined"
    VERIFIED = "verified"
    REJECTED = "rejected"
    SCHEDULED = "scheduled"
    SHOWN = "shown"
    EXPIRED = "expired"
    KILLED = "killed"
    REVISED = "revised"
    WITHDRAWN = "withdrawn"


class CaseOutcome(StrEnum):
    """What the investigation concluded. Drives which card variant renders."""

    EXPLAINED = "explained"  # at least one cause in the taxonomy survived
    OTHER = "other"  # a real effect with no fitting class
    NONE = "none"  # no clear cause; normal variation


class MomentType(StrEnum):
    PRESSURE_SHIFT = "pressure_shift"
    MOMENTUM_SWING = "momentum_swing"
    CONTROL_TO_CHAOS = "control_to_chaos"
    CHAOS_TO_CONTROL = "chaos_to_control"
    SHAPE_CHANGE = "shape_change"
    FATIGUE_SIGNAL = "fatigue_signal"
    INDIVIDUAL_SPIKE = "individual_spike"
    MILESTONE = "milestone"
    KEY_EVENT = "key_event"


class Metric(StrEnum):
    PPDA = "ppda"
    PRESS_INTENSITY = "press_intensity"
    LONG_BALL_SHARE = "long_ball_share"
    FIELD_TILT = "field_tilt"
    PASS_ACCURACY = "pass_accuracy"
    PASS_ACCURACY_UNDER_PRESSURE = "pass_accuracy_under_pressure"
    PASS_DIFFICULTY = "pass_difficulty"
    XG = "xg"
    SPRINT_COUNT = "sprint_count"
    HIGH_INTENSITY_RUN_RATE = "high_intensity_run_rate"
    MOMENTUM = "momentum"
    CONTROL_CHAOS = "control_chaos"
    RHYTHM = "rhythm"
    LINE_HEIGHT = "line_height"
    BALL_SPEED = "ball_speed"
    SHOT_SPEED = "shot_speed"
    # Stretch
    POSSESSION_SHARE = "possession_share"
    DISTANCE_COVERED = "distance_covered"


class ThresholdKind(StrEnum):
    """How a predicted change is measured against its baseline.

    RELATIVE: |value - baseline| / |baseline|; only for ratios and counts
    with a baseline well above zero.
    ABSOLUTE: |value - baseline| in the metric's own units.
    SIGMA: |value - baseline| / std from the `distribution` tool; the default
    for signed or near-zero metrics such as momentum.
    """

    RELATIVE = "relative"
    ABSOLUTE = "absolute"
    SIGMA = "sigma"


DEFAULT_THRESHOLD_KIND: dict[Metric, ThresholdKind] = {
    Metric.PPDA: ThresholdKind.RELATIVE,
    Metric.PRESS_INTENSITY: ThresholdKind.RELATIVE,
    Metric.LONG_BALL_SHARE: ThresholdKind.ABSOLUTE,
    Metric.FIELD_TILT: ThresholdKind.ABSOLUTE,
    Metric.PASS_ACCURACY: ThresholdKind.ABSOLUTE,
    Metric.PASS_ACCURACY_UNDER_PRESSURE: ThresholdKind.ABSOLUTE,
    Metric.PASS_DIFFICULTY: ThresholdKind.ABSOLUTE,
    Metric.XG: ThresholdKind.SIGMA,
    Metric.SPRINT_COUNT: ThresholdKind.RELATIVE,
    Metric.HIGH_INTENSITY_RUN_RATE: ThresholdKind.RELATIVE,
    Metric.MOMENTUM: ThresholdKind.SIGMA,
    Metric.CONTROL_CHAOS: ThresholdKind.SIGMA,
    Metric.RHYTHM: ThresholdKind.RELATIVE,
    Metric.LINE_HEIGHT: ThresholdKind.ABSOLUTE,
    Metric.BALL_SPEED: ThresholdKind.RELATIVE,
    Metric.SHOT_SPEED: ThresholdKind.RELATIVE,
    Metric.POSSESSION_SHARE: ThresholdKind.ABSOLUTE,
    Metric.DISTANCE_COVERED: ThresholdKind.RELATIVE,
}


class BaselineScope(StrEnum):
    FIRST_HALF = "first_half"
    MATCH_SO_FAR = "match_so_far"
    SEASON_AVERAGE = "season_average"  # read from state/season_baselines.json


class OverlayTemplate(StrEnum):
    PLAYER_NAME_TAG = "player_name_tag"
    SPEED_DISTANCE_TAG = "speed_distance_tag"
    SHOT_SPEED = "shot_speed"
    PASS_DIFFICULTY = "pass_difficulty"
    PRESSURE_SHIFT_BAR = "pressure_shift_bar"
    MOMENTUM_STRIP = "momentum_strip"
    CONTROL_CHAOS_GAUGE = "control_chaos_gauge"
    SHAPE_CHANGE = "shape_change"
    FATIGUE_WARNING = "fatigue_warning"
    MILESTONE_BADGE = "milestone_badge"
    UPDATE_BANNER = "update_banner"
    WITHDRAWAL_BANNER = "withdrawal_banner"
