# Planted and Decoy Suites Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Status:** executed on branch `planted-suites` in October 2026, with a spec check, code-quality reviews of Tasks 1–2 and 3–6, a final branch review and an outside audit. The code blocks show each task as dispatched; the fixes listed under "Review fixes during execution" changed the code after the task named. Do not re-run it; later plans pick up the follow-ups at the end.

**Goal:** Give the evaluator planted and decoy suites whose causes span all three agents' domains, each with sealed ground truth and frozen, provenance-carrying `not_observable` flags.

**Architecture:** Two new script features let the engine plant causes beyond the press: a player parameter can target a whole unit, and an intervention can wait for the score (`when: trailing | leading`), with the simulator recording when it actually started. `contracts/planted.py` fixes what each plantable class looks like (its observables and their directions) and the sealed ground-truth record; `contracts/eval_run.py` gains a frozen `FlagSet` every planted run embeds. `engine/paired.py` measures each script over seed pairs and judges it under spec §7.2; `engine/suite_builder.py` and `proofline-engine suite` build the suites from per-split seed ranges, choosing only matches where the planted change is the one fair answer.

**Tech Stack:** Python 3.12, pydantic v2, PyYAML, pytest, ruff, uv; `multiprocessing` for suite building. No new dependency.

---

## Where this plan sits

This is the rest of plan 2, after the contract-hygiene plan (merged at `409424f`). A review of `827b51b` found the engine could plant almost nothing outside the press, so the multi-agent comparison would have little to measure. This plan fixes that for the planted and decoy suites. Deliberately left to the next plan: amendment output and the correction suite, tracking samples for the pitch view, the realism report and the dataset release. `state/season_baselines.json` waits for the State Builder, whose metric definitions it needs.

Every code block was run on a scratch copy of `409424f`. Constants were tuned on seeds 0–79; nothing here touches the evaluation ranges except the suites themselves.

## Design decisions (review these)

- **Plantable classes.** Six, two per domain: press intensity up and down (tactical), chasing the result and protecting a lead (game state), unit fatigue and player fatigue (physical). Block height, formation, flank, substitution and numerical-change causes have no mechanism and are not planted; an agent may still name them, and precision counts it. Separating block height from press, for example, would need a new mechanism plus recalibration, and the six classes already span every agent.
- **Game state by trigger, not by label.** A chasing-the-result script is a press-and-directness change with `when: trailing`: it starts at the first moment from `at` that the team trails. The mechanism is the same as a tactical press change; only the motive differs, which is exactly where the Game-State agent must earn its place.
- **Fatigue from sprint events, not tracking.** Physical observables are sprint count (per minute of play) and mean sprint speed, both already in the event feed; tracking samples come with the pitch view in the next plan. Fatigue needs a stronger stamina decay (7–10), so its allowed range rises from 5 to 10.
- **Single-match visibility on tuning seeds** (separation in natural standard deviations, best observable): press up 4.9, press down 2.5, chasing 2.9, protecting a lead 2.7, unit fatigue 3.9, player fatigue 3.2.
- **Ground-truth hygiene.** A press-up script is planted only where the team is not trailing at its start, and a press-down script only where it is not leading, so that a game-state answer is never equally fair. A score-triggered script is planted only where it starts by 75:00.
- **Opaque match ids** (`p-h-07`, `d-d-02`): match ids reach product code in the event feed, so they must not name the cause. Scripts name mechanisms only; the class lives in `ground_truth.yaml`.
- **Seeds** follow spec §11.1: dev 1000–1999 and held-out 2000–2999, with match seeds from the base, decoys from base + 300 and paired-run seeds from base + 500.
- **Frozen flags with provenance.** `FlagSet` lists every planted script, the seeds measured for each (at least 20, spec §7.2), the exclusions and when it froze, with a content hash as its id. A planted `EvalRun` must embed one frozen before it started, for its own split; it replaces the bare exclusion list from the contract-hygiene plan.
- **Sizes.** Planted: 2 per class in dev (12), 5 in held-out (30); decoys: 4 and 10. Measured in the prototype: 1 of 12 dev scripts and 2 of 30 held-out scripts are excluded (all "no separation": two weaker press-down scripts and one player-fatigue script), honestly reported rather than tuned away.

## File structure

| File | Change |
|---|---|
| `contracts/taxonomy.py` | `Metric.SPRINT_SPEED` |
| `contracts/eval_run.py` | `MIN_SEED_PAIRS`, `FlagSet`; `EvalRun.flags` replaces `not_observable` |
| `contracts/planted.py` | New: `CAUSE_OBSERVABLES`, `PlantedTruth`, `GroundTruth` |
| `engine/script.py` | `unit`, `when`; stamina decay up to 10 |
| `engine/params.py`, `engine/sim.py` | Unit targeting; triggered starts recorded in `ParamTimeline.started` |
| `engine/visibility.py` | Per-minute counts, sprint observables, directional `clears`, `observable()` |
| `engine/paired.py` | New: `window_after`, `resolve`, `measure`, `judge` |
| `engine/suite_builder.py`, `engine/cli.py` | New suite builder; `proofline-engine suite` |
| `scripts/check_engine_isolation.py`, `pyproject.toml` | Product code may not name `engine/scripts` or `engine/suites`; suites stay out of the wheel |
| `engine/suites/**` | The generated suites, committed |
| `tests/…` | Tests for all of the above |
| `docs/spec.md`, `DATASET.md`, `README.md`, `CLAUDE.md` | The new features, suites and command |

Commands: `uv run pytest -q` (about 3 minutes after Task 7), `uv run ruff check . && uv run ruff format --check .`, `uv run python scripts/check_engine_isolation.py`, `uv run python scripts/export_schemas.py`. Commits: one concern each, imperative subject, a body that says why, no attribution trailers.

---

### Task 1: Freeze not-observable flags with their provenance

**Files:** `contracts/taxonomy.py`, `contracts/eval_run.py`, `tests/test_contracts.py`, `docs/*.schema.json`.

- [ ] **Step 1: Tests.** In `tests/test_contracts.py`, add `FlagSet` to the `contracts.eval_run` import (it becomes `from contracts.eval_run import FlagSet, MetricEstimate, Split, Suite, Variant, VariantComparison`). Replace `_eval_run` with:

```python
def _flags(*exclusions, scripts=("p07-s1",)):
    seeds = {s: list(range(2500, 2520)) for s in scripts}
    return dict(
        split="heldout",
        scripts=list(scripts),
        paired_seeds=seeds,
        frozen_at_ms=0,
        exclusions=list(exclusions),
    )


def _eval_run(metrics):
    return EvalRun(
        run_id="r1",
        variant=Variant.A_PROOFLINE,
        suites=[Suite.PLANTED],
        split=Split.HELDOUT,
        model_tier="final",
        match_ids=["m01"],
        metrics=metrics,
        started_at_ms=0,
        finished_at_ms=10,
        flags=FlagSet(**_flags()),
    )
```

Replace `_with_exclusions` with:

```python
def _with_exclusions(exclusions, suite=Suite.PLANTED):
    run = _eval_run([_estimate()]).model_dump(exclude={"flags"})
    metrics = [_estimate(suite=suite).model_dump()]
    return EvalRun.model_validate(
        dict(run, suites=[suite], metrics=metrics, flags=_flags(*exclusions))
    )
```

In `test_excluded_scripts_carry_the_numbers_that_excluded_them` read `.flags.exclusions[0]` instead of `.not_observable[0]`. Replace `test_exclusions_belong_to_planted_runs_and_are_listed_once` with:

```python
def test_exclusions_belong_to_planted_runs_and_are_listed_once():
    with pytest.raises(ValidationError, match="listed once"):
        _with_exclusions([_exclusion("no_separation")] * 2)
    with pytest.raises(ValidationError, match="carries its flag set, and only such a run"):
        _with_exclusions([_exclusion("no_separation")], suite=Suite.DECOYS)


def test_a_flag_set_names_its_provenance_and_changes_id_with_it():
    flags = FlagSet(**_flags())
    assert flags.flag_set_id.startswith("flags-")
    assert FlagSet(**_flags()).flag_set_id == flags.flag_set_id
    excluding = FlagSet(**_flags(_exclusion("no_separation")))
    assert excluding.flag_set_id != flags.flag_set_id
    assert FlagSet.model_validate_json(excluding.model_dump_json()) == excluding


@pytest.mark.parametrize(
    "overrides,message",
    [
        (dict(paired_seeds={"p07-s1": list(range(19))}), "fewer than 20 seed pairs"),
        (dict(paired_seeds={}), "has its paired seeds"),
        (dict(scripts=["p07-s1", "p07-s1"]), "listed once"),
        (dict(exclusions=[_exclusion("no_separation") | {"script_id": "p99"}]), "outside the set"),
    ],
)
def test_a_flag_set_covers_exactly_its_scripts(overrides, message):
    with pytest.raises(ValidationError, match=message):
        FlagSet(**(_flags() | overrides))


def test_a_planted_run_carries_flags_frozen_before_it_for_its_split():
    run = _eval_run([_estimate()]).model_dump()
    with pytest.raises(ValidationError, match="carries its flag set"):
        EvalRun.model_validate(dict(run, flags=None))
    with pytest.raises(ValidationError, match="another split"):
        EvalRun.model_validate(dict(run, flags=_flags() | {"split": "dev"}))
    with pytest.raises(ValidationError, match="frozen before the run starts"):
        EvalRun.model_validate(dict(run, flags=_flags() | {"frozen_at_ms": 5}, started_at_ms=1))
```

