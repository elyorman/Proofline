# Planted Signal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Status:** executed on branch `planted-signal` in October 2026, with a spec review and a code-quality review after every task. The code blocks show each task as dispatched; the fixes listed under "Review fixes during execution" changed the code after the task named. Do not re-run it; later plans pick up the follow-ups at the end.

**Goal:** Make each planted story in the demo match visible to a detector that watches one match, prove it with a single-match visibility test on held-out seeds, and choose the demo seed by a stated rule.

**Architecture:** A new `engine/visibility.py` measures a story's in-match change (detection window against the same match's first half) against the change the same observable shows without the story, in natural standard deviations. A new `engine/amend.py` derives the feed as first delivered, so the 55' flank card's v1 view can be measured. The simulator stops piling play onto the touchlines and gains one mechanism (long balls to bypass a high press); m01's scripts are retimed and strengthened, and its fatigue script is dropped because no single match can show it.

**Tech Stack:** Python 3.12, pydantic v2 (existing contracts), PyYAML, pytest, ruff, uv. No new dependency.

---

## Where this plan sits

The Match Engine core (`docs/plans/2026-10-21-match-engine-core.md`) is merged at `a33ab94`. Its final review and an external review agree: the engine works, but the demo match's planted story is not visible in a single match. Gate 2 needs the detector to fire on the planted moment; the demo needs a verified 63' card and a real correction beat. This plan runs before the rest of plan 2 (paired-run tooling, suites with sealed ground truth, the realism report, the dataset release).

Every number below was measured on a scratch copy of the repo built task by task from `a33ab94`, with the full suite green after each task. Constants were tuned on seeds 0–79; every reported number uses held-out seeds 100–139.

## Design decisions (review these)

- **Visibility in one match.** For an observable and a detection window, a match's *change* is the observable over the window minus its value over the same match's first half: what a detector with per-half baselines sees. The *natural change* is the same quantity without the story (the same seed with the intervention removed or, for a feed error, the corrected events). *Separation* is the mean story change minus the mean natural change, in natural standard deviations; a match *clears* when its own change is at least two natural standard deviations above the mean natural change. A paired-run CI clear of zero is not enough: s2 had one (−0.93 sprints, CI [−1.21, −0.64]) at a separation of only 0.40.
- **The press story.** s1 started at 60:00 with a 3-minute ramp while the card's window is 58–63', so the window saw about a quarter of the change. It now starts at 56:00 with a 2-minute ramp and reaches full height at 58:00. Harbour City start in a mid-block (press 0.30, was 0.45) and switch to a high press (0.90, was 0.75), a larger change of the kind a card at 63' would describe. One new mechanism, `BYPASS`: facing a press above 0.5, a team goes long more often from its own 70 m even when nobody presses the passer (+0.4 long-ball chance at a 0.9 press). On the tuning seeds Northvale's long-ball share separates by 2.7 without it and 5.2 with it.
- **PPDA cannot carry the press over five minutes.** Its natural change has a standard deviation of about 6.7 in a 5-minute window (a ratio over 4–8 defensive actions), so its separation stays near −0.5 whatever the press does. Pressure rate per opponent action and long-ball share carry the story; the 63' card's PPDA proposition is a follow-up for the State Builder plan.
- **Touchlines.** Clamping y put 17% of on-ball actions exactly on a touchline. Open play now reflects off the touchlines and the passer's own goal line, and a misplaced pass ending within 8 m of a touchline runs out for a throw-in: its end moves onto the line and the opponent throws in from the same spot. This keeps throw-ins realistic (42.5 a match) and spreads play across the width. Shot choice (0.05 → 0.035) and the xG intercept (−0.65 → −0.75) are retuned on seeds 0–79 to hold goals near 2.8. A pull towards the middle was tried and rejected: any pull strong enough to cut throw-ins to a realistic count left the 18 m strips along each touchline with about 19% of on-ball actions each, against 26% under a flat spread.
- **The flank story.** a1 selected 2.3 events per match. It now selects every Northvale pass, carry and dribble from 45:00–55:00 whose true start and end lie in y 0–46, and the feed first showed them 22 m to the right (about 55 events per match, never fewer than 17). Channels are equal thirds of the width in the acting team's frame (right: y > 45.33), defined in spec §8.1 by this plan. The flank story is weaker by nature: consecutive actions stay on one side (lag-1 autocorrelation 0.63), so a 10-minute channel share has a natural standard deviation of about 0.165, and any lateral shift can move at most about a third of the events into the right channel. It separates by 1.84 and clears in half the held-out matches. That is enough because a1 is a correction-suite story, not a planted cause, and the demo-seed rule guarantees the demo match shows it.
- **Fatigue is no longer planted in m01.** One player's sprint count cannot show fatigue in a single match: on seeds 0–79, over 70–90', a striker's separation is 0.93 at a 5× stamina decay, 1.65 at 10× and 2.06 at 20×, where the player barely sprints at all. Mean sprint speed would work (−3.3 at 10×), but it needs an observable the State Builder does not have and a decay at the edge of plausibility. The stamina mechanism stays, tested on a test-only script. Physical causes for the planted suite are designed with tracking (`player_load`) and held to the same visibility bar.
- **The demo-seed rule.** m01's seed is the first from 4417 upwards on which, in that one match, every observable in `DATASET.md`'s table changes by at least its held-out median and clears two natural standard deviations, and the corrected right-channel change does not clear them (the exact wording is in `DATASET.md`). It picks **4434**. About one held-out match in seven meets the rule, so the demo match is a clear instance, not a typical one, and no reported number comes from it. The rule is stated in the script, `DATASET.md`, the spec and the README, and a test fails if the script's seed is not the one it picks.
- **Observability in the spec (review this one).** Spec §7.2 marked a script `not_observable` only when its paired CI includes zero. This plan adds a second rule: no observable of the script's class separates by two natural standard deviations in its own direction. Separation belongs to the script (paired-run seeds, the ground truth's observable window), never to an evaluated match, flags freeze before either variant runs, and the scoreboard lists every exclusion with all-script recall beside the headline. Without it, a script like the old s2 counts against recall although no single-match method could find it; with it stated loosely, an implementer could drop the detector's misses and inflate recall, which is why review tightened the wording twice.
- **Amendment filters list types and shift laterally only.** `AmendmentFilter.type` becomes `types` (passes, carries and dribbles; the only events with a ball path to relocate). `AmendmentSpec` rejects a non-zero `dx_m` and a zero or non-finite `dy_m`, so every displaced event stays on the pitch and every amendment moves something.

## Measured on held-out seeds 100–139

Realism, with no scripts:

| Measure | `a33ab94` | After this plan | Typical top flight |
|---|---|---|---|
| Passes per team | 495 | 498 | ~450–550 |
| Pass completion | 80.0% | 80.4% | ~78–85% |
| Shots per team | 13.3 | 13.8 | ~12–14 |
| Goals per match | 2.83 | 2.80 | ~2.7–2.9 |
| Mean shot distance | 18.3 m | 18.0 m | ~16–18 m |
| Throw-ins per match | 43.4 | 42.5 | ~40–50 |
| On-ball actions exactly on a touchline | 17.4% | 3.3% (throw-ins, taken there) | — |
| Busiest 2 m strip of the width | 10.3% | 5.2% | — |
| Left / centre / right thirds of the width | 33.7 / 31.4 / 34.9% | 31.9 / 35.7 / 32.4% | — |
| Long-ball share | 13.6% | 13.6% | ~10–15% |

Visibility in one match (separation in natural standard deviations; share of held-out matches that clear two):

| Story | Observable | Window | `a33ab94` | After this plan |
|---|---|---|---|---|
| s1 | Harbour City pressures per Northvale action in Northvale's first 60% | 58–63' | 0.42 (10%) | 3.26 (82%) |
| s1 | Northvale's share of passes over 30 m | 58–63' | 0.21 (10%) | 5.09 (85%) |
| a1 | Northvale's right-channel share as first delivered | 48–55', then 45–55' | 0.27 (5%) | 1.84 (50%) |
| s2 | NV-03 sprints | 75–90' | 0.40 (3%) | not planted |

Events a1 corrects: 2.3 per match (minimum 0) before, 54.6 (minimum 17) after.