Also in `test_every_metric_has_a_pinned_threshold_kind` add `assert DEFAULT_THRESHOLD_KIND[Metric.SPRINT_SPEED] == ThresholdKind.ABSOLUTE`. Run `uv run pytest tests/test_contracts.py -q` → fails at import (`FlagSet`).

- [ ] **Step 2: Implement.** In `contracts/taxonomy.py` add `SPRINT_SPEED = "sprint_speed"` after `SPRINT_COUNT` and `Metric.SPRINT_SPEED: ThresholdKind.ABSOLUTE,` after the `SPRINT_COUNT` entry. In `contracts/eval_run.py`:
  - imports become `import hashlib`, `import json`, `from enum import StrEnum`, and `from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator`;
  - below `VISIBILITY_SDS` add `MIN_SEED_PAIRS = 20  # spec §7.2: each script is estimated over 20-30 seed pairs`;
  - above `class EvalRun` add:

```python
class FlagSet(BaseModel):
    """The frozen not_observable flags of one planted suite split, with their provenance.

    Every planted EvalRun embeds the same flag set, frozen before either variant ran, so
    both variants exclude the same scripts and the scoreboard can show why.
    """

    split: Split
    scripts: list[str] = Field(min_length=1, description="every planted match considered")
    paired_seeds: dict[str, list[int]] = Field(description="per script, the seeds measured")
    frozen_at_ms: int = Field(ge=0)
    exclusions: list[Exclusion] = Field(default_factory=list)

    @computed_field
    @property
    def flag_set_id(self) -> str:
        content = self.model_dump(
            mode="json", include={"split", "scripts", "paired_seeds", "exclusions"}
        )
        digest = hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()
        return f"flags-{digest[:16]}"

    @model_validator(mode="after")
    def _covers_its_scripts(self) -> "FlagSet":
        if len(self.scripts) != len(set(self.scripts)):
            raise ValueError("each planted script is listed once")
        if set(self.paired_seeds) != set(self.scripts):
            raise ValueError("every planted script, and only those, has its paired seeds")
        thin = sorted(s for s, seeds in self.paired_seeds.items() if len(seeds) < MIN_SEED_PAIRS)
        if thin:
            raise ValueError(f"fewer than {MIN_SEED_PAIRS} seed pairs for {thin}")
        excluded = [x.script_id for x in self.exclusions]
        if len(excluded) != len(set(excluded)):
            raise ValueError("each excluded script is listed once")
        unknown = sorted(set(excluded) - set(self.scripts))
        if unknown:
            raise ValueError(f"exclusions name scripts outside the set: {unknown}")
        return self
```

  - in `EvalRun` replace the `not_observable` field with:

```python
    flags: FlagSet | None = Field(
        default=None, description="the planted suite's frozen not_observable flags (spec §7.2)"
    )
```

  - replace the `_exclusions_from_planted_runs` validator with:

```python
    @model_validator(mode="after")
    def _planted_runs_carry_frozen_flags(self) -> "EvalRun":
        planted = Suite.PLANTED in self.suites
        if planted != (self.flags is not None):
            raise ValueError("a planted-suite run carries its flag set, and only such a run")
        if self.flags is not None:
            if self.flags.split != self.split:
                raise ValueError("the flag set is for another split")
            if self.flags.frozen_at_ms > self.started_at_ms:
                raise ValueError("flags must be frozen before the run starts")
        return self
```

- [ ] **Step 3: Check.** `uv run python scripts/export_schemas.py`, then `uv run pytest -q && uv run ruff check . && uv run ruff format --check .`.

- [ ] **Step 4: Commit** `contracts/taxonomy.py contracts/eval_run.py tests/test_contracts.py docs/*.schema.json`:

```bash
git commit -m "Freeze not-observable flags with their provenance" -m "An empty exclusion list could not tell nothing excluded from flags never attached, and nothing tied variant A's exclusions to B's or said which seeds produced them. A planted run now embeds a FlagSet, frozen before it started, naming every script, the seeds measured for each and a content hash. Sprint speed joins the metrics for the fatigue classes."
```

---

### Task 2: Pin what each plantable cause looks like

**Files:** Create `contracts/planted.py`, `tests/test_contracts_planted.py`.

- [ ] **Step 1: Tests.** Create `tests/test_contracts_planted.py`:

```python
import pytest
from pydantic import ValidationError

from contracts.planted import CAUSE_OBSERVABLES, GroundTruth, PlantedTruth
from contracts.prediction import Direction
from contracts.taxonomy import DEFAULT_THRESHOLD_KIND, Cause, Metric


def _truth(**overrides):
    base = dict(
        match_id="p-h-01",
        cause=Cause.PRESS_INTENSITY_UP,
        team="Harbour City",
        script_id="s1",
        started="60:00",
        window="60:00-68:00",
        observables=[
            dict(metric=Metric.PRESSURE_RATE, subject="Harbour City", direction=Direction.UP),
            dict(metric=Metric.LONG_BALL_SHARE, subject="Northvale", direction=Direction.UP),
        ],
    )
    return base | overrides


def test_plantable_classes_have_real_observables():
    for cause, observables in CAUSE_OBSERVABLES.items():
        assert cause.domain in ("tactical", "physical", "game_state")
        assert observables and all(o.metric in DEFAULT_THRESHOLD_KIND for o in observables)
        assert all(o.direction != Direction.FLAT for o in observables)
    # Every domain has a class the engine can plant, so every agent can be right.
    assert {c.domain for c in CAUSE_OBSERVABLES} == {"tactical", "physical", "game_state"}


def test_planted_truth_matches_its_class():
    assert PlantedTruth(**_truth()).window.end.minute == 68
    nothing = PlantedTruth(match_id="d-h-01", cause=Cause.NONE)
    assert nothing.observables == []


@pytest.mark.parametrize(
    "overrides,message",
    [
        (dict(cause=Cause.BLOCK_DEEPER), "cannot be planted"),
        (dict(team=None), "names its team, script and window"),
        (dict(observables=[]), "observables must be"),
        (dict(window="58:00-66:00"), "opens before the change began"),
        (dict(cause=Cause.NONE), "names nothing"),
    ],
)
def test_planted_truth_refuses_what_does_not_fit(overrides, message):
    with pytest.raises(ValidationError, match=message):
        PlantedTruth(**_truth(**overrides))


def test_ground_truth_fits_its_suite():
    planted = PlantedTruth(**_truth())
    nothing = PlantedTruth(match_id="d-h-01", cause=Cause.NONE)
    assert GroundTruth(suite="planted", split="heldout", entries=[planted])
    assert GroundTruth(suite="decoys", split="heldout", entries=[nothing])
    with pytest.raises(ValidationError, match="plants nothing"):
        GroundTruth(suite="decoys", split="heldout", entries=[planted])
    with pytest.raises(ValidationError, match="plants a cause"):
        GroundTruth(suite="planted", split="heldout", entries=[nothing])
    with pytest.raises(ValidationError, match="appears once"):
        GroundTruth(suite="planted", split="heldout", entries=[planted, planted])
```

Run it → fails at import.

- [ ] **Step 2: Implement.** Create `contracts/planted.py`:

```python
"""What a planted cause looks like, and the sealed record of what was planted (spec §7.1-7.3).

The observables of each plantable class are fixed here, before any script of that class
runs (spec §7.2). Ground truth records are written by the engine and read by `eval/`
alone; product code never opens the files (scripts/check_engine_isolation.py).
"""

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from contracts.clock import MatchClock, Window
from contracts.eval_run import Split, Suite
from contracts.prediction import Direction
from contracts.taxonomy import Cause, Metric

Role = Literal["team", "opponent", "unit", "player"]


class CauseObservable(BaseModel):
    """An observable of a class: the metric, whose it is, and which way the class moves it."""

    model_config = {"frozen": True}

    metric: Metric
    subject: Role
    direction: Direction


def _obs(metric: Metric, subject: Role, direction: Direction) -> CauseObservable:
    return CauseObservable(metric=metric, subject=subject, direction=direction)


UP, DOWN = Direction.UP, Direction.DOWN

# The classes the Match Engine can plant, and what each moves. Classes missing here
# (block height, formation, flank, substitution, numerical change) have no mechanism
# yet and are never planted; an agent may still name them, and precision counts it.
CAUSE_OBSERVABLES: dict[Cause, tuple[CauseObservable, ...]] = {
    Cause.PRESS_INTENSITY_UP: (
        _obs(Metric.PRESSURE_RATE, "team", UP),
        _obs(Metric.LONG_BALL_SHARE, "opponent", UP),
    ),
    Cause.PRESS_INTENSITY_DOWN: (
        _obs(Metric.PRESSURE_RATE, "team", DOWN),
        _obs(Metric.LONG_BALL_SHARE, "opponent", DOWN),
    ),
    Cause.CHASING_RESULT: (
        _obs(Metric.PRESSURE_RATE, "team", UP),
        _obs(Metric.LONG_BALL_SHARE, "team", UP),
    ),
    Cause.PROTECTING_LEAD: (
        _obs(Metric.PRESSURE_RATE, "team", DOWN),
        _obs(Metric.LONG_BALL_SHARE, "team", UP),
    ),
    Cause.UNIT_FATIGUE: (
        _obs(Metric.SPRINT_COUNT, "unit", DOWN),
        _obs(Metric.SPRINT_SPEED, "unit", DOWN),
    ),
    Cause.PLAYER_FATIGUE: (
        _obs(Metric.SPRINT_COUNT, "player", DOWN),
        _obs(Metric.SPRINT_SPEED, "player", DOWN),
    ),
}


class TruthObservable(BaseModel):
    metric: Metric
    subject: str = Field(min_length=1, description="team name, Team.unit, or player id")
    direction: Direction


class PlantedTruth(BaseModel):
    """What one suite match planted, or that it planted nothing (cause `none`)."""

    match_id: str
    cause: Cause
    team: str | None = None
    script_id: str | None = None
    started: MatchClock | None = Field(default=None, description="when the change began")
    window: Window | None = Field(default=None, description="where its effect is measured")
    observables: list[TruthObservable] = Field(default_factory=list)

    @model_validator(mode="after")
    def _complete(self) -> "PlantedTruth":
        planted = (self.team, self.script_id, self.started, self.window)
        if self.cause == Cause.NONE:
            if any(v is not None for v in planted) or self.observables:
                raise ValueError(f"{self.match_id}: a match with nothing planted names nothing")
            return self
        if self.cause not in CAUSE_OBSERVABLES:
            raise ValueError(f"{self.match_id}: {self.cause} cannot be planted")
        if any(v is None for v in planted):
            raise ValueError(f"{self.match_id}: a planted cause names its team, script and window")
        expected = [(o.metric, o.direction) for o in CAUSE_OBSERVABLES[self.cause]]
        if [(o.metric, o.direction) for o in self.observables] != expected:
            raise ValueError(f"{self.match_id}: observables must be {self.cause}'s, in order")
        if self.window.start < self.started:
            raise ValueError(f"{self.match_id}: the window opens before the change began")
        return self


class GroundTruth(BaseModel):
    """The sealed answer key for one suite split."""

    suite: Suite
    split: Split
    entries: list[PlantedTruth] = Field(min_length=1)

    @model_validator(mode="after")
    def _fits_suite(self) -> "GroundTruth":
        ids = [e.match_id for e in self.entries]
        if len(ids) != len(set(ids)):
            raise ValueError("each match appears once")
        nothing = [e.cause == Cause.NONE for e in self.entries]
        if self.suite == Suite.DECOYS and not all(nothing):
            raise ValueError("a decoy match plants nothing")
        if self.suite == Suite.PLANTED and any(nothing):
            raise ValueError("every planted-suite match plants a cause")
        return self
```

- [ ] **Step 3: Check and commit** `contracts/planted.py tests/test_contracts_planted.py`:

```bash
git commit -m "Pin what each plantable cause looks like" -m "Spec 7.2 fixes each class's observables and directions before any script of that class runs; contracts/planted.py now holds them for the six classes the engine can plant, two per domain, and the sealed ground-truth record checks every planted match against its class."
```

---

### Task 3: Let a script target a unit and wait for the score

**Files:** `engine/script.py`, `tests/test_engine_script.py`.

- [ ] **Step 1: Tests.** In `tests/test_engine_script.py`, append to the parameter list of `test_bad_interventions_are_rejected`:

```text
        ({"player": "HC-03", "set": {"stamina_decay": 10.5}}, "outside"),
        ({"unit": "defence", "set": {"press_height": 0.7}}, "not valid player parameter"),
        ({"unit": "defense", "set": {"stamina_decay": 2.0}}, "Input should be"),
        ({"player": "HC-03", "unit": "defence", "set": {"stamina_decay": 2.0}}, "not both"),
        ({"when": "drawing"}, "Input should be"),
```

and add at the end of the file:

```python
def test_a_unit_and_a_score_trigger_can_be_scripted():
    script = _script(
        scripts=[
            _intervention(unit="midfield", set={"stamina_decay": 8.0}),
            _intervention(id="s2", when="trailing", set={"press_height": 0.9}),
        ]
    )
    tired, chasing = script.scripts
    assert (tired.unit, tired.player, chasing.when) == ("midfield", None, "trailing")
```

Run → the new cases fail.

- [ ] **Step 2: Implement.** In `engine/script.py`: change `"stamina_decay": (0.0, 5.0),` to `"stamina_decay": (0.0, 10.0),`; below `PLAYER_ID` add

```python
Unit = Literal["defence", "midfield", "attack"]
Trigger = Literal["trailing", "leading"]
```

In `Intervention`, between `player` and `set`, add

```python
    unit: Unit | None = Field(default=None, description="every player of this unit")
    when: Trigger | None = Field(
        default=None, description="start at the first moment from `at` the team is trailing/leading"
    )
```

and make the start of `_known_params`

```python
        if self.player and self.unit:
            raise ValueError(f"{self.id}: name a player or a unit, not both")
        level = "player" if self.player or self.unit else "team"
        allowed = PLAYER_PARAMS if level == "player" else TEAM_PARAMS
```

(the rest of the validator is unchanged).

- [ ] **Step 3: Check and commit** `engine/script.py tests/test_engine_script.py`:

```bash
git commit -m "Let a script target a unit and wait for the score" -m "Unit fatigue needs one player parameter applied to a whole unit, and the game-state classes need a change that starts when the team trails or leads, not at a fixed minute. Fatigue strong enough to show in one match needs a stamina decay up to 10."
```

---

### Task 4: Start unit and score-triggered changes in the simulator

**Files:** `engine/params.py`, `engine/sim.py`, `tests/test_engine_params.py`, `tests/test_engine_sim.py`.

- [ ] **Step 1: Tests.** In `tests/test_engine_params.py` add `from contracts.clock import MatchClock` above `from engine.params import ParamTimeline`, and at the end:

```python
TRIGGERED = MatchScript.model_validate(
    {
        "match_id": "t03",
        "seed": 1,
        "teams": {
            "home": {"name": "Harbour City", "code": "HC", "press_height": 0.4},
            "away": {"name": "Northvale", "code": "NV"},
        },
        "scripts": [
            {
                "id": "chase",
                "at": "55:00",
                "ramp": "2m",
                "team": "home",
                "when": "trailing",
                "set": {"press_height": 0.9},
            },
            {
                "id": "legs",
                "at": "60:00",
                "team": "away",
                "unit": "defence",
                "set": {"stamina_decay": 8.0},
            },
        ],
    }
)


def test_a_unit_intervention_reaches_every_player_of_that_unit_only():
    tl = ParamTimeline(TRIGGERED)
    assert tl.player("away", "NV-02", 2, at(61), unit="defence")["stamina_decay"] == 8.0
    assert tl.player("away", "NV-07", 2, at(61), unit="midfield")["stamina_decay"] == 1.0
    assert tl.player("home", "HC-02", 2, at(61), unit="defence")["stamina_decay"] == 1.0


def test_a_score_triggered_intervention_waits_for_its_start():
    tl = ParamTimeline(TRIGGERED)
    assert tl.started == {"chase": None, "legs": MatchClock.parse("60:00")}
    assert [iv.id for iv in tl.pending()] == ["chase"]
    assert tl.team("home", 2, at(70))["press_height"] == pytest.approx(0.4)
    tl.start(tl.pending()[0], MatchClock.parse("66:00"))
    assert tl.pending() == []
    assert tl.team("home", 2, at(67))["press_height"] == pytest.approx(0.65)  # half the ramp
    assert tl.team("home", 2, at(70))["press_height"] == pytest.approx(0.9)
```

At the end of `tests/test_engine_sim.py`:

```python
def test_a_score_triggered_change_starts_when_its_condition_first_holds():
    leading = Intervention.model_validate(
        {
            "id": "sit",
            "at": "50:00",
            "team": "home",
            "when": "leading",
            "set": {"press_height": 0.1},
        }
    )
    script = M01.model_copy(update={"scripts": [leading]})
    for seed in (3, 4, 5, 6, 7, 8):
        sim = MatchSim(script, seed=seed)
        events = sim.run()
        started = sim.params.started["sit"]
        goals = [e for e in events if e.type == "goal"]

        def lead_at(clock, goals=goals):
            ours = sum(g.team == "Harbour City" and g.clock < clock for g in goals)
            return ours - sum(g.team == "Northvale" and g.clock < clock for g in goals)

        if started is None:
            later = [g.clock for g in goals if g.clock >= leading.at] + [leading.at]
            assert all(lead_at(c) <= 0 for c in later), seed
        else:
            assert started >= leading.at and lead_at(started) > 0, seed
            # nothing between `at` and the start already had them ahead at a goal
            assert all(lead_at(g.clock) <= 0 for g in goals if leading.at <= g.clock < started)
```

Run → they fail.

- [ ] **Step 2: Implement `engine/params.py`.** Replace everything from `def __init__` to the end of the file with:

```text
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

    def team(self, side: Side, period: int, s: float) -> dict[str, float]:
        values = dict(self._base[side])
        for iv in self._interventions:
            if iv.team == side and iv.player is None and iv.unit is None:
                self._apply(values, iv, period, s)
        return values

    def player(
        self, side: Side, player_id: str, period: int, s: float, unit: str | None = None
    ) -> dict[str, float]:
        values = dict(PLAYER_DEFAULTS)
        for iv in self._interventions:
            if iv.team == side and (iv.player == player_id or (unit and iv.unit == unit)):
                self._apply(values, iv, period, s)
        return values

    def _apply(self, values: dict[str, float], iv: Intervention, period: int, s: float) -> None:
        start = self.started[iv.id]
        if start is None:
            return
        p = _progress(start, iv.ramp_seconds, period, s)
        for key, target in iv.set.items():
            values[key] += (target - values[key]) * p
```

- [ ] **Step 3: Implement `engine/sim.py`.** In `_physical_minute` pass the unit: `decay = self.params.player(side, pid, self.period, start, p.unit)["stamina_decay"]`. Directly above `def _possession` add, and call `self._start_triggered()` as the first line of `_possession`:

```python
    def _start_triggered(self) -> None:
        """Start each score-triggered intervention the first time its condition holds."""
        now = clock_at(self.period, self.t)
        for iv in self.params.pending():
            if now < iv.at:
                continue
            own, them = self.score[iv.team], self.score[other(iv.team)]
            if (iv.when == "trailing" and own < them) or (iv.when == "leading" and own > them):
                self.params.start(iv, now)
```

The check runs at every possession start, which follows every goal; it draws no random numbers, so matches without triggered scripts are unchanged (the golden pin still holds).

- [ ] **Step 4: Check and commit** `engine/params.py engine/sim.py tests/test_engine_params.py tests/test_engine_sim.py`:

```bash
git commit -m "Start unit and score-triggered changes in the simulator" -m "A unit intervention reaches every player of that unit; a score-triggered one starts at the first possession from its time at which the team trails or leads, and the timeline records when, which ground truth and paired runs need. Scripts without either behave exactly as before."
```

---

### Task 5: Measure sprints per minute and judge visibility either way

**Files:** `engine/visibility.py`, `tests/test_engine_visibility.py`.

- [ ] **Step 1: Tests.** Append to `tests/test_engine_visibility.py` (adding `Metric` to its `contracts.taxonomy` import, or `from contracts.taxonomy import Metric`, and `Direction` from `contracts.prediction`; import `observable`, `sprint_count`, `sprint_speed`, `window_minutes` from `engine.visibility`):

```python
def _sprint(team, player, position, speed, clock):
    return Event(
        event_id="s",
        match_id="t01",
        clock=clock,
        wall_clock_ms=0,
        type="sprint",
        team=team,
        player_id=player,
        position=position,
        start=Point(x=30, y=30),
        end=Point(x=50, y=30),
        qualifiers={"speed_kmh": speed, "distance_m": 20.0},
    )


SPRINTS = [
    _sprint("Harbour City", "HC-02", "RB", 30.0, "10:00"),
    _sprint("Harbour City", "HC-10", "ST", 32.0, "20:00"),
    _sprint("Northvale", "NV-02", "RB", 31.0, "20:00"),
    _sprint("Harbour City", "HC-02", "RB", 28.0, "60:00"),
    Event(
        event_id="e",
        match_id="t01",
        clock="45+0:00",
        wall_clock_ms=0,
        type="period_end",
        team="Harbour City",
    ),
]
CARD = Window.model_validate("58:00-63:00")


def test_sprints_are_counted_per_minute_for_a_team_a_unit_or_a_player():
    # One sprint in 5 minutes against one in the 45-minute first half.
    assert change(sprint_count("Harbour City.defence"), SPRINTS, CARD) == pytest.approx(
        1 / 5 - 1 / 45
    )
    assert change(sprint_count("HC-10"), SPRINTS, CARD) == pytest.approx(-1 / 45)
    assert change(sprint_count("Northvale"), SPRINTS, CARD) == pytest.approx(-1 / 45)


def test_sprint_speed_is_the_mean_and_undefined_without_sprints():
    assert change(sprint_speed("Harbour City"), SPRINTS, CARD) == pytest.approx(28.0 - 31.0)
    assert math.isnan(change(sprint_speed("Northvale"), SPRINTS, CARD))


def test_a_window_spanning_half_time_is_refused():
    with pytest.raises(ValueError, match="spans half-time"):
        window_minutes(Window.model_validate("44:00-46:00"))


def test_observables_are_found_by_metric():
    assert observable(Metric.PRESSURE_RATE, "Harbour City", "Northvale")
    with pytest.raises(ValueError, match="does not measure"):
        observable(Metric.XG, "Harbour City", "Northvale")


def test_clears_in_the_story_direction():
    natural = [0.0, 2.0, 4.0]  # mean 2, sd 2
    assert clears(-2.0, natural, direction=Direction.DOWN)
    assert not clears(-1.9, natural, direction=Direction.DOWN)
    assert not clears(6.0, natural, direction=Direction.DOWN)
```

(add `import math` at the top). Run → fails at import.

- [ ] **Step 2: Implement.** In `engine/visibility.py`:
  - replace the docstring's last sentence (`Every observable here rises with its story.`) with `Separation is signed like the change: positive when the observable rose. A story clears when its change goes far enough in its own direction. Counts compared across windows of different lengths are rates per minute of play.`;
  - imports: add `from contracts.eval_run import VISIBILITY_SDS`, `from contracts.prediction import Direction`, `from contracts.taxonomy import Metric`, `from engine.teams import UNIT_OF_ROLE`;
  - replace `first_half`, `change`, `separation` and `clears` with:

```python
class PerMinute:
    """A count, compared per minute of play so that windows of different lengths compare."""

    def __init__(self, count: Callable[[list[Event], Keep], int]) -> None:
        self.count = count


def first_half(e: Event) -> bool:
    return e.clock.period == 1


def first_half_minutes(events: list[Event]) -> float:
    """The first half's played length, stoppage included, from its period_end event."""
    end = next(e for e in events if e.type == "period_end" and e.clock.period == 1)
    return end.clock.seconds_in_period / 60


def window_minutes(window: Window) -> float:
    if window.start.period != window.end.period:
        raise ValueError(f"{window} spans half-time")
    return (window.end.seconds_in_period - window.start.seconds_in_period) / 60


def change(observable: Observable | PerMinute, events: list[Event], window: Window) -> float:
    """The observable over `window` minus its first-half value, in one match."""

    def in_window(e: Event) -> bool:
        return window.contains(e.clock)

    if isinstance(observable, PerMinute):
        during = observable.count(events, in_window) / window_minutes(window)
        return during - observable.count(events, first_half) / first_half_minutes(events)
    return observable(events, in_window) - observable(events, first_half)


def separation(story: list[float], natural: list[float]) -> float:
    """Mean story change minus mean natural change, in natural standard deviations."""
    return (statistics.mean(story) - statistics.mean(natural)) / statistics.stdev(natural)


def clears(
    story_change: float,
    natural: list[float],
    sds: float = VISIBILITY_SDS,
    direction: Direction = Direction.UP,
) -> bool:
    """One match's change sits at least `sds` natural standard deviations past normal,
    in the story's direction."""
    way = 1 if direction == Direction.UP else -1
    return way * (story_change - statistics.mean(natural)) >= sds * statistics.stdev(natural)
```

  - append:

```python
def _sprints_of(subject: str) -> Callable[[Event], bool]:
    """Sprints by a team ("Harbour City"), one of its units ("Harbour City.defence") or a
    player ("HC-10")."""
    team, _, unit = subject.partition(".")
    if "-" in subject and not unit:
        return lambda e: e.type == "sprint" and e.player_id == subject
    return lambda e: (
        e.type == "sprint" and e.team == team and (not unit or UNIT_OF_ROLE[e.position] == unit)
    )


def sprint_count(subject: str) -> PerMinute:
    """Sprints by a team, unit or player, per minute of play."""
    mine = _sprints_of(subject)
    return PerMinute(lambda events, keep: sum(mine(e) and keep(e) for e in events))


def sprint_speed(subject: str) -> Observable:
    """Mean speed of a team's, unit's or player's sprints, in km/h; NaN with none."""
    mine = _sprints_of(subject)

    def speed(events: list[Event], keep: Keep) -> float:
        speeds = [e.qualifiers["speed_kmh"] for e in events if mine(e) and keep(e)]
        return statistics.mean(speeds) if speeds else float("nan")

    return speed


def observable(metric: Metric, subject: str, opponent: str) -> Observable | PerMinute:
    """The engine's measure of a contracts metric for `subject` (whose opponent is named)."""
    if metric == Metric.PRESSURE_RATE:
        return pressure_rate(subject, opponent)
    if metric == Metric.LONG_BALL_SHARE:
        return long_ball_share(subject)
    if metric == Metric.SPRINT_COUNT:
        return sprint_count(subject)
    if metric == Metric.SPRINT_SPEED:
        return sprint_speed(subject)
    raise ValueError(f"the engine does not measure {metric}")
```

- [ ] **Step 3: Check and commit** `engine/visibility.py tests/test_engine_visibility.py` (the planted-signal tests must still pass unchanged):

```bash
git commit -m "Measure sprints per minute and judge visibility either way" -m "The fatigue classes are seen in sprint counts and sprint speed, and a count over a 20-minute window only compares with the first half per minute of play. Falling observables need clears to look the story's way, and the threshold now comes from the contracts."
```

---

### Task 6: Measure each script over seed pairs and judge it

**Files:** Create `engine/paired.py`, `tests/test_engine_paired.py`.

- [ ] **Step 1: Tests.** Create `tests/test_engine_paired.py`:

```python
from pathlib import Path

import pytest

from contracts.clock import MatchClock
from contracts.eval_run import ExclusionRule
from contracts.planted import TruthObservable
from contracts.prediction import Direction
from contracts.taxonomy import Cause, Metric
from engine.paired import judge, measure, resolve, window_after
from engine.script import Intervention, load_script

ROOT = Path(__file__).resolve().parents[1]
M01 = load_script(ROOT / "engine" / "scripts" / "planted" / "m01.yaml")
PRESS = [
    TruthObservable(metric=Metric.PRESSURE_RATE, subject="Harbour City", direction=Direction.UP),
    TruthObservable(metric=Metric.LONG_BALL_SHARE, subject="Northvale", direction=Direction.UP),
]


def _with(**fields):
    iv = Intervention.model_validate({"id": "s1", "team": "home", **fields})
    return M01.model_copy(update={"scripts": [iv]})


def test_a_window_is_counted_from_the_start_of_the_change():
    window = window_after(MatchClock.parse("63:27"), (7, 27))
    assert (str(window.start), str(window.end)) == ("70:27", "90+0:27")


def test_observables_are_named_for_the_script():
    tired = Intervention.model_validate(
        {"id": "s1", "at": "60:00", "team": "away", "unit": "defence", "set": {"stamina_decay": 8}}
    )
    resolved = resolve(Cause.UNIT_FATIGUE, M01, tired)
    assert [o.subject for o in resolved] == ["Northvale.defence", "Northvale.defence"]
    press = resolve(Cause.PRESS_INTENSITY_UP, M01, M01.scripts[0])
    assert [(o.metric, o.subject) for o in press] == [
        (Metric.PRESSURE_RATE, "Harbour City"),
        (Metric.LONG_BALL_SHARE, "Northvale"),
    ]


def test_the_demo_press_counts_toward_recall():
    checks, seeds = measure(M01, "s1", PRESS, (0, 8), range(1500, 1600), pairs=20)
    assert len(seeds) == 20
    assert all(c.clears_zero and c.separates for c in checks)
    assert judge("m01", Cause.PRESS_INTENSITY_UP, checks) is None


def test_an_intervention_that_changes_nothing_is_not_observable():
    idle = _with(at="60:00", set={"press_height": 0.3})  # Harbour City's own base press
    checks, _ = measure(idle, "s1", PRESS, (0, 8), range(1500, 1600), pairs=20)
    assert all(c.ci_low == c.ci_high == 0 for c in checks)
    assert judge("idle", Cause.PRESS_INTENSITY_UP, checks).rule == ExclusionRule.NO_PAIRED_EFFECT


def test_a_change_that_never_starts_in_time_cannot_be_measured():
    late = _with(at="80:00", set={"press_height": 0.9})
    with pytest.raises(ValueError, match="starts in time on only 0 seeds"):
        measure(late, "s1", PRESS, (0, 8), range(1500, 1510), pairs=20)
```

Run → fails at import.

- [ ] **Step 2: Implement.** Create `engine/paired.py`:

```python
"""Paired runs: a script with and without one intervention, over many seeds (spec §7.2).

For every seed on which the intervention starts in time, the engine runs the match twice
and measures each observable's in-match change over a window anchored where the change
began. The paired difference gives the effect's confidence interval; the spread of the
change without the intervention gives the natural variation that separation is measured
in. From those numbers a script either counts toward recall or is excluded, and why.
"""

import math
import statistics
from collections.abc import Iterable

from contracts.clock import MatchClock, Window
from contracts.eval_run import Exclusion, ExclusionRule, ObservableCheck
from contracts.planted import CAUSE_OBSERVABLES, TruthObservable
from contracts.taxonomy import Cause
from engine.script import Intervention, MatchScript
from engine.sim import MatchSim
from engine.visibility import change, observable

Z95 = 1.96
LATEST_START = MatchClock.parse("75:00")  # later starts leave too little match to measure


def window_after(start: MatchClock, offsets: tuple[int, int]) -> Window:
    """Minutes `offsets[0]` to `offsets[1]` after `start`, in the same half."""
    base = start.minute * 60 + start.second

    def at(minutes: int) -> MatchClock:
        total = base + minutes * 60
        return MatchClock(period=start.period, minute=total // 60, second=total % 60)

    return Window(start=at(offsets[0]), end=at(offsets[1]))


def resolve(cause: Cause, script: MatchScript, intervention: Intervention) -> list[TruthObservable]:
    """The class's observables, with their subjects named for this script."""
    team = script.teams[intervention.team].name
    opponent = script.teams["away" if intervention.team == "home" else "home"].name
    subjects = {
        "team": team,
        "opponent": opponent,
        "unit": f"{team}.{intervention.unit}",
        "player": intervention.player,
    }
    return [
        TruthObservable(metric=o.metric, subject=subjects[o.subject], direction=o.direction)
        for o in CAUSE_OBSERVABLES[cause]
    ]


def _opponent(script: MatchScript, subject: str) -> str:
    names = [t.name for t in script.teams.values()]
    team = subject.partition(".")[0]
    return next((n for n in names if n != team), names[0])


def measure(
    script: MatchScript,
    script_id: str,
    observables: list[TruthObservable],
    offsets: tuple[int, int],
    seeds: Iterable[int],
    pairs: int,
) -> tuple[list[ObservableCheck], list[int]]:
    """Each observable's paired-effect interval and separation over `pairs` seeds.

    Seeds on which the intervention never starts, or starts after LATEST_START, are
    skipped; a seed with no value for one observable (no sprints in the window, say) is
    left out of that observable only.
    """
    iv = next(s for s in script.scripts if s.id == script_id)
    without = script.model_copy(update={"scripts": [s for s in script.scripts if s.id != iv.id]})
    measures = [observable(o.metric, o.subject, _opponent(script, o.subject)) for o in observables]
    story: list[list[float]] = [[] for _ in observables]
    natural: list[list[float]] = [[] for _ in observables]
    used: list[int] = []
    for seed in seeds:
        sim = MatchSim(script, seed=seed)
        events = sim.run()
        start = sim.params.started[iv.id]
        if start is None or LATEST_START < start:
            continue
        window = window_after(start, offsets)
        plain = MatchSim(without, seed=seed).run()
        for i, f in enumerate(measures):
            pair = change(f, events, window), change(f, plain, window)
            if not any(math.isnan(x) for x in pair):
                story[i].append(pair[0])
                natural[i].append(pair[1])
        used.append(seed)
        if len(used) == pairs:
            break
    if len(used) < pairs:
        raise ValueError(f"{script.match_id}: {iv.id} starts in time on only {len(used)} seeds")
    checks = []
    for o, s, n in zip(observables, story, natural, strict=True):
        diffs = [a - b for a, b in zip(s, n, strict=True)]
        half = Z95 * statistics.stdev(diffs) / math.sqrt(len(diffs))
        mean = statistics.mean(diffs)
        checks.append(
            ObservableCheck(
                metric=o.metric,
                subject=o.subject,
                direction=o.direction,
                separation=(statistics.mean(s) - statistics.mean(n)) / statistics.stdev(n),
                ci_low=mean - half,
                ci_high=mean + half,
            )
        )
    return checks, used


def judge(script_id: str, cause: Cause, checks: list[ObservableCheck]) -> Exclusion | None:
    """Spec §7.2: excluded under the first rule the numbers meet, or None if it counts."""
    if not any(c.clears_zero for c in checks):
        rule = ExclusionRule.NO_PAIRED_EFFECT
    elif not any(c.separates for c in checks):
        rule = ExclusionRule.NO_SEPARATION
    else:
        return None
    return Exclusion(script_id=script_id, cause=cause, rule=rule, observables=checks)
```

- [ ] **Step 3: Check and commit** `engine/paired.py tests/test_engine_paired.py`:

```bash
git commit -m "Measure each script over seed pairs and judge it" -m "Spec 7.2 excludes a planted script from recall when no observable's paired effect clears zero its way, or when none separates from natural variation by two standard deviations in one match. paired.py measures both from seeds on which the change starts in time, anchoring the window where it began, and names the rule a script meets."
```

---

### Task 7: Build the suites, sealed from product code

**Files:** Create `engine/suite_builder.py`, `tests/test_engine_suites.py`; modify `engine/cli.py`, `scripts/check_engine_isolation.py`, `tests/test_engine_isolation.py`, `pyproject.toml`.

- [ ] **Step 1: Tests.** Create `tests/test_engine_suites.py`:

```python
from pathlib import Path

import yaml

from contracts.eval_run import FlagSet, Split
from contracts.planted import CAUSE_OBSERVABLES, GroundTruth
from contracts.taxonomy import Cause
from engine.script import load_script
from engine.sim import MatchSim
from engine.suite_builder import decoys, dump_script, planted, write

ROOT = Path(__file__).resolve().parents[1] / "engine" / "suites"


def _load(tmp_path, text):
    path = tmp_path / "script.yaml"
    path.write_text(text, encoding="utf-8")
    return load_script(path)


def test_a_small_planted_suite_plants_every_class_unambiguously(tmp_path):
    built = planted(Split.DEV, per_class=1, pairs=20, processes=4)
    assert {t.cause for t in built.truth.entries} == set(CAUSE_OBSERVABLES)
    for script, truth in zip(built.scripts, built.truth.entries, strict=True):
        text = dump_script(script)
        # The script and its match id name a mechanism, never the class it stands for.
        assert truth.cause.value.split(".")[1] not in text and "." not in script.match_id
        sim = MatchSim(_load(tmp_path, text))
        sim.run()
        assert sim.params.started["s1"] == truth.started
    assert built.flags.scripts == [s.match_id for s in built.scripts]
    out = write(built, tmp_path)
    names = sorted(p.name for p in out.iterdir())
    assert names == ["ground_truth.yaml", "ground_truth_flags.json", "scripts"]
    reread = GroundTruth.model_validate(yaml.safe_load((out / "ground_truth.yaml").read_text()))
    assert reread == built.truth


def test_decoys_plant_nothing():
    built = decoys(Split.DEV, count=2)
    assert [t.cause for t in built.truth.entries] == [Cause.NONE, Cause.NONE]
    assert all(s.scripts == [] for s in built.scripts)


def test_the_committed_suites_are_consistent():
    for truth_path in sorted(ROOT.glob("*/*/ground_truth.yaml")):
        truth = GroundTruth.model_validate(yaml.safe_load(truth_path.read_text(encoding="utf-8")))
        scripts = {p.stem: load_script(p) for p in (truth_path.parent / "scripts").glob("*.yaml")}
        assert set(scripts) == {e.match_id for e in truth.entries}, truth_path
        flags_path = truth_path.with_name("ground_truth_flags.json")
        if flags_path.exists():
            flags = FlagSet.model_validate_json(flags_path.read_text(encoding="utf-8"))
            assert flags.split == truth.split and set(flags.scripts) == set(scripts)
        first = truth.entries[0]
        if first.started is not None:  # the record matches what the engine does
            sim = MatchSim(scripts[first.match_id])
            sim.run()
            assert sim.params.started[first.script_id] == first.started
```

Append to `tests/test_engine_isolation.py`:

```python
def test_engine_scripts_and_suites_are_sealed_too(tmp_path):
    guard = _load()
    repo = _repo(tmp_path)
    (repo / "state" / "peek.py").write_text('p = "engine/suites/planted/heldout/scripts"\n')
    (repo / "state" / "demo.py").write_text('p = "engine/scripts/planted/m01.yaml"\n')
    found = guard.scan(repo)
    assert len(found) == 2 and all("engine scripts or suites" in v for v in found)
```

Run → fails at import, and the guard test fails.

- [ ] **Step 2: Implement `engine/suite_builder.py`.**