Paired runs on seeds 0–19 (`tests/test_engine_mechanisms.py`), 95% CIs after this plan: Harbour City pressure rate 62–68' [+0.26, +0.38]; Northvale long-ball share [+0.24, +0.37]; long-ball share of Northvale passes nobody pressed, 62–90' [+0.29, +0.40] (over 62–68' before `BYPASS`: [−0.06, +0.01]); NV-03 sprints under the test-only fatigue script [−1.02, −0.38].

The demo match: `m01 seed 4434: 2963 events, Harbour City 2-3 Northvale`. Harbour City's pressure rate goes from 0.32 in the first half to 0.83 in 58–63'; Northvale's long-ball share from 11% to 59%. Northvale's right-channel share is 24% in the first half and 62% in 45–55' as first delivered, 38% once a1 corrects 54 events. Northvale lead 3-1 when the press rises (goals at 0:55 HC, 12:30, 26:51 and 52:54 NV, 77:09 HC), which fits the spec card's secondary cause.

---

## File structure

| File | Change | Responsibility |
|---|---|---|
| `engine/script.py` | Modify | `AmendmentFilter.types`; lateral, finite shifts only |
| `engine/amend.py` | Create | Events each amendment corrects; the feed as first delivered |
| `engine/visibility.py` | Create | Observables, in-match change, separation, clears |
| `engine/sim.py` | Modify | Touchline reflection, throw-ins from misplaced passes, `BYPASS`, recalibration |
| `engine/scripts/planted/m01.yaml` | Modify | Retimed, stronger s1; s2 removed; wider a1; seed 4434 |
| `tests/test_engine_script.py` | Modify | New filter shape, rejections, demo script |
| `tests/test_engine_amend.py` | Create | Selection and first-delivered unit tests |
| `tests/test_engine_visibility.py` | Create | Observable and statistic unit tests |
| `tests/test_engine_planted_signal.py` | Create | m01 stories visible in one match; the demo-seed rule |
| `tests/test_engine_sim.py` | Modify | Throw-in test; before-intervention test without s2 |
| `tests/test_engine_realism.py` | Modify | Width spread and throw-in bands |
| `tests/test_engine_mechanisms.py` | Modify | Bypass test; fatigue on a test-only script |
| `tests/test_engine_cli.py` | Modify | Golden pin of the demo match |
| `docs/spec.md` | Modify | §7.1 example and sequence, §7.2 observability, §8.1 channel share, §11.1, §19 |
| `docs/demo-script.md` | Modify | Correction beat wording |
| `DATASET.md` | Create | Demo match, seed rule, visibility statistic |
| `README.md`, `CLAUDE.md` | Modify | `DATASET.md` row; generate command without `--seed` |
| `docs/plans/2026-10-21-match-engine-core.md` | Modify | Mark the follow-ups this plan resolves |

Commands used throughout (from the repo root):

```bash
uv run pytest -q                                     # whole suite (about 40 s after Task 7)
uv run ruff check . && uv run ruff format --check .
uv run python scripts/check_engine_isolation.py
```

Commits follow `CLAUDE.md`: one concern each, imperative subject, a body that says why, and no `Co-Authored-By` or other attribution trailers.

---

### Task 1: Let amendment filters list event types

**Files:**
- Modify: `engine/script.py`
- Modify: `engine/scripts/planted/m01.yaml:28`
- Modify: `docs/spec.md` (the `filter:` line of the §7.1 YAML example)
- Test: `tests/test_engine_script.py`

- [ ] **Step 1: Write the failing tests**

In `tests/test_engine_script.py`, replace the `_amendment` helper with:

```python
def _amendment(at="68:00", dy=-22, dx=0.0, **band):
    batch_filter = {"types": ["pass", "carry"], "team": "away", "window": "45:00-55:00"}
    batch_filter |= {"y_min": 0, "y_max": 46, **band}
    shift = {"dx_m": dx, "dy_m": dy}
    return {"id": "a1", "at": at, "batch": {"filter": batch_filter, "shift": shift}, "reason": "r"}
```

and replace the parameter list of `test_incoherent_amendments_are_rejected` with:

```python
@pytest.mark.parametrize(
    "amendment,message",
    [
        (_amendment(types=["carries"]), "Input should be"),
        (_amendment(types=[]), "at least 1 item"),
        (_amendment(types=["shot"]), "relocate carry, dribble, pass events only"),
        (_amendment(y_min=50, y_max=32), "above y_max"),
        (_amendment(at="50:00"), "before its window ends"),
        (_amendment(y_max=48), "leaves the pitch"),
        (_amendment(dx=3.0), "lateral only"),
        (_amendment(dy=float("nan")), "lateral only"),
    ],
)
```

Leave `test_demo_script_loads` and `test_unquoted_yaml_time_is_rejected` as they are; Task 6 changes them.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_engine_script.py -q`
Expected: `8 failed, 9 passed`; every `test_incoherent_amendments_are_rejected` case fails because the filter has no `types` field.

- [ ] **Step 3: Implement**

In `engine/script.py`, add `import math` above `import re`, and below the `PLAYER_ID` line add:

```python
AMENDABLE = frozenset({EventType.PASS, EventType.CARRY, EventType.DRIBBLE})
```

Replace the `AmendmentFilter` class with:

```python
class AmendmentFilter(BaseModel):
    """Events whose true start and end both lie in [y_min, y_max]; v1 shows them displaced."""

    model_config = ConfigDict(extra="forbid")

    types: list[EventType] = Field(min_length=1)
    team: Side
    window: Window
    y_min: float = Field(default=0, ge=0, le=68)
    y_max: float = Field(default=68, ge=0, le=68)

    @model_validator(mode="after")
    def _band(self) -> "AmendmentFilter":
        if not set(self.types) <= AMENDABLE:
            raise ValueError(f"amendments relocate {', '.join(sorted(AMENDABLE))} events only")
        if self.y_min > self.y_max:
            raise ValueError(f"y_min {self.y_min} is above y_max {self.y_max}")
        return self
```

In `AmendmentSpec._coherent`, directly after `band, dy = self.batch.filter, self.batch.shift.dy_m`, add:

```python
        if self.batch.shift.dx_m != 0 or not math.isfinite(dy):
            raise ValueError(f"{self.id}: shifts are lateral only: a finite dy_m and no dx_m")
```

In `engine/scripts/planted/m01.yaml`, and in the same line of the YAML example in `docs/spec.md` §7.1, change `filter: { type: carry, ...` to `filter: { types: [carry], ...` (nothing else on the line changes).

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest -q && uv run ruff check . && uv run ruff format --check .`
Expected: all tests pass; ruff clean.

- [ ] **Step 5: Commit**

```bash
git add engine/script.py engine/scripts/planted/m01.yaml docs/spec.md tests/test_engine_script.py
git commit -m "Let amendment filters list event types" -m "A provider re-sync moves every kind of on-ball event, not only carries, so an amendment can now relocate passes, carries and dribbles together. Shifts are lateral and finite only, which keeps every displaced event on the pitch."
```

---

### Task 2: Derive the feed as first delivered

**Files:**
- Create: `engine/amend.py`
- Test: `tests/test_engine_amend.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_engine_amend.py`:

```python
import pytest

from contracts.event import Event, Point
from engine.amend import corrected_by, first_delivered
from engine.script import MatchScript

SCRIPT = MatchScript.model_validate(
    {
        "match_id": "t01",
        "seed": 1,
        "teams": {
            "home": {"name": "Harbour City", "code": "HC"},
            "away": {"name": "Northvale", "code": "NV"},
        },
        "amendments": [
            {
                "id": "a1",
                "at": "68:00",
                "batch": {
                    "filter": {
                        "types": ["pass", "carry"],
                        "team": "away",
                        "window": "45:00-55:00",
                        "y_min": 0,
                        "y_max": 46,
                    },
                    "shift": {"dy_m": -22},
                },
                "reason": "provider coordinate recalibration",
            }
        ],
    }
)
A1 = SCRIPT.amendments[0]


def _carry(event_id, clock="50:00", team="Northvale", y0=30.0, y1=40.0, type_="carry"):
    return Event(
        event_id=event_id,
        match_id="t01",
        clock=clock,
        wall_clock_ms=0,
        type=type_,
        team=team,
        start=Point(x=50, y=y0),
        end=Point(x=55, y=y1),
    )


def test_selects_by_type_team_window_and_true_position():
    events = [
        _carry("in"),
        _carry("ends-outside-the-band", y1=46.1),
        _carry("other-team", team="Harbour City"),
        _carry("first-half", clock="44:59"),
        _carry("window-end", clock="55:00"),  # windows are half-open
        _carry("not-a-listed-type", type_="dribble"),
    ]
    assert corrected_by(A1, "Northvale", events) == ["in"]


def test_first_delivered_shows_corrected_events_displaced():
    events = [_carry("in", y0=30.0, y1=46.0), _carry("other-team", team="Harbour City")]
    delivered, corrected = first_delivered(SCRIPT, events)
    assert corrected == {"a1": ["in"]}
    assert (delivered[0].start.y, delivered[0].end.y) == (52.0, 68.0)  # 22 m to the right
    unchanged = {"start", "end"}
    assert delivered[0].model_dump(exclude=unchanged) == events[0].model_dump(exclude=unchanged)
    assert delivered[1] is events[1]


def test_overlapping_amendments_are_refused():
    twice = SCRIPT.model_copy(update={"amendments": [A1, A1.model_copy(update={"id": "a2"})]})
    with pytest.raises(ValueError, match="a2 corrects events already amended"):
        first_delivered(twice, [_carry("in")])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_engine_amend.py -q`
Expected: collection error, `ModuleNotFoundError: No module named 'engine.amend'`.

- [ ] **Step 3: Implement**

Create `engine/amend.py`:

```python
"""What the feed first delivered, and which events each amendment corrects (spec §7.1).

The simulator produces the truth. An amendment's filter selects events by their true
position; the provider first showed them displaced by the opposite of the correcting
shift, and the batch at the amendment's `at` moves them back.
"""

from contracts.event import Event, Point
from engine.script import AmendmentSpec, MatchScript


def corrected_by(amendment: AmendmentSpec, team: str, events: list[Event]) -> list[str]:
    """Ids of the events `amendment` relocates: its types, team and window, with the
    true start and end both inside its y band."""
    f = amendment.batch.filter
    return [
        e.event_id
        for e in events
        if e.type in f.types
        and e.team == team
        and f.window.contains(e.clock)
        and f.y_min <= e.start.y <= f.y_max
        and f.y_min <= e.end.y <= f.y_max
    ]


def first_delivered(
    script: MatchScript, events: list[Event]
) -> tuple[list[Event], dict[str, list[str]]]:
    """The events as the feed first showed them, and the ids each amendment corrects."""
    corrected: dict[str, list[str]] = {}
    dy_of: dict[str, float] = {}
    for amendment in script.amendments:
        team = script.teams[amendment.batch.filter.team].name
        ids = corrected_by(amendment, team, events)
        overlap = dy_of.keys() & ids
        if overlap:
            raise ValueError(f"{amendment.id} corrects events already amended: {sorted(overlap)}")
        corrected[amendment.id] = ids
        dy_of |= dict.fromkeys(ids, amendment.batch.shift.dy_m)
    delivered = [
        e.model_copy(
            update={
                "start": Point(x=e.start.x, y=round(e.start.y - dy_of[e.event_id], 1)),
                "end": Point(x=e.end.x, y=round(e.end.y - dy_of[e.event_id], 1)),
            }
        )
        if e.event_id in dy_of
        else e
        for e in events
    ]
    return delivered, corrected
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest -q && uv run ruff check . && uv run ruff format --check .`
Expected: all tests pass; ruff clean.

- [ ] **Step 5: Commit**

```bash
git add engine/amend.py tests/test_engine_amend.py
git commit -m "Derive the feed as first delivered" -m "The simulator produces the truth, and an amendment's events were first shown displaced. first_delivered builds that v1 feed and lists the events each amendment corrects, so tests can measure what the 55' flank card saw before the correction."
```

---

### Task 3: Measure whether a planted story is visible in one match

**Files:**
- Create: `engine/visibility.py`
- Test: `tests/test_engine_visibility.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_engine_visibility.py`:

```python
import pytest

from contracts.clock import Window
from contracts.event import Event, PassQualifiers, Point
from engine.visibility import (
    change,
    clears,
    first_half,
    long_ball_share,
    pressure_rate,
    right_channel_share,
    separation,
)


def _event(type_, team, clock="10:00", x=30.0, y=34.0, dist=10.0):
    pass_q = PassQualifiers(distance_m=dist, ball_speed_kmh=50, pressure_on_passer=0)
    return Event(
        event_id="e",
        match_id="t01",
        clock=clock,
        wall_clock_ms=0,
        type=type_,
        team=team,
        start=Point(x=x, y=y),
        end=Point(x=x, y=y),
        pass_q=pass_q if type_ == "pass" else None,
    )


def _all(e):
    return True


def test_pressure_rate_counts_only_the_opponents_first_60_percent():
    events = [
        _event("pass", "Northvale", x=30),  # in Northvale's first 60%
        _event("carry", "Northvale", x=62),
        _event("carry", "Northvale", x=70),  # beyond it
        _event("pressure", "Harbour City", x=60),  # x > 42 in the presser's frame
        _event("pressure", "Harbour City", x=40),
    ]
    assert pressure_rate("Harbour City", "Northvale")(events, _all) == 0.5


def test_long_ball_share_counts_passes_over_30_metres():
    events = [_event("pass", "Northvale", dist=d) for d in (10, 30, 31, 45)]
    events.append(_event("pass", "Harbour City", dist=50))
    assert long_ball_share("Northvale")(events, _all) == 0.5


def test_right_channel_share_uses_the_right_third_of_the_width():
    events = [_event("carry", "Northvale", y=y) for y in (10, 45.3, 45.4, 60)]
    assert right_channel_share("Northvale")(events, _all) == 0.5


def test_change_is_the_window_against_the_same_matchs_first_half():
    events = [
        _event("pass", "Northvale", clock="10:00", dist=10),
        _event("pass", "Northvale", clock="20:00", dist=40),
        _event("pass", "Northvale", clock="60:00", dist=40),
    ]
    assert long_ball_share("Northvale")(events, first_half) == 0.5
    assert change(long_ball_share("Northvale"), events, Window.model_validate("58:00-63:00")) == 0.5


def test_separation_and_clears_are_in_natural_standard_deviations():
    natural = [0.0, 2.0, 4.0]  # mean 2, sd 2
    assert separation([6.0, 8.0], natural) == pytest.approx(2.5)
    assert clears(6.0, natural)
    assert not clears(5.9, natural)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_engine_visibility.py -q`
Expected: collection error, `ModuleNotFoundError: No module named 'engine.visibility'`.

- [ ] **Step 3: Implement**

Create `engine/visibility.py`:

```python
"""Would a detector see a planted story in one match? (spec §7.2)

The detector watches a single match, so a paired-run effect whose confidence interval
clears zero is not enough. A story is visible when its observable's in-match change
(the detection window against the same match's first half) stands out from the change
that observable shows without the story. Separation is that gap in standard deviations
of the natural change, over many seeds. Every observable here rises with its story.
"""

import statistics
from collections.abc import Callable

from contracts.clock import Window
from contracts.event import Event

ON_BALL = ("pass", "carry", "dribble")
RIGHT_CHANNEL_Y = 68 * 2 / 3  # right third of the width, in the acting team's frame

Keep = Callable[[Event], bool]
Observable = Callable[[list[Event], Keep], float]


def first_half(e: Event) -> bool:
    return e.clock.period == 1


def change(observable: Observable, events: list[Event], window: Window) -> float:
    """The observable over `window` minus its first-half value, in one match."""
    return observable(events, lambda e: window.contains(e.clock)) - observable(events, first_half)


def separation(story: list[float], natural: list[float]) -> float:
    """Mean story change above mean natural change, in natural standard deviations."""
    return (statistics.mean(story) - statistics.mean(natural)) / statistics.stdev(natural)


def clears(story_change: float, natural: list[float], sds: float = 2.0) -> bool:
    """One match's change sits at least `sds` natural standard deviations above normal."""
    return story_change >= statistics.mean(natural) + sds * statistics.stdev(natural)


def pressure_rate(presser: str, opponent: str) -> Observable:
    """Pressures by `presser` per `opponent` on-ball action in the opponent's first 60%.

    A rate, not a count: a heavier press also shortens the opponent's time on the ball.
    That zone is x < 63 in the opponent's frame and x > 42 in the presser's.
    """

    def rate(events: list[Event], keep: Keep) -> float:
        pressures = sum(
            e.type == "pressure" and e.team == presser and e.start.x > 42 and keep(e)
            for e in events
        )
        actions = sum(
            e.type in ON_BALL and e.team == opponent and e.start.x < 63 and keep(e) for e in events
        )
        return pressures / actions

    return rate


def long_ball_share(team: str) -> Observable:
    """Share of `team`'s passes longer than 30 m."""

    def share(events: list[Event], keep: Keep) -> float:
        passes = [e for e in events if e.type == "pass" and e.team == team and keep(e)]
        return sum(p.pass_q.distance_m > 30 for p in passes) / len(passes)

    return share


def right_channel_share(team: str) -> Observable:
    """Share of `team`'s on-ball actions that start in the right third of the width."""

    def share(events: list[Event], keep: Keep) -> float:
        ys = [e.start.y for e in events if e.type in ON_BALL and e.team == team and keep(e)]
        return sum(y > RIGHT_CHANNEL_Y for y in ys) / len(ys)

    return share
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run python scripts/check_engine_isolation.py`
Expected: all tests pass; ruff clean; `Engine isolation OK`.

- [ ] **Step 5: Commit**

```bash
git add engine/visibility.py tests/test_engine_visibility.py
git commit -m "Measure whether a planted story is visible in one match" -m "The detector sees one match, so a paired effect that clears zero is not enough. signal.py takes a story's in-match change against the same match's first half and compares it with the change the observable shows without the story, in standard deviations of that natural change."
```

---

### Task 4: Keep open play off the touchlines and recalibrate

**Files:**
- Modify: `engine/sim.py`
- Test: `tests/test_engine_sim.py`, `tests/test_engine_realism.py`

- [ ] **Step 1: Write the failing tests**

In `tests/test_engine_sim.py`, add `from itertools import pairwise` as the first import, and append (after two blank lines):

```python
def test_a_ball_over_a_touchline_comes_back_as_a_throw_in():
    """Open play reflects off the touchlines; only a misplaced pass goes over one."""
    for seed in (3, 4, 5):
        play = [e for e in MatchSim(M01, seed=seed).run() if e.type != "sprint"]
        throw_ins = 0
        for prev, e in pairwise(play):
            over = prev.type == "pass" and prev.end.y in (0.0, 68.0)
            throw_in = e.type == "set_piece" and e.qualifiers["kind"] == "throw_in"
            assert over == throw_in, e.event_id
            if over:
                throw_ins += 1
                assert prev.outcome == "incomplete" and e.team != prev.team, e.event_id
                line = 67.5 if prev.end.y == 0.0 else 0.5  # the same touchline, other frame
                assert _close(e.start, Point(x=105 - prev.end.x, y=line)), e.event_id
        assert throw_ins > 0
```

Sprints are filtered out because a sprint can be timestamped between a pass and the restart that follows it.

Replace `tests/test_engine_realism.py` with:

```python
"""Match totals stay within typical top-flight ranges (spec §7.3 realism controls).

Seeds 100-139 are held out: none of them were used to tune the engine's constants.
"""

import statistics
from collections import Counter
from pathlib import Path

from engine.script import load_script
from engine.sim import MatchSim

M01_PATH = Path(__file__).resolve().parents[1] / "engine" / "scripts" / "planted" / "m01.yaml"
BASE = load_script(M01_PATH).model_copy(update={"scripts": []})


def test_totals_per_team_are_realistic():
    passes, completion, shots, goals, shot_x, shot_dist = [], [], [], [], [], []
    throw_ins, on_ball_y = [], []
    for seed in range(100, 140):
        events = MatchSim(BASE, seed=seed).run()
        match_shots = [e for e in events if e.type == "shot"]
        shot_x += [round(e.start.x) for e in match_shots]
        shot_dist += [e.shot_q.distance_m for e in match_shots]
        throw_ins.append(
            sum(e.type == "set_piece" and e.qualifiers["kind"] == "throw_in" for e in events)
        )
        on_ball_y += [e.start.y for e in events if e.type in ("pass", "carry", "dribble")]
        for team in ("Harbour City", "Northvale"):
            team_passes = [e for e in events if e.type == "pass" and e.team == team]
            passes.append(len(team_passes))
            completion.append(sum(p.outcome == "complete" for p in team_passes) / len(team_passes))
            shots.append(sum(e.type == "shot" and e.team == team for e in events))
            goals.append(sum(e.type == "goal" and e.team == team for e in events))
    assert 400 <= statistics.mean(passes) <= 600
    assert 0.75 <= statistics.mean(completion) <= 0.86
    assert 10 <= statistics.mean(shots) <= 17
    assert 2.4 <= 2 * statistics.mean(goals) <= 3.3
    assert 15 <= statistics.mean(shot_dist) <= 21
    # Open play must not pile up on one line: no single metre of x holds 15% of shots,
    assert Counter(shot_x).most_common(1)[0][1] / len(shot_x) < 0.15
    # no 2 m strip of the width holds 8% of on-ball actions, and neither wide third of
    # the width is starved.
    strips = Counter(int(y // 2) for y in on_ball_y)
    assert max(strips.values()) / len(on_ball_y) < 0.08
    for wide in (sum(y < 68 / 3 for y in on_ball_y), sum(y > 68 * 2 / 3 for y in on_ball_y)):
        assert wide / len(on_ball_y) >= 0.25
    assert 30 <= statistics.mean(throw_ins) <= 55
```

A flat spread puts 33.1% of actions in each third, so the wide-third bound is a floor only; the pile-up is caught by the 2 m strip (10.3% on the touchline strip before this task).

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_engine_sim.py tests/test_engine_realism.py -q`
Expected: `test_a_ball_over_a_touchline_comes_back_as_a_throw_in` fails (clamped open play ends passes on the line without a throw-in) and `test_totals_per_team_are_realistic` fails at `assert (5662 / 54896) < 0.08`.

- [ ] **Step 3: Implement**

In `engine/sim.py`, replace the module docstring with:

```python
"""Possession-chain match simulator (spec §7.1).

A possession is a chain of actions (pass, carry, dribble, shot) by the team on the
ball while the other team presses according to its press height. Pressure makes
passes riskier and pushes the team on the ball to go long: the mechanism behind a
pressure shift. Open play reflects off the touchlines, and a misplaced pass near one
runs out for a throw-in. Every random draw comes from a keyed stream (engine.rng), so
a run without one intervention stays aligned with the run that has it. Coordinates
are in the acting team's attacking frame (engine.teams).
"""
```

Below `OPEN_PLAY_MAX_X`, add:

```python
THROW_IN_BAND = 8.0  # a misplaced pass ending this close to a touchline runs out
```

Replace `ahead()` with `reflect()` and a new `ahead()`:

```python
def reflect(v: float, lo: float, hi: float) -> float:
    return 2 * lo - v if v < lo else 2 * hi - v if v > hi else v


def ahead(x: float, y: float, dist: float, angle: float) -> tuple[float, float]:
    """A point `dist` metres away at `angle` radians, reflected off the six-yard line,
    the touchlines and the passer's own goal line.

    Reflecting rather than clamping keeps play from piling up on any line.
    """
    tx = reflect(x + dist * math.cos(angle), 0.5, OPEN_PLAY_MAX_X)
    ty = reflect(y + dist * math.sin(angle), 0.5, PITCH_Y - 0.5)
    return tx, ty
```

One reflection is enough: no pass or carry overshoots by more than the pitch's width. In `_pass`, directly after the `ok = self.rng.chance("pass_success", ...)` line, add:

```python
        out = not ok and (ty < THROW_IN_BAND or ty > PITCH_Y - THROW_IN_BAND)
        if out:  # a misplaced pass near a touchline runs out over it
            ty = 0.0 if ty < PITCH_Y / 2 else PITCH_Y
            dist = math.hypot(tx - x, ty - y)
```

and replace the old throw-in branch

```python
        if ty < 3 or ty > PITCH_Y - 3:  # out for a throw-in
            spot = on_pitch(lost_at[0], 0.5 if lost_at[1] < 34 else PITCH_Y - 0.5)
```

with

```python
        if out:
            spot = on_pitch(*lost_at)
```

The recalibration, tuned on seeds 0–79: in `_possession` change the shot choice to `0.035 + 0.006 * (x - 80)` (was `0.05 + ...`), and in `_shot` change the xG intercept to `-0.75` (was `-0.65`):

```python
            if shooting_zone and self.rng.chance("shot_choice", m, 0.035 + 0.006 * (x - 80)):
```

```python
        xg = 1 / (1 + math.exp(-(-0.75 - 0.10 * dist + 0.03 * angle - 0.30 * defenders)))
```

Without the recalibration the touchline change alone lifts held-out goals to 3.73 a match.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest -q && uv run ruff check . && uv run ruff format --check .`
Expected: all tests pass (the m01 mechanism tests still hold); ruff clean.

- [ ] **Step 5: Commit**

```bash
git add engine/sim.py tests/test_engine_sim.py tests/test_engine_realism.py
git commit -m "Keep open play off the touchlines and recalibrate" -m "Clamping y put 17% of on-ball actions on a touchline and inflated the wide channels the 55' flank card reads. Open play now reflects off the touchlines, and a misplaced pass ending within 8 m of one runs out for a throw-in. Shot choice and the xG intercept are retuned on seeds 0-79 to hold goals near 2.8 a match."
```

---

### Task 5: Bypass a high press with long balls from the back

**Files:**
- Modify: `engine/sim.py`
- Test: `tests/test_engine_mechanisms.py`

- [ ] **Step 1: Write the failing test**

In `tests/test_engine_mechanisms.py`, add above `def nv03_sprints`:

```python
def nv_unpressed_long_share(events):
    """Long-ball share of Northvale passes from their own 70 m that nobody pressed."""
    passes = [
        e
        for e in events
        if e.type == "pass"
        and e.team == "Northvale"
        and e.start.x < 70
        and e.pass_q.pressure_on_passer == 0
        and _in(e, 62, 68)
    ]
    return sum(p.pass_q.distance_m > 30 for p in passes) / len(passes)
```

and above `def test_stamina_decay_costs_sprints`:

```python
def test_a_high_press_is_bypassed_with_long_balls():
    low, _ = _paired_ci("s1", nv_unpressed_long_share)
    assert low > 0
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_engine_mechanisms.py -q`
Expected: `test_a_high_press_is_bypassed_with_long_balls` fails at `assert -0.0622... > 0`: today only pressure on the passer makes a team go long.

- [ ] **Step 3: Implement**

In `engine/sim.py`, replace the module docstring with:

```python
"""Possession-chain match simulator (spec §7.1).

A possession is a chain of actions (pass, carry, dribble, shot) by the team on the
ball while the other team presses according to its press height. Pressure makes
passes riskier and pushes the team on the ball to go long, and a press above 0.5 is
bypassed with long balls from the back even when nobody presses the passer: the
mechanisms behind a pressure shift. Open play reflects off the touchlines, and a
misplaced pass near one runs out for a throw-in. Every random draw comes from a keyed
stream (engine.rng), so a run without one intervention stays aligned with the run that
has it. Coordinates are in the acting team's attacking frame (engine.teams).
"""
```

Below `THROW_IN_BAND`, add:

```python
BYPASS = 1.0  # extra long-ball chance per unit of opponent press height above 0.5
```

In `_pass`, replace the `long_p = ...` line with:

```python
        opp_press = self.params.team(other(att), self.period, self.t)["press_height"]
        bypass = BYPASS * max(0.0, opp_press - 0.5)  # go long to skip a high press
        long_p = clamp(tp["directness"] + bypass + 0.9 * pressure, 0.0, 0.9) if x < 70 else 0.05
```

The press is read at the same moment as the rest of the possession's parameters, so the match before an intervention stays identical with and without it.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest -q && uv run ruff check . && uv run ruff format --check .`
Expected: all tests pass; the new CI is about [+0.14, +0.32] on today's m01. Realism stays in band (held-out goals 3.15 with today's m01, 2.80 after Task 6).

- [ ] **Step 5: Commit**

```bash
git add engine/sim.py tests/test_engine_mechanisms.py
git commit -m "Bypass a high press with long balls from the back" -m "Facing a press above 0.5, a team now goes long more often from its own 70 m even when nobody presses the passer, as teams do to skip a press. Without it a raised press barely moved the opponent's long-ball share in a single match."
```

---

### Task 6: Make the demo match's planted stories visible in one match

**Files:**
- Modify: `engine/scripts/planted/m01.yaml`
- Create: `tests/test_engine_planted_signal.py`
- Modify: `tests/test_engine_script.py`, `tests/test_engine_sim.py`, `tests/test_engine_mechanisms.py`
- Modify: `docs/spec.md` (§7.1 example and text, §19 table), `docs/demo-script.md`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_engine_planted_signal.py`:

```python
"""Each planted story in the demo match is visible in a single match (spec §7.2).

Held-out seeds 100-139 set the natural variation; none of them tuned the engine.
"""

import functools
from pathlib import Path

from contracts.clock import Window
from engine.amend import first_delivered
from engine.script import load_script
from engine.sim import MatchSim
from engine.visibility import (
    change,
    long_ball_share,
    pressure_rate,
    right_channel_share,
    separation,
)

M01_PATH = Path(__file__).resolve().parents[1] / "engine" / "scripts" / "planted" / "m01.yaml"
M01 = load_script(M01_PATH)
WITHOUT_S1 = M01.model_copy(update={"scripts": [s for s in M01.scripts if s.id != "s1"]})
HELD_OUT = range(100, 140)
CARD = Window.model_validate("58:00-63:00")  # the 63' press card's change window
FLANK = Window.model_validate("45:00-55:00")  # a1's window, and the 55' flank card's
PRESS = {
    "pressure_rate": pressure_rate("Harbour City", "Northvale"),
    "long_ball_share": long_ball_share("Northvale"),
}
RIGHT = right_channel_share("Northvale")


@functools.cache
def _match(seed):
    """Per observable: (change with the story, change without it), in one match.

    The press story's natural change comes from the same seed without s1; the flank
    story's from the truth, which a1 restores.
    """
    events = MatchSim(M01, seed=seed).run()
    without = MatchSim(WITHOUT_S1, seed=seed).run()
    delivered, corrected = first_delivered(M01, events)
    out = {name: (change(f, events, CARD), change(f, without, CARD)) for name, f in PRESS.items()}
    out["right_channel_share"] = change(RIGHT, delivered, FLANK), change(RIGHT, events, FLANK)
    out["corrected"] = len(corrected["a1"])
    return out


def _natural(name):
    return [_match(s)[name][1] for s in HELD_OUT]


def _separation(name):
    return separation([_match(s)[name][0] for s in HELD_OUT], _natural(name))


def test_raised_press_is_visible_in_one_match():
    assert _separation("pressure_rate") >= 2.5
    assert _separation("long_ball_share") >= 2.5


def test_flank_error_is_visible_as_first_delivered():
    # Play stays on one side for spells, so a 10-minute channel share is noisy and the
    # largest rise a lateral shift can cause is about a third: the bar is lower. 1.5 is
    # the requirement, not a fit: other 40-seed sets give 1.56-2.21, so a change that
    # reshuffles the random draws can land near it without any real regression.
    assert _separation("right_channel_share") >= 1.5
    assert min(_match(s)["corrected"] for s in HELD_OUT) >= 12
```

The bars sit below the measured values (3.26, 5.09 and 1.84; at least 17 events corrected) so that ordinary changes elsewhere in the engine do not trip them, and well above where today's m01 sits.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_engine_planted_signal.py -q`
Expected: `2 failed`. Today's s1 starts at 60:00 (the 58–63' window sees little of it), and a1 selects only carries in y 32–50.

- [ ] **Step 3: Rewrite the demo script**

Replace `engine/scripts/planted/m01.yaml` with:

```yaml
# Demo match. Mechanisms only: which cause each intervention represents lives in
# the planted suite's sealed ground truth, never here.
match_id: m01
seed: 4417
teams:
  home: { name: "Harbour City", code: HC, formation: "4-3-3", press_height: 0.3 }
  away: { name: "Northvale", code: NV, formation: "4-2-3-1", press_height: 0.55 }

scripts:
  - id: s1
    at: "56:00"   # at full height by 58:00, so the 58-63' card window sees all of it
    ramp: "2m"
    team: home
    set: { press_height: 0.9 }

amendments:
  - id: a1
    at: "68:00"   # after the 63' press card, so the demo shows a published card withdrawn
    batch:
      # Northvale's on-ball events whose true start and end both lie in y 0-46;
      # the feed first showed them 22 m to the right.
      filter:
        types: [pass, carry, dribble]
        team: away
        window: "45:00-55:00"
        y_min: 0
        y_max: 46
      shift: { dy_m: -22 }
    reason: "provider coordinate recalibration"
```

s2 is gone: one player's sprint count cannot show fatigue in a single match (see the design decisions). The seed changes in Task 7.

- [ ] **Step 4: Run the new tests to verify they pass**

Run: `uv run pytest tests/test_engine_planted_signal.py -q`
Expected: `2 passed`.

- [ ] **Step 5: Run the whole suite and see what the new script breaks**

Run: `uv run pytest -q`
Expected: four failures, all from tests that name the old script: `test_demo_script_loads`, `test_unquoted_yaml_time_is_rejected`, `test_interventions_leave_the_match_before_them_untouched`, `test_stamina_decay_costs_sprints`.

- [ ] **Step 6: Update those tests**

In `tests/test_engine_script.py`, replace `test_demo_script_loads` with:

```python
def test_demo_script_loads():
    script = load_script(M01)
    (s1,) = script.scripts
    assert (s1.at.period, s1.at.minute, s1.ramp_seconds) == (2, 56, 120)
    assert s1.set == {"press_height": 0.9}
    (a1,) = script.amendments
    assert a1.batch.filter.types == ["pass", "carry", "dribble"]
    assert a1.batch.shift.dy_m == -22
```

and in `test_unquoted_yaml_time_is_rejected` replace the comment and the `write_text` line with:

```python
    # YAML reads an unquoted 56:00 as the integer 3360; loading must refuse it.
    bad = tmp_path / "bad.yaml"
    bad.write_text(M01.read_text().replace('at: "56:00"', "at: 56:00"))
```

In `tests/test_engine_sim.py`, change the import to `from engine.script import Intervention, load_script`, add below `M01 = load_script(M01_PATH)`:

```python
TIRED = M01.model_copy(
    update={
        "scripts": [
            *M01.scripts,
            Intervention.model_validate(
                {
                    "id": "s2",
                    "at": "62:00",
                    "ramp": "6m",
                    "team": "away",
                    "player": "NV-03",
                    "set": {"stamina_decay": 2.5},
                }
            ),
        ]
    }
)
```

and replace `test_interventions_leave_the_match_before_them_untouched` with:

```python
def test_interventions_leave_the_match_before_them_untouched():
    for script, sid, start_minute in ((M01, "s1", 56), (TIRED, "s2", 62)):
        without = script.model_copy(update={"scripts": [s for s in script.scripts if s.id != sid]})

        def before(events, cutoff=start_minute):
            return _dump([e for e in events if e.clock.minute < cutoff])

        assert before(MatchSim(script, seed=3).run()) == before(MatchSim(without, seed=3).run())
```

In `tests/test_engine_mechanisms.py`, replace everything from the imports down to the end of `_paired_ci` with:

```python
import statistics
from pathlib import Path

from engine.script import Intervention, load_script
from engine.sim import MatchSim

M01_PATH = Path(__file__).resolve().parents[1] / "engine" / "scripts" / "planted" / "m01.yaml"
M01 = load_script(M01_PATH)
# m01 no longer plants fatigue (one player's sprints cannot show it in a single match),
# so the stamina mechanism is checked on m01 plus a test-only intervention.
TIRED = M01.model_copy(
    update={
        "scripts": [
            *M01.scripts,
            Intervention.model_validate(
                {
                    "id": "s2",
                    "at": "62:00",
                    "ramp": "6m",
                    "team": "away",
                    "player": "NV-03",
                    "set": {"stamina_decay": 2.5},
                }
            ),
        ]
    }
)
SEEDS = range(20)


def _paired_ci(script, sid, observable):
    """Mean with-minus-without difference over seeds, with a normal 95% CI."""
    without = script.model_copy(update={"scripts": [s for s in script.scripts if s.id != sid]})
    diffs = [
        observable(MatchSim(script, seed=s).run()) - observable(MatchSim(without, seed=s).run())
        for s in SEEDS
    ]
    mean = statistics.mean(diffs)
    half = 1.96 * statistics.stdev(diffs) / len(diffs) ** 0.5
    return mean - half, mean + half
```

(keep the module docstring above it), then update the four call sites:

```python
    low, _ = _paired_ci(M01, "s1", hc_pressure_rate)
    low, _ = _paired_ci(M01, "s1", nv_long_ball_share)
    low, _ = _paired_ci(M01, "s1", nv_unpressed_long_share)
    _, high = _paired_ci(TIRED, "s2", nv03_sprints)
```

- [ ] **Step 7: Update the spec and the demo script**

In `docs/spec.md` §7.1, replace the whole YAML example (from `# Demo match.` to `reason: "provider coordinate recalibration"`) with the exact contents of the new `engine/scripts/planted/m01.yaml`. Then make three replacements:

- In the paragraph that starts `For the demo match the sequence is:`, replace `the amendment at 68' relocating the 48–55' carries;` with `the amendment at 68' relocating Northvale's 45–55' passes, carries and dribbles;`.
- Replace `observable 60:00–68:00` with `observable 56:00–64:00`.
- In the §19 table row `1:00–1:18`, replace `At 68' a batch amendment relocates Northvale's 48–55' carries.` with `At 68' a batch amendment relocates Northvale's 45–55' passes, carries and dribbles.`

Make the same §19 replacement in `docs/demo-script.md` (its `1:00–1:18` row).

- [ ] **Step 8: Run all checks**

Run: `uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run python scripts/check_engine_isolation.py`
Expected: all tests pass; ruff clean; `Engine isolation OK`.

- [ ] **Step 9: Commit**

```bash
git add engine/scripts/planted/m01.yaml tests/test_engine_planted_signal.py tests/test_engine_script.py tests/test_engine_sim.py tests/test_engine_mechanisms.py docs/spec.md docs/demo-script.md
git commit -m "Make the demo match's planted stories visible in one match" -m "s1 started at 60:00 with a 3-minute ramp, so the 58-63' card window saw a quarter of it; it now starts at 56:00 and is at full height by 58:00, a switch from a mid-block to a high press. a1 relocates about fifty Northvale passes, carries and dribbles instead of two carries. s2 is no longer planted: one player's sprint count cannot show fatigue in a single match."
```

---

### Task 7: Choose the demo seed by a stated rule and pin the demo match

**Files:**
- Modify: `tests/test_engine_planted_signal.py`, `tests/test_engine_cli.py`
- Modify: `engine/scripts/planted/m01.yaml`
- Create: `DATASET.md`
- Modify: `docs/spec.md` (§7.1), `README.md`, `CLAUDE.md`

- [ ] **Step 1: Write the failing test**

In `tests/test_engine_planted_signal.py`, add `import statistics` below `import functools`, add `clears,` to the `engine.visibility` import list (after `change,`), and append (after two blank lines):

```python
def _typical_and_visible(name, story_change):
    """At least the held-out median, and clear of natural variation."""
    held_out = [_match(s)[name][0] for s in HELD_OUT]
    return story_change >= statistics.median(held_out) and clears(story_change, _natural(name))


def _shows_every_story(seed):
    m = _match(seed)
    stories = ("pressure_rate", "long_ball_share", "right_channel_share")
    corrected_flank = m["right_channel_share"][1]
    return all(_typical_and_visible(name, m[name][0]) for name in stories) and not clears(
        corrected_flank, _natural("right_channel_share")
    )


def test_demo_seed_is_the_first_from_4417_that_shows_every_story():
    seed = 4417
    while not _shows_every_story(seed):
        seed += 1
    assert M01.seed == seed, f"the demo-seed rule now picks seed {seed}"
```

"Clears" alone is not enough: on seed 4417 the pressure-rate change (0.245) clears the bar (0.238) by a hair while sitting well below the held-out median (0.384), and a demo match that barely clears is fragile once real detector thresholds exist.

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_engine_planted_signal.py -q`
Expected: `AssertionError: the demo-seed rule now picks seed 4434` (18 seeds scanned, about 4 s).

- [ ] **Step 3: Set the seed and state the rule in the script**

In `engine/scripts/planted/m01.yaml`, replace the line `seed: 4417` with:

```yaml
# The first seed from 4417 up on which every planted story is visible in this one
# match (tests/test_engine_planted_signal.py; DATASET.md). Reported numbers use held-out seeds.
seed: 4434
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_engine_planted_signal.py -q`
Expected: `3 passed`.

- [ ] **Step 5: Pin the demo match**

In `tests/test_engine_cli.py`, add `import hashlib` above `import json`, and append (after two blank lines):

```python
def test_the_demo_match_is_pinned(tmp_path, capsys):
    """The video's match. A change that moves it must update these lines on purpose."""
    main(["generate", "--script", str(M01), "--out", str(tmp_path)])
    out = capsys.readouterr().out.strip()
    assert out == "m01 seed 4434: 2963 events, Harbour City 2-3 Northvale"
    digest = hashlib.sha256((tmp_path / "events.jsonl").read_bytes()).hexdigest()
    assert digest == "fe4a2b2f7fac83443c3828ba3e22e893d31c99b7661f9939bec6804da3e45424"
```

Run: `uv run pytest tests/test_engine_cli.py -q`
Expected: `5 passed`. If the digest differs while the line matches, the platform's float formatting differs from the one this was measured on; record the CI value only after checking that the event count and score agree.

- [ ] **Step 6: Write `DATASET.md`**

Create `DATASET.md` at the repo root (spec §22). It describes rules only; measured numbers join it with the generated realism report.

```markdown
# Proofline synthetic match dataset

Every club, player and competition here is fictional. Matches come from the Match Engine (`engine/`), a possession-chain simulator driven by tactical scripts that declare mechanisms, never causes. The schema, the script DSL, the amendment format, the paired-run method and the realism report join this file with the dataset release.

## The demo match

[`engine/scripts/planted/m01.yaml`](engine/scripts/planted/m01.yaml) plants one tactical change and one feed error:

- **s1** raises Harbour City's press height from 0.3 to 0.9 from 56:00, reaching it at 58:00.
- **a1** is a provider error: the feed first shows Northvale's 45:00–55:00 passes, carries and dribbles 22 m to the right of where they happened, and a batch amendment at 68:00 moves them back.

Its seed is chosen by a stated rule, never by eye: **the first seed from 4417 upwards on which, in that one match, each planted story's change is at least its median over the held-out seeds and clears two natural standard deviations, and on which the corrected flank change does not.** [`tests/test_engine_planted_signal.py`](tests/test_engine_planted_signal.py) applies the rule and fails if the script's seed is not the one it picks. The demo match is therefore a clear instance of each story, not a typical one, and no reported number comes from it: evaluation uses held-out seeds 100–139, which played no part in tuning the engine.

## Is a planted story visible in one match?

The detector watches a single match, so a paired-run effect whose confidence interval clears zero is not enough. For an observable and a detection window, a match's **change** is the observable over the window minus its value over the same match's first half. The **natural change** is the same quantity without the story: the same seed with the intervention removed or, for a feed error, the corrected events. **Separation** is the mean change with the story minus the mean natural change, in standard deviations of the natural change across seeds ([`engine/visibility.py`](engine/visibility.py)). A match **clears** when its own change is at least two natural standard deviations above the mean natural change.

| Story | Observable | Window |
|---|---|---|
| s1 | Harbour City pressures per Northvale on-ball action in Northvale's first 60% | 58:00–63:00 |
| s1 | Share of Northvale's passes longer than 30 m | 58:00–63:00 |
| a1 | Share of Northvale's on-ball actions starting in the right third of the width, as first delivered | 45:00–55:00 |
```

- [ ] **Step 7: State the rule in the spec, the README and `CLAUDE.md`**

In `docs/spec.md` §7.1, replace the YAML example again with the exact contents of `engine/scripts/planted/m01.yaml` (it now carries the seed comment and `seed: 4434`), and at the end of the paragraph that starts `For the demo match the sequence is:`, after `the press card untouched.`, append (after one space):

```markdown
The demo match's seed is chosen by a stated rule (`DATASET.md`): the first seed from 4417 upwards on which every planted story is at least typical and visible in that one match, and the corrected flank is not. No reported number comes from it.
```

In `README.md`, add this row to the Repository table below the `engine/` row:

```markdown
| `DATASET.md` | The synthetic dataset: the demo match, the stated rule that picks its seed, and how each planted story is checked for visibility in a single match |
```

In `CLAUDE.md`, replace the line

```bash
uv run proofline-engine generate --script engine/scripts/planted/m01.yaml --seed 4417 --out data/m01/
```

with

```bash
uv run proofline-engine generate --script engine/scripts/planted/m01.yaml --out data/m01/   # the script carries its seed
```

- [ ] **Step 8: Run all checks**

Run: `uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run python scripts/check_engine_isolation.py && uv run proofline-engine generate --script engine/scripts/planted/m01.yaml --out data/m01/`
Expected: all tests pass (121 at this point in execution); ruff clean; `Engine isolation OK`; the last line prints `m01 seed 4434: 2963 events, Harbour City 2-3 Northvale`. `data/` is gitignored; do not commit it.

- [ ] **Step 9: Commit**

```bash
git add tests/test_engine_planted_signal.py tests/test_engine_cli.py engine/scripts/planted/m01.yaml DATASET.md docs/spec.md README.md CLAUDE.md
git commit -m "Choose the demo seed by a stated rule and pin the demo match" -m "The demo match is the first seed from 4417 up on which every planted story is at least typical and visible in that one match, and the corrected flank is not; a test applies the rule, so the seed can never be picked by eye. A golden test pins the video's match. Reported numbers stay on held-out seeds."
```

---

### Task 8: Require single-match visibility before a script counts toward recall

**Files:**
- Modify: `docs/spec.md` (§7.2, §8.1, §11.1)

- [ ] **Step 1: Edit the spec**

In §7.2, replace the bullet

```markdown
- A script whose effect's confidence interval includes zero is `not_observable` and excluded from recall.
```

with

```markdown
- A script is `not_observable`, and excluded from recall, when its effect's confidence interval includes zero or when none of its observables separates from natural variation by two standard deviations, in the direction its ground truth names, in a single match (`engine/visibility.py`, defined in `DATASET.md`). The detector sees one match: a paired effect can clear zero and still be invisible in every match it happens in. The scoreboard reports how many scripts each rule excluded.
```

In the §8.1 metric table, add this row below `Field tilt`:

```markdown
| Channel share | Share of a team's on-ball actions starting in the left, centre or right third of the width, in its own attacking frame | Build |
```

In §11.1, replace the bullet

```markdown
- Scripts marked `not_observable` by paired runs are excluded from recall.
```

with

```markdown
- Scripts marked `not_observable` (§7.2) are excluded from recall.
```

- [ ] **Step 2: Check nothing else depends on the old wording**

Run: `grep -n "not_observable" docs/spec.md CLAUDE.md README.md`
Expected: the §7.2 bullet, the §11.1 bullet and no other definition.

- [ ] **Step 3: Commit**

```bash
git add docs/spec.md
git commit -m "Require single-match visibility before a script counts toward recall" -m "A script whose paired effect clears zero but which no single match can show only lowers recall, because the detector sees one match. Spec 7.2 now also requires two natural standard deviations of separation and the scoreboard reports what each rule excluded; 8.1 defines channel share, which the 55' flank card reads."
```

---

### Task 9: Verify, and close the engine-core follow-ups this plan resolves

**Files:**
- Modify: `docs/plans/2026-10-21-match-engine-core.md` (Follow-ups section)
- Modify: `docs/plans/2026-10-22-planted-signal.md` (status line)

- [ ] **Step 1: Run every check from a clean state**

```bash
git status --short          # expect a clean tree (data/ is gitignored)
uv sync
uv run ruff check . && uv run ruff format --check .
uv run python scripts/check_engine_isolation.py
uv run pytest -q
```

Expected: ruff clean; `Engine isolation OK`; 122 tests pass.

- [ ] **Step 2: Mark the resolved follow-ups**

In `docs/plans/2026-10-21-match-engine-core.md`, under `## Follow-ups for later plans`, add directly below the section's first paragraph:

```markdown
> Resolved by `docs/plans/2026-10-22-planted-signal.md`: the demo seed (now chosen by a stated rule), the touchline pile-up, the 55' flank card, pinning the demo match, and rejecting a NaN `dy_m`. Flank bands are superseded: channels are equal thirds of the width, defined in spec §8.1.
```

- [ ] **Step 3: Add a status line to this plan**

Below the "For agentic workers" note at the top of this file, add:

```markdown
> **Status:** executed in October 2026. Do not re-run it; later plans pick up the follow-ups at the end.
```

- [ ] **Step 4: Commit and push**

```bash
git add docs/plans/2026-10-21-match-engine-core.md docs/plans/2026-10-22-planted-signal.md
git commit -m "Close the engine-core follow-ups the planted-signal plan resolves" -m "Each resolved item now points at the plan that fixed it, so the remaining follow-ups are the open ones."
git push
```

---

## Review fixes during execution

Each review finding that changed the code or the docs, after the task named. The design and every measured number above are unchanged by them.

| Task | Fix | Commit |
|---|---|---|
| 1 | Refuse a zero shift, so a missing or misspelled `dy_m` cannot validate as an amendment that moves nothing; messages name the refused type and say exactly which shift field is wrong; a test accepts several types | `6933346` |
| — | Ruff formats Python blocks inside Markdown, so this plan's blocks were made ruff-clean (a class fragment became the whole class) | `55aa399` |
| 2 | Tests pin the start-of-band check and the 0.1 m rounding of v1 coordinates (both could be deleted without a failure) | `8e6eac9` |
| 3 | `engine/signal.py` renamed `engine/visibility.py`: it shadowed the standard library's `signal` whenever `engine/` was on the import path; the plan's later tasks follow | `b1624e5`, `069e66f` |
| 3 | Tests pin the observables' `keep` and team filters and that first-half stoppage stays in the first-half baseline | `9438788`, `67f7a7b` |
| 4 | Tests pin the recomputed distance of a pass that runs out, that carries never end on a touchline, and the share of actions on a touchline; comments say x = 97 is 8 m from the goal line | `fbcd771` |
| 5 | The bypass test measures 62–90': over 62–68' a 0.9 press leaves about four qualifying passes a seed and one seed in 200 has none; the docstring names the 70 m zone | `6bd12a3` |
| 6 | The flank bar's comment says 1.5 is the requirement and gives the 1.56–2.21 range across 40-seed sets; the test is named for what it checks | `300c2f5` |
| 7 | The rule is stated exactly in the script comment, spec, `DATASET.md` and README (the short version picked 4417; "each planted story" could pick 4418 or 4429); a test keeps the spec's YAML identical to the script | `94c600d` |
| 7 | The seed scan stops after 200 seeds; a failing golden pin says what to re-check | `ae68856` |
| 7 | An outside reader implementing the rule from `DATASET.md` alone picked 4423: the pressure-rate zone now applies to both sides of the ratio. A second reader reproduced 4434 | `f050054` |
| 8 | The `not_observable` rule belongs to the script, never to an evaluated match; observables and directions are fixed per class, each judged in its own direction; window, baseline, seeds and freezing are stated; every exclusion is listed | `f8e7f03`, `f8102bb` |

## Follow-ups for later plans

> Open items are tracked in [`docs/backlog.md`](../backlog.md) from 2026-10-23; this list is kept as history.

> Resolved by `docs/plans/2026-10-22-contract-hygiene.md`: channel share and pressure rate in the contracts, and spec §5's example card (now the demo match's measured card, with fatigue rejected by a control counter-test that holds on it). In this plan, "held-out seeds" means seeds 100–139, now called validation seeds; spec §11.1 gives "held-out" to the evaluation suites' 2000–2999.

**Plan 2 (rest): engine proof tooling**
- **Amendment output.** Write the v1 feed (`first_delivered`) and an `amendments.jsonl` of `contracts.EventAmendment` records, one per batch, with `event_ids` from `first_delivered`'s map; the Match Clock replays v1 and emits each batch at its `at`. Refuse an amendment that selects nothing (`EventAmendment.event_ids` needs at least one id). State the 0.1 m rounding rule in `contracts` and require `dy_m` to be a multiple of 0.1, so v1 plus the correction returns the truth exactly.
- **Observability.** The paired-run tooling marks `not_observable` with both rules of spec §7.2. `engine/visibility.py` needs a direction per observable, a before-the-script baseline for scripts that start in the first half, and a defined result for an empty window or a zero natural spread (today both divide by zero); `DATASET.md` gains the per-class table of observables and directions and the observable-window definition (its table today uses the demo cards' windows, 58–63' for s1, while the ground truth's is 56–64').
- **Physical causes in the planted suite.** Design them with tracking: one player's sprint count cannot clear two natural standard deviations, but mean sprint speed separates by 3.3 at a 10× stamina decay, and `player_load` aggregates should do better. Hold every planted script to the same visibility bar before it enters the suite.
- **Realism report.** Record or fix: in about 28% of throw-ins the taker's first action is a carry or dribble; about 22% of on-ball actions reflect off x = 97 and 38.5% start in the last 30 m; scripted windows reach long-ball shares near 40% (m01, 58–63') and 35–36% when a press of 0.9–1.0 runs all match. Fixing the first two changes random draws and needs a recalibration and a new demo seed by the stated rule.
- **The v1 feed's own consistency.** a1 shifts only the Northvale actions whose band fits, so the first-delivered feed has 2–8 jumps of 22 m between consecutive Northvale actions a match, and Harbour City's pressures sit 22 m from the ball they press. A real calibration fault would move one side of the pitch for both teams. Revisit if the State Builder or the Verifier checks v1 consistency.