```python
"""Planted and decoy suites, with their sealed ground truth and frozen flags (spec §7.3).

Each planted match carries one intervention whose mechanism belongs to one plantable
class; the class itself is written only to the sealed ground truth. Match ids are
opaque, so nothing a product package can see names the cause. Seeds come from the
split's own range (spec §11.1), and a match seed is used only when the planted change
is unambiguous there: a press change is not planted while the score gives the team a
game-state reason for it, and a score-triggered change must actually start in time.
"""

import random
import time
from dataclasses import dataclass
from multiprocessing import Pool
from pathlib import Path

import yaml

from contracts.clock import MatchClock
from contracts.eval_run import FlagSet, Split, Suite
from contracts.planted import CAUSE_OBSERVABLES, GroundTruth, PlantedTruth
from contracts.taxonomy import Cause
from engine.paired import LATEST_START, judge, measure, resolve, window_after
from engine.script import Intervention, MatchScript, TeamSpec
from engine.sim import MatchSim
from engine.teams import FORMATIONS, UNIT_OF_ROLE

SPLIT_BASE = {Split.DEV: 1000, Split.HELDOUT: 2000}  # spec §11.1
MATCH_OFFSET, DECOY_OFFSET, PAIRED_OFFSET = 0, 300, 500
PER_CLASS = {Split.DEV: 2, Split.HELDOUT: 5}
DECOYS = {Split.DEV: 4, Split.HELDOUT: 10}
PAIRS = 30
SCAN = 200  # seeds tried before a planted match or its pairs are given up

# Minutes after the change starts in which its effect is measured.
WINDOW = {
    Cause.PRESS_INTENSITY_UP: (0, 8),
    Cause.PRESS_INTENSITY_DOWN: (0, 8),
    Cause.CHASING_RESULT: (0, 8),
    Cause.PROTECTING_LEAD: (0, 8),
    Cause.UNIT_FATIGUE: (7, 27),
    Cause.PLAYER_FATIGUE: (7, 27),
}

HOME = TeamSpec(name="Harbour City", code="HC", formation="4-3-3")
AWAY = TeamSpec(name="Northvale", code="NV", formation="4-2-3-1")


def _clock(rng: random.Random, lo: int, hi: int) -> str:
    return f"{rng.randint(lo, hi)}:00"


def _r(rng: random.Random, lo: float, hi: float) -> float:
    return round(rng.uniform(lo, hi), 2)


def _template(cause: Cause, rng: random.Random, team: TeamSpec) -> tuple[dict, dict]:
    """(the scripted team's starting parameters, its intervention) for one class."""
    if cause == Cause.PRESS_INTENSITY_UP:
        return {"press_height": _r(rng, 0.25, 0.4)}, {
            "at": _clock(rng, 55, 65),
            "ramp": "2m",
            "set": {"press_height": _r(rng, 0.8, 0.95)},
        }
    if cause == Cause.PRESS_INTENSITY_DOWN:
        return {"press_height": _r(rng, 0.65, 0.8)}, {
            "at": _clock(rng, 55, 65),
            "ramp": "2m",
            "set": {"press_height": _r(rng, 0.15, 0.3)},
        }
    if cause == Cause.CHASING_RESULT:
        return {"press_height": _r(rng, 0.35, 0.5)}, {
            "at": "55:00",
            "when": "trailing",
            "ramp": "2m",
            "set": {"press_height": _r(rng, 0.85, 0.95), "directness": _r(rng, 0.4, 0.5)},
        }
    if cause == Cause.PROTECTING_LEAD:
        return {"press_height": _r(rng, 0.6, 0.7)}, {
            "at": "55:00",
            "when": "leading",
            "ramp": "2m",
            "set": {"press_height": _r(rng, 0.05, 0.15), "directness": _r(rng, 0.4, 0.5)},
        }
    if cause == Cause.UNIT_FATIGUE:
        return {}, {
            "at": _clock(rng, 55, 62),
            "ramp": "4m",
            "unit": rng.choice(["defence", "midfield"]),
            "set": {"stamina_decay": _r(rng, 7.0, 9.0)},
        }
    if cause == Cause.PLAYER_FATIGUE:
        outfield = [
            f"{team.code}-{i:02d}"
            for i, (role, _, _) in enumerate(FORMATIONS[team.formation], start=1)
            if UNIT_OF_ROLE[role] in ("midfield", "attack")
        ]
        return {}, {
            "at": _clock(rng, 55, 62),
            "ramp": "4m",
            "player": rng.choice(outfield),
            "set": {"stamina_decay": _r(rng, 9.0, 10.0)},
        }
    raise ValueError(f"{cause} cannot be planted")


def _teams(rng: random.Random) -> dict:
    return {
        side: spec.model_copy(
            update={"press_height": _r(rng, 0.45, 0.6), "quality": _r(rng, 0.4, 0.6)}
        )
        for side, spec in (("home", HOME), ("away", AWAY))
    }


def _score_at(events: list, team: str, clock: MatchClock) -> int:
    return sum(e.type == "goal" and e.team == team and e.clock < clock for e in events)


def _unambiguous(cause: Cause, script: MatchScript, sim: MatchSim, events: list) -> bool:
    """The planted change is the only fair answer in this match."""
    iv = script.scripts[0]
    start = sim.params.started[iv.id]
    if start is None or LATEST_START < start:
        return False
    team = script.teams[iv.team].name
    rival = next(t.name for t in script.teams.values() if t.name != team)
    lead = _score_at(events, team, iv.at) - _score_at(events, rival, iv.at)
    if cause == Cause.PRESS_INTENSITY_UP:
        return lead >= 0  # trailing would make chasing the result a fair answer
    if cause == Cause.PRESS_INTENSITY_DOWN:
        return lead <= 0  # leading would make protecting the lead a fair answer
    return True


@dataclass
class BuiltSuite:
    suite: Suite
    split: Split
    scripts: list[MatchScript]
    truth: GroundTruth
    flags: FlagSet | None = None


def _planted_match(args: tuple) -> tuple[MatchScript, PlantedTruth]:
    split, cause, k, match_id = args
    rng = random.Random(f"planted:{split}:{cause}:{k}")
    teams = _teams(rng)
    side = rng.choice(["home", "away"])
    params, fields = _template(cause, rng, teams[side])
    teams[side] = teams[side].model_copy(update=params)
    iv = Intervention.model_validate({"id": "s1", "team": side, **fields})
    first = SPLIT_BASE[split] + MATCH_OFFSET + 20 * k + 7 * list(CAUSE_OBSERVABLES).index(cause)
    for seed in range(first, first + SCAN):
        script = MatchScript(match_id=match_id, seed=seed, teams=teams, scripts=[iv])
        sim = MatchSim(script)
        events = sim.run()
        if _unambiguous(cause, script, sim, events):
            start = sim.params.started[iv.id]
            truth = PlantedTruth(
                match_id=match_id,
                cause=cause,
                team=teams[side].name,
                script_id=iv.id,
                started=start,
                window=window_after(start, WINDOW[cause]),
                observables=resolve(cause, script, iv),
            )
            return script, truth
    raise ValueError(f"{match_id}: no seed from {first} plants {cause} unambiguously")


def _flag(args: tuple):
    split, script, truth, pairs = args
    first = SPLIT_BASE[split] + PAIRED_OFFSET
    checks, seeds = measure(
        script,
        truth.script_id,
        truth.observables,
        WINDOW[truth.cause],
        range(first, first + SCAN),
        pairs,
    )
    return judge(script.match_id, truth.cause, checks), seeds


def planted(
    split: Split, per_class: int | None = None, pairs: int = PAIRS, processes: int | None = None
) -> BuiltSuite:
    """`per_class` scripts of every plantable class, in a deterministic shuffled order, each
    flagged from `pairs` seed pairs."""
    per_class = PER_CLASS[split] if per_class is None else per_class
    jobs = [(c, k) for c in CAUSE_OBSERVABLES for k in range(per_class)]
    random.Random(f"order:{split}").shuffle(jobs)
    prefix = "p-d" if split == Split.DEV else "p-h"
    args = [(split, c, k, f"{prefix}-{i:02d}") for i, (c, k) in enumerate(jobs, start=1)]
    with Pool(processes) as pool:
        built = pool.map(_planted_match, args)
        flagged = pool.map(_flag, [(split, s, t, pairs) for s, t in built])
    scripts = [s for s, _ in built]
    flags = FlagSet(
        split=split,
        scripts=[s.match_id for s in scripts],
        paired_seeds={s.match_id: seeds for s, (_, seeds) in zip(scripts, flagged, strict=True)},
        frozen_at_ms=int(time.time() * 1000),
        exclusions=[x for x, _ in flagged if x is not None],
    )
    truth = GroundTruth(suite=Suite.PLANTED, split=split, entries=[t for _, t in built])
    return BuiltSuite(Suite.PLANTED, split, scripts, truth, flags)


def decoys(split: Split, count: int | None = None) -> BuiltSuite:
    """Matches with nothing planted: natural swings only."""
    count = DECOYS[split] if count is None else count
    prefix = "d-d" if split == Split.DEV else "d-h"
    scripts, entries = [], []
    for k in range(count):
        rng = random.Random(f"decoy:{split}:{k}")
        match_id = f"{prefix}-{k + 1:02d}"
        seed = SPLIT_BASE[split] + DECOY_OFFSET + k
        scripts.append(MatchScript(match_id=match_id, seed=seed, teams=_teams(rng)))
        entries.append(PlantedTruth(match_id=match_id, cause=Cause.NONE))
    truth = GroundTruth(suite=Suite.DECOYS, split=split, entries=entries)
    return BuiltSuite(Suite.DECOYS, split, scripts, truth)


def dump_script(script: MatchScript) -> str:
    """The script as YAML in the hand-written style: clocks as quoted text."""

    def intervention(iv: Intervention) -> dict:
        out = {"id": iv.id, "at": str(iv.at), "ramp": iv.ramp, "team": iv.team}
        for key in ("player", "unit", "when"):
            if getattr(iv, key) is not None:
                out[key] = getattr(iv, key)
        return out | {"set": iv.set}

    doc = {
        "match_id": script.match_id,
        "seed": script.seed,
        "teams": {side: t.model_dump() for side, t in script.teams.items()},
        "scripts": [intervention(iv) for iv in script.scripts],
    }
    return yaml.safe_dump(doc, sort_keys=False)


def write(built: BuiltSuite, root: Path) -> Path:
    """root/<suite>/<split>/: scripts/*.yaml, ground_truth.yaml and, for the planted
    suite, ground_truth_flags.json. All of it is sealed from product code."""
    out = Path(root) / built.suite / built.split
    (out / "scripts").mkdir(parents=True, exist_ok=True)
    for script in built.scripts:
        (out / "scripts" / f"{script.match_id}.yaml").write_text(
            dump_script(script), encoding="utf-8"
        )
    truth = built.truth.model_dump(mode="json", exclude_none=True)
    for raw, entry in zip(truth["entries"], built.truth.entries, strict=True):
        if entry.started is not None:  # clocks as the text a reader writes
            raw["started"], raw["window"] = str(entry.started), str(entry.window)
    (out / "ground_truth.yaml").write_text(yaml.safe_dump(truth, sort_keys=False), encoding="utf-8")
    if built.flags is not None:
        (out / "ground_truth_flags.json").write_text(
            built.flags.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
    return out
```

- [ ] **Step 3: The `suite` command.** In `engine/cli.py` add `from contracts.eval_run import Split` and `from engine.suite_builder import decoys, planted, write` to the imports; after the `generate` parser's arguments add

```python
    suite = sub.add_parser("suite", help="build a planted or decoy suite with sealed ground truth")
    suite.add_argument("--suite", choices=["planted", "decoys"], required=True)
    suite.add_argument("--split", choices=["dev", "heldout"], required=True)
    suite.add_argument("--out", default="engine/suites", help="suites root directory")
    suite.add_argument(
        "--size", type=_seed, default=None, help="scripts per class (planted) or matches (decoys)"
    )
```

and directly after `args = parser.parse_args(argv)`:

```python
    if args.command == "suite":
        return _suite(parser, args)
```

with, above `if __name__ == "__main__":`,

```python
def _suite(parser: argparse.ArgumentParser, args: argparse.Namespace) -> int:
    split = Split(args.split)
    built = planted(split, args.size) if args.suite == "planted" else decoys(split, args.size)
    try:
        out = write(built, args.out)
    except OSError as exc:
        parser.error(f"cannot write {args.out}: {exc}")
    excluded = len(built.flags.exclusions) if built.flags else 0
    print(f"{args.suite} {args.split}: {len(built.scripts)} matches, {excluded} not observable")
    print(f"written to {out}")
    return 0
```