**Plan 4: State Builder**
- **PPDA over five minutes.** Its natural change has a standard deviation of about 6.7 in a 5-minute window; the 63' card's press proposition should use pressure rate per opponent action, and spec §5's example (PPDA 11.4 → 6.1, long-ball share 21% → 48%) should then quote what the demo match measures (pressure rate 0.32 → 0.83, long-ball share 11% → 59%), presented as this match's numbers: at a 0.9 press the held-out mean pressure rate is about 0.62. The State Builder's pressure rate must use the same zone on both sides of the ratio (x < 63 for the opponent's actions, x > 42 for the pressures), or those numbers will not recompute; §8.1's "press intensity" is a different metric.
- **The 63' card's sample size.** On the demo match the 58–63' window holds 17 Northvale passes and 18 in-zone actions (held-out median 20 passes, minimum 7), against the spec example's 41 and 33. If `docs/support-rules.md` sets a minimum above about 16, the press card cannot reach `measured` language and the casual fan never sees it. Either set the minimums with this in view or let the card use the ground-truth window, 56–64' (25 passes and 30 actions on the demo match; separations 4.14 and 5.20, clearing in 88% and 98% of held-out matches).
- **Channel share in the contracts.** Add `channel_share_left|centre|right` (or a channel argument) to `Metric` and `DEFAULT_THRESHOLD_KIND` with a test before any producer uses them; spec §8.1 now defines it.
- **Support bands for channel share.** Set them on the dev split, never to make the demo come out a particular way. On the demo match the corrected right-channel share is 38% against 24% in the first half (+14 points): if the bands still support that, the demo shows a revision of the 55' card rather than a withdrawal, or the seed rule is extended openly in `DATASET.md`.