- [ ] **Step 4: Seal them.** In `scripts/check_engine_isolation.py`, below `GROUND_TRUTH_RE` add

```python
# A script reveals its planted moment as plainly as ground truth does.
ENGINE_DATA_RE = re.compile(r"engine/(scripts|suites)/")
```

and after the ground-truth check in `violations_in` add an `elif ENGINE_DATA_RE.search(line):` branch appending `f"{path}:{i}: references engine scripts or suites"`. In `pyproject.toml` under `[tool.hatch.build.targets.wheel]` add `exclude = ["engine/suites"]  # sealed answers never ship in a package`.

- [ ] **Step 5: Check and commit.** `uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run python scripts/check_engine_isolation.py && uv build --wheel -o /tmp/claude-1000/wheel` (the wheel lists `engine/suite_builder.py` but nothing under `engine/suites/`). Commit `engine/suite_builder.py engine/cli.py scripts/check_engine_isolation.py pyproject.toml tests/test_engine_suites.py tests/test_engine_isolation.py`:

```bash
git commit -m "Build planted and decoy suites, sealed from product code" -m "The evaluator needs matches whose causes span all three agents, with an answer key product code never sees. The builder plants one class per match from per-split seeds, only where that class is the one fair answer, writes opaque ids, sealed ground truth and frozen flags, and the guard now refuses product references to engine scripts or suites."
```

---

### Task 8: Generate and commit the suites

- [ ] **Step 1: Build.** `for s in planted decoys; do for sp in dev heldout; do uv run proofline-engine suite --suite $s --split $sp; done; done` (about 4 minutes on 12 cores). Expected: `planted dev: 12 matches, 1 not observable`, `planted heldout: 30 matches, 2 not observable`, `decoys dev: 4 matches, 0 not observable`, `decoys heldout: 10 matches, 0 not observable`. If a count differs, report it rather than changing anything to match.

- [ ] **Step 2: Check and commit.** `uv run pytest -q tests/test_engine_suites.py` (the committed-suites test now reads them). Commit `engine/suites`:

```bash
git commit -m "Add the planted and decoy suites" -m "Dev holds 12 planted and 4 decoy matches, held-out 30 and 10; the frozen flags exclude 1 dev and 2 held-out scripts whose effect is clear across seeds but too small to see in one match, which the scoreboard will list."
```

---

### Task 9: Document the suites and the new script features

- [ ] **Step 1: Spec §7.1.** After the paragraph that starts `Amendments are **batches**`, add: `An intervention can also target a whole unit with a player parameter (\`unit: defence\`), and can wait for the score (\`when: trailing\` or \`leading\`): it then starts at the first moment from \`at\` that the condition holds, and the engine records when it started.`

- [ ] **Step 2: Spec §7.3.** After the suites table add: `The planted suite plants the six classes the engine has a mechanism for (\`contracts/planted.py\`): press intensity up and down, chasing the result, protecting a lead, unit fatigue and player fatigue. Dev holds two matches per class and four decoys; held-out five per class and ten decoys. A press change is planted only where the score gives no game-state reason for it, and match ids never name the cause. Block height, formation, flank, substitution and numerical-change causes are not planted; an agent may still name them, and precision counts it. \`proofline-engine suite\` builds both suites, sealed from product code.`

- [ ] **Step 3: `DATASET.md`.** Add a section `## Planted and decoy suites` saying: where the suites live (`engine/suites/<suite>/<split>/`: `scripts/`, `ground_truth.yaml`, and for the planted suite `ground_truth_flags.json`); that the ground truth and flags are sealed from product code; the six classes and their observables (point at `contracts/planted.py`); the seed ranges (match seeds from 1000/2000, decoys +300, paired runs +500); the hygiene rule; and that the flags list every excluded script with its numbers.

- [ ] **Step 4: README and CLAUDE.md.** README's `engine/` row becomes `Match Engine: synthetic matches from tactical scripts (\`proofline-engine generate\`) and the planted and decoy suites with sealed ground truth (\`proofline-engine suite\`); never imported by product code`. In CLAUDE.md, below the `generate` command add `uv run proofline-engine suite --suite planted --split heldout   # writes engine/suites/ (sealed from product code)`.

- [ ] **Step 5: Check and commit** the four files: `uv run pytest -q tests/test_contracts.py tests/test_engine_script.py`, then

```bash
git commit -m "Document the planted suites and the new script features" -m "The spec, DATASET.md, the README and CLAUDE.md now say which classes the engine plants, how the suites are built and sealed, and how a script targets a unit or waits for the score."
```

---

### Task 10: Record what this plan resolved

- [ ] Add a status line to this plan, a "Review fixes during execution" table and the follow-ups the reviews find; in `docs/plans/2026-10-22-contract-hygiene.md` mark resolved: where flags came from, each class's observables, and the visibility threshold coming from the contracts. Verify with `uv sync --locked && uv run ruff check . && uv run ruff format --check . && uv run python scripts/check_engine_isolation.py && uv run pytest -q`, and commit both plans: `git commit -m "Record what the planted-suites plan resolved" -m "..."`.

## Review fixes during execution

| Task | Fix | Commit |
|---|---|---|
| 1 | A flag set's fields are `match_ids` and an exclusion's is `match_id`: both hold suite match ids, while a planted truth's `script_id` is the intervention inside the match. A planted run must score every match its flag set lists. Paired seeds must be distinct and inside the split's spec §11.1 range, now `SEED_RANGES` in the contracts and used by the suite builder | `a97ef83` |
| 2 | A planted truth's observables must be measured on the right subject: the team itself, its own unit, or an opponent or player that is not the team. Ground truth is kept only for the planted and decoy suites. `Role` is `SubjectRole` | `a97ef83` |
| 4 | Interventions apply in the order they actually start, so a triggered change with an early `at` but a late start is not overridden by one that began before it | `0592b8b` |
| 4 | The trigger test finds when the condition first holds, after each goal as well as before, and requires the start within 90 seconds of it | `bad2bcf` |
| 5 | Players are recognised by the player-id pattern and units by name, so a team named with a hyphen or a dot still counts its sprints; a rate without a first-half `period_end` says why it fails | `f5ba243` |
| 6 | Seeds run until every observable has the pairs asked for, so sprint speed never rests on fewer than the record claims; the interval uses the t quantile for its seed count; a window must start in the second half and end by 90:00; `resolve` refuses a class whose unit or player the intervention does not name | `382da8f` |
| 7 | The score rule that makes a class the only fair answer holds from the change's start to the end of its window, so a team protecting a lead cannot concede inside it | `86b60b5` |
| 7 | Match ids come from one seeded shuffle across suites and splits (`m417`), since `p-`/`d-` prefixes told product code whether anything was planted. Every planted match has seeds of its own (three pairs per split shared one, with identical sprint streams). Game-state changes draw `at` from 55–64' and every planted change starts by 65:00, so start time no longer tells game state apart (all ten held-out game-state matches had started at 55'). A rebuild replaces the whole suite; sizes are bounded; `dump_script` refuses amendments | `9ce5f4e` |
| 7 | The isolation guard catches `Path("engine") / "suites"` and joined spellings; the sdist excludes the suites too; dotted team names work in the opponent lookup and the planted-truth subject check; the committed-suites test re-simulates every match and checks the score rule | `5b6b8ce`, `9ce5f4e` |

The suites came out as the prototype measured, before and after the final round: dev 12 planted with one excluded (player fatigue), held-out 30 with two excluded (press down), all for no separation; 4 and 10 decoys.

## Follow-ups for later plans

> Open items are tracked in [`docs/backlog.md`](../backlog.md) from 2026-10-23; this list is kept as history.

**Evaluator**
- **One flag set per comparison.** `VariantComparison` should carry the `flag_set_id` and refuse two runs whose flag sets differ.
- **An exclusion lists its class's observables exactly.** Check an `Exclusion`'s observables against `CAUSE_OBSERVABLES`, as `PlantedTruth` already is, so one cannot leave out the observable that clears zero.
- **Recall denominators** (carried from the contract-hygiene plan): fixed metric names for headline and all-script recall, and a check that the headline's count plus the exclusions equals the all-script count.
- **Match the team, not only the class.** A press-up card about the other team must not count toward recall.
- **Name the suite version a run scored.** The scripts and ground truth have no digest an `EvalRun` can cite, as it cites its flag set.

**Engine**
- **First-half planted changes** are refused: spec §7.2 measures them against the minutes before the change, which `engine/visibility.py` does not do yet.
- **Per-observable seed counts** are not recorded: the flag set lists every seed run, and each observable rests on at least the requested pairs among them.