**Plan 5: Moment Detector**
- **Expected hit rates.** On held-out seeds the press story clears two natural standard deviations in 82% of matches on pressure rate, 85% on long-ball share and 100% on either; the flank story in 50%. Thresholds tuned on the dev split should be compared with these.
- **The "fatigue ruled out" beat.** With s2 gone, refuting fatigue at 63' rests on ordinary tiredness, and that is not flat: on the demo match Northvale's team sprint rate in 58–63' is 34% below the first half (held-out mean −21%, sd 17%), while spec §5's example says "sprint count flat versus first half (-2%)". Decide how the Physical agent's hypothesis is honestly refuted on this match (for example, Harbour City's sprints fall alike, or the decline is gradual rather than a step at 58') and quote the measured change in §5; or extend the seed rule openly.
- **The 74' "honest silence" beat.** Check on seed 4434 once the detector exists (Harbour City score at 77:09). If a demo beat ever needs another condition on the seed, extend the rule openly in `DATASET.md` and record the seed it replaces.

**General**
- **Test time and duplication.** The suite grew from about 21 s to about 40 s; `tests/test_engine_mechanisms.py` runs the same 40 m01 simulations for each of its three s1 tests (caching them saves about 9 s), defines `TIRED` a second time, and duplicates two observables from `engine/visibility.py`; `tests/test_engine_planted_signal.py` also runs the without-s1 simulation for every scanned seed although the seed rule never reads it there.
