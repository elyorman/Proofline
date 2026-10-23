# Contract and Hygiene Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Status:** executed on branch `contract-hygiene` in October 2026, with a spec check and a code-quality review after every task. The code blocks show each task as dispatched; the fixes listed under "Review fixes during execution" changed the code after the task named. Do not re-run it; later plans pick up the follow-ups at the end.

**Goal:** Close the contract gaps two independent reviews of `827b51b` found before anything downstream builds on them, and fix the repo hygiene they flagged.

**Architecture:** Contract changes first, each with its tests and its exported schema in the same commit: surfaced cards must carry a passing verification, predictions can say "flat", cross-examination is scored by code, the demo card's metrics exist, and evaluation runs record which planted scripts were excluded and why. Then the spec catches up (the 63' example card with the demo match's measured numbers, flat predictions and mechanical cross-examination, a fixed seed partition, no real league names), and CI and the isolation guard close two small holes.

**Tech Stack:** Python 3.12, pydantic v2, pytest, ruff, uv. No new dependency.

---

## Where this plan sits

Between the planted-signal plan (merged at `827b51b`) and the rest of plan 2. Two reviews of `827b51b` are kept locally, uncommitted. Every claim acted on here was checked against the code first. Deliberately not in this plan:

- **Making more causes plantable** (game state, block height apart from press, physical causes with tracking) and **a same-window season baseline for fatigue** are the rework of the rest of plan 2.
- **Infra for the first service deploy** (`azd-service-name` tags, a registry pull with the managed identity, Event Hubs and Web PubSub tiers) belongs to the streaming plan.
- **Team display names as identifiers** stay as they are: the names are fictional, fixed and never translated, and switching to codes would move every engine test and the golden pin for little gain.

Every code block below was run on a scratch copy of `827b51b`: the full suite passed (135 tests), ruff was clean and the isolation guard passed.

## Design decisions (review these)

- **Rule 6 in the card contract.** A full-lane card that is `verified`, `scheduled`, `shown` or `revised` must carry a `passed` or `corrected` verification. Fast-lane cards are exempt: they carry deterministic facts only and never go through the Verifier.
- **Revision history.** `revisions` lists revisions 2 up to the card's `revision`, in order; the first revision is the card itself.
- **Flat predictions.** `Direction.FLAT` holds when the change stays within `min_change` either way. It exists for counter-tests ("sprint count flat"); a change proposition on a card must still move up or down.
- **Mechanical cross-examination.** `CrossExamination` stores the counter-test's observed change, and `result` is computed: refuted when the counter-prediction holds, weakened when it reaches half its threshold (or, for flat, stays within twice its tolerance), holds otherwise. No agent sets it.
- **New metrics.** `pressure_rate` (the demo card's press proposition, since PPDA cannot carry a 5-minute window) and `channel_share_left|centre|right` (the 55' flank card), all pinned absolute.
- **Exclusion records.** `EvalRun.not_observable` lists each excluded planted script with its class, rule and every observable's direction, separation and paired-effect interval. The contract checks that the numbers fit the rule named, so a script cannot be filed under the wrong rule.
- **Cues name their insight.** Insight, update and withdrawal cues must carry `insight_id` and `insight_revision`; key-event cues need not.
- **The 63' example card** in spec §5 becomes the demo match's card with seed 4434's numbers: pressure rate 0.32 → 0.83 (n 18), Northvale long-ball share 11% → 59% (n 17). The secondary cause "chasing the result" now explains Harbour City's press, which it can (Harbour City trail 1-3), not Northvale's long balls. Fatigue is refuted by a counter-test that holds on this match: Harbour City's sprints fell too (−25% against Northvale's −34%), so the drop is the usual second-half decline. A same-window season baseline, planned for the rest of plan 2, will sharpen this later.
- **Seed partition.** 0–79 tuned the engine; 100–139 check realism and visibility and set the demo-seed medians, which makes them validation seeds; evaluation dev seeds come from 1000–1999 and held-out seeds from 2000–2999, which nothing else touches.
- **No real league names in the spec.** The header line (which also named the build tool) and three prior-art links go, so `CLAUDE.md` rule 5 holds.

## File structure

| File | Change |
|---|---|
| `contracts/taxonomy.py` | `pressure_rate`, three channel shares, their threshold kinds |
| `contracts/card.py` | Surfaced cards need a passing verification; revisions numbered; change propositions move |
| `contracts/prediction.py` | `Direction.FLAT`; `supported_by(share=)`; computed cross-examination result |
| `contracts/eval_run.py` | `ExclusionRule`, `ObservableCheck`, `Exclusion`, `EvalRun.not_observable` |
| `contracts/cue.py` | Insight-tied cues name their insight |
| `docs/*.schema.json` | Re-exported in the same commit as each contract change |
| `tests/test_contracts.py` | Tests for all of the above |
| `docs/spec.md` | §5 and §12.3 examples, §8.1 pressure rate, §9.1, §11.1, header, §24 |
| `DATASET.md` | Seed partition |
| `.github/workflows/ci.yml` | `uv sync --locked`; schema check catches new files |
| `scripts/check_engine_isolation.py`, `tests/test_engine_isolation.py` | Root-level files checked; the duplicated test replaced |
| `docs/plans/2026-10-22-planted-signal.md` | Mark the follow-ups this plan resolves; reword the support-band follow-up |

Commands (repo root): `uv run pytest -q`, `uv run ruff check . && uv run ruff format --check .`, `uv run python scripts/check_engine_isolation.py`, `uv run python scripts/export_schemas.py`. Commits: one concern each, imperative subject, a body that says why, no `Co-Authored-By` or other attribution trailer.

---

### Task 1: Add the metrics the demo cards read

**Files:** Modify `contracts/taxonomy.py`; Test `tests/test_contracts.py`; Regenerate `docs/*.schema.json`.

- [ ] **Step 1: Write the failing test.** In `tests/test_contracts.py`, change the line `from contracts.taxonomy import AgentRole, BaselineScope, Metric, MomentType, OverlayTemplate` to:

```python
from contracts.taxonomy import (
    DEFAULT_THRESHOLD_KIND,
    AgentRole,
    BaselineScope,
    Metric,
    MomentType,
    OverlayTemplate,
)
```

and add directly after `test_prediction_defaults_threshold_kind_per_metric`:

```python
def test_every_metric_has_a_pinned_threshold_kind():
    assert set(DEFAULT_THRESHOLD_KIND) == set(Metric)
    assert DEFAULT_THRESHOLD_KIND[Metric.PRESSURE_RATE] == ThresholdKind.ABSOLUTE
    assert DEFAULT_THRESHOLD_KIND[Metric.CHANNEL_SHARE_RIGHT] == ThresholdKind.ABSOLUTE
```

- [ ] **Step 2: Run it.** `uv run pytest tests/test_contracts.py -q` → fails with `AttributeError: PRESSURE_RATE`.

- [ ] **Step 3: Implement.** In `contracts/taxonomy.py`, add to `Metric` `PRESSURE_RATE = "pressure_rate"` directly after `PRESS_INTENSITY`, and `CHANNEL_SHARE_LEFT = "channel_share_left"`, `CHANNEL_SHARE_CENTRE = "channel_share_centre"`, `CHANNEL_SHARE_RIGHT = "channel_share_right"` directly after `FIELD_TILT`. In `DEFAULT_THRESHOLD_KIND`, add `Metric.PRESSURE_RATE: ThresholdKind.ABSOLUTE,` after the `PRESS_INTENSITY` entry and the three channel shares, each `ThresholdKind.ABSOLUTE`, after the `FIELD_TILT` entry.

- [ ] **Step 4: Export and check.** `uv run python scripts/export_schemas.py`, then `uv run pytest -q && uv run ruff check . && uv run ruff format --check .` → all pass; `git status` shows `docs/case.schema.json`, `docs/hypothesis.schema.json`, `docs/insight-card.schema.json`, `docs/profile.schema.json` and `docs/tool-result.schema.json` changed (they list the metric enum).

- [ ] **Step 5: Commit.**

```bash
git add contracts/taxonomy.py tests/test_contracts.py docs/*.schema.json
git commit -m "Add the pressure-rate and channel-share metrics" -m "The 63' card's press proposition moves from PPDA, which cannot carry a 5-minute window, to pressure rate, and the 55' flank card reads channel share; neither metric existed, so no tool or prediction could name them."
```

---

### Task 2: Let a card reach a surface only once verified

**Files:** Modify `contracts/card.py`; Test `tests/test_contracts.py`; Regenerate schemas.

- [ ] **Step 1: Write the failing tests.** In `tests/test_contracts.py`, add `import json` above `import re`, and add directly before `def test_cue_template_is_an_enum_everywhere():`:

```python
def _card_example():
    return json.loads(_spec_example("## 5. Insight Card"))


def test_a_card_reaches_a_surface_only_once_verified():
    card = _card_example()
    assert InsightCard.model_validate(dict(card, status="shown")).status == "shown"
    rejected = dict(
        card["verification"],
        status="rejected",
        rejection_reason="number mismatch",
        number_check="failed",
        support_level=None,
        language_level=None,
    )
    for status in ("verified", "scheduled", "shown", "revised"):
        for verification in (None, rejected):
            with pytest.raises(ValidationError, match="needs a passed or corrected verification"):
                InsightCard.model_validate(dict(card, status=status, verification=verification))
    # Fast-lane cards carry deterministic facts only and skip the Verifier (rule 6).
    fast = dict(card, lane="fast", status="shown", verification=None)
    assert InsightCard.model_validate(fast).lane == "fast"


def test_revisions_are_numbered_from_two_up_to_the_card_revision():
    card = _card_example()
    second = {"revision": 2, "at": "70:05", "reason": "events amended", "amendment_ids": ["a1"]}
    assert InsightCard.model_validate(dict(card, revision=2, revisions=[second])).revision == 2
    for revision, revisions in ((2, []), (1, [second]), (3, [second])):
        with pytest.raises(ValidationError, match="revisions must list"):
            InsightCard.model_validate(dict(card, revision=revision, revisions=revisions))
```

`_spec_example` is defined further down the file; that is fine, since tests call it at run time.

- [ ] **Step 2: Run them.** `uv run pytest tests/test_contracts.py -q` → both fail: today an unverified card validates as `shown`, and revisions are unchecked.

- [ ] **Step 3: Implement.** In `contracts/card.py`, add directly above `class InsightCard(BaseModel):`:

```python
# Statuses in which a card has reached, or is queued for, a surface (CLAUDE.md rule 6).
SURFACED = frozenset(
    {CardStatus.VERIFIED, CardStatus.SCHEDULED, CardStatus.SHOWN, CardStatus.REVISED}
)
```

and at the end of `InsightCard._consistent`, before `return self`:

```python
        if self.lane == "full" and self.status in SURFACED:
            if self.verification is None or self.verification.status == "rejected":
                raise ValueError(f"a {self.status} card needs a passed or corrected verification")
        if [r.revision for r in self.revisions] != list(range(2, self.revision + 1)):
            raise ValueError(f"revisions must list revisions 2..{self.revision} in order")
```

- [ ] **Step 4: Export and check.** As in Task 1 (the exported schemas do not change; validators are not in the schema).

- [ ] **Step 5: Commit.**

```bash
git add contracts/card.py tests/test_contracts.py
git commit -m "Let a card reach a surface only once verified" -m "A card validated as shown with no verification or a rejected one, so nothing in the contract enforced rule 6. Full-lane cards that are verified, scheduled, shown or revised now need a passed or corrected verification; fast-lane cards, which carry only deterministic facts, are exempt. Revision history is checked against the card's revision."
```

---

### Task 3: Score cross-examination by code, and let predictions say flat

**Files:** Modify `contracts/prediction.py`, `contracts/card.py`; Test `tests/test_contracts.py`; Regenerate schemas.

- [ ] **Step 1: Write the failing tests.** In `tests/test_contracts.py`, change `from contracts.prediction import Direction` to `from contracts.prediction import CrossExamination, Direction`, and add directly after `test_prediction_is_judged_on_signed_change`:

```python
def test_a_flat_prediction_holds_within_its_tolerance():
    flat = _prediction(metric=Metric.SPRINT_COUNT, direction=Direction.FLAT, min_change=0.1)
    assert flat.supported_by(0.08) and flat.supported_by(-0.1)
    assert not flat.supported_by(0.15)


def _cross_examination(observed_change):
    sprints_flat = _prediction(
        metric=Metric.SPRINT_COUNT, subject="Northvale", direction=Direction.FLAT, min_change=0.1
    )
    return CrossExamination(
        hypothesis_id="hyp-physical-01",
        challenger=AgentRole.TACTICS,
        counter_prediction=sprints_flat,
        tool_call_id="tc-8850",
        observed_change=observed_change,
        reason="sprints compared with the season average for the same minutes",
    )


def test_cross_examination_is_scored_by_its_counter_test():
    assert _cross_examination(-0.05).result == "refuted"  # the counter-prediction holds
    assert _cross_examination(-0.15).result == "weakened"  # within twice the tolerance
    assert _cross_examination(-0.30).result == "holds"
    assert _cross_examination(-0.05).model_dump()["result"] == "refuted"
```

and directly before `def test_cue_template_is_an_enum_everywhere():`:

```python
def test_change_propositions_move():
    with pytest.raises(ValidationError, match="moves up or down"):
        ChangeProposition(
            id="p1",
            metric=Metric.PRESSURE_RATE,
            subject="Harbour City",
            direction=Direction.FLAT,
            window="58:00-63:00",
            baseline=BaselineScope.FIRST_HALF,
        )
```

- [ ] **Step 2: Run them.** `uv run pytest tests/test_contracts.py -q` → the three tests fail (`Direction` has no `FLAT`).

- [ ] **Step 3: Implement.** In `contracts/prediction.py`:
  - change the pydantic import to `from pydantic import BaseModel, Field, computed_field, model_validator`;
  - add `FLAT = "flat"  # no change beyond min_change either way; predictions only` to `Direction`;
  - replace the `min_change` field with

```python
    min_change: float = Field(
        gt=0,
        description="relative fraction, absolute units, or sigmas; for flat, the tolerance",
    )
```

  - replace `supported_by` with

```python
    def supported_by(self, observed_change: float, share: float = 1.0) -> bool:
        """Mechanical verdict on a signed change.

        Up or down: the change points the predicted way by at least `share` of min_change.
        Flat: the change stays within min_change / share either way.
        """
        if self.direction == Direction.FLAT:
            return abs(observed_change) <= self.min_change / share
        signed = observed_change if self.direction == Direction.UP else -observed_change
        return signed >= share * self.min_change
```

  - replace `CrossExamination` with

```python
class CrossExamination(BaseModel):
    """A challenger's counter-test, scored by code: if the counter-prediction holds, the
    hypothesis is refuted; if it reaches half its threshold, weakened; otherwise it holds."""

    hypothesis_id: str
    challenger: AgentRole
    counter_prediction: Prediction
    tool_call_id: str
    observed_change: float = Field(description="signed, in the counter-prediction's units")
    reason: str

    @computed_field
    @property
    def result(self) -> CrossExamResult:
        if self.counter_prediction.supported_by(self.observed_change):
            return CrossExamResult.REFUTED
        if self.counter_prediction.supported_by(self.observed_change, share=0.5):
            return CrossExamResult.WEAKENED
        return CrossExamResult.HOLDS
```

  In `contracts/card.py`, add to `ChangeProposition`, after its `baseline` field:

```python
    @model_validator(mode="after")
    def _moves(self) -> "ChangeProposition":
        if self.direction == Direction.FLAT:
            raise ValueError("a change proposition moves up or down")
        return self
```

- [ ] **Step 4: Export and check.** As in Task 1; `docs/hypothesis.schema.json` and `docs/insight-card.schema.json` gain `flat`.

- [ ] **Step 5: Commit.**

```bash
git add contracts/prediction.py contracts/card.py tests/test_contracts.py docs/*.schema.json
git commit -m "Score cross-examination by code and let predictions say flat" -m "An agent set the cross-examination result freely, and a prediction could only say up or down, so the spec's own refutation, sprint count flat, could not be pre-registered. The result is now computed from the counter-test, and a flat prediction holds within its tolerance; a card's change proposition must still move."
```

---

### Task 4: Record which planted scripts were excluded, and why

**Files:** Modify `contracts/eval_run.py`; Test `tests/test_contracts.py`; Regenerate schemas.

- [ ] **Step 1: Write the failing tests.** In `tests/test_contracts.py`, add directly after `test_eval_metric_belongs_to_a_suite_the_run_covered`:

```python
def _check(**overrides):
    base = dict(
        metric=Metric.SPRINT_COUNT,
        subject="NV-03",
        direction=Direction.DOWN,
        separation=0.9,
        ci_low=-1.2,
        ci_high=-0.6,
    )
    return base | overrides


def _exclusion(rule, **check):
    return dict(
        script_id="p07-s1", cause=Cause.PLAYER_FATIGUE, rule=rule, observables=[_check(**check)]
    )


def _with_exclusions(exclusions, suite=Suite.PLANTED):
    run = _eval_run([_estimate()]).model_dump()
    metrics = [_estimate(suite=suite).model_dump()]
    return EvalRun.model_validate(
        dict(run, suites=[suite], metrics=metrics, not_observable=exclusions)
    )


def test_excluded_scripts_carry_the_numbers_that_excluded_them():
    # Its paired CI clears zero downwards, but one match cannot show it: single_match.
    run = _with_exclusions([_exclusion("single_match")])
    assert run.not_observable[0].observables[0].clears_zero
    # A CI that includes zero is excluded by the paired-effect rule first.
    assert _with_exclusions([_exclusion("paired_effect", ci_high=0.1)]).not_observable


@pytest.mark.parametrize(
    "exclusion,message",
    [
        (_exclusion("paired_effect"), "clears zero its way"),
        (_exclusion("single_match", ci_high=0.1), "paired-effect rule applies first"),
        (_exclusion("single_match", separation=2.4), "separates enough to count"),
        (_exclusion("single_match", direction=Direction.FLAT), "moves up or down"),
    ],
)
def test_an_exclusion_must_fit_its_rule(exclusion, message):
    with pytest.raises(ValidationError, match=message):
        _with_exclusions([exclusion])


def test_exclusions_belong_to_planted_runs_and_are_listed_once():
    with pytest.raises(ValidationError, match="listed once"):
        _with_exclusions([_exclusion("single_match")] * 2)
    with pytest.raises(ValidationError, match="planted suite"):
        _with_exclusions([_exclusion("single_match")], suite=Suite.DECOYS)
```

- [ ] **Step 2: Run them.** `uv run pytest tests/test_contracts.py -q` → they fail: `EvalRun` has no `not_observable` (today the extra key is silently ignored, so the first assertion fails).

- [ ] **Step 3: Implement.** In `contracts/eval_run.py`, below the pydantic import add (after one blank line):

```python
from contracts.prediction import Direction
from contracts.taxonomy import Cause, Metric

VISIBILITY_SDS = 2.0  # spec §7.2: separation a script needs on at least one observable
```

directly above `class EvalRun(BaseModel):` add:

```python
class ExclusionRule(StrEnum):
    """Spec §7.2. Each excluded script is counted once, under the first rule it meets."""

    PAIRED_EFFECT = "paired_effect"  # no observable's paired CI clears zero its way
    SINGLE_MATCH = "single_match"  # one does, but none separates by VISIBILITY_SDS


class ObservableCheck(BaseModel):
    metric: Metric
    subject: str
    direction: Direction
    separation: float = Field(description="natural sds, positive when it moves `direction`")
    ci_low: float
    ci_high: float

    @model_validator(mode="after")
    def _checkable(self) -> "ObservableCheck":
        if self.direction == Direction.FLAT:
            raise ValueError("an observable of a cause moves up or down")
        if self.ci_low > self.ci_high:
            raise ValueError("ci_low is above ci_high")
        return self

    @property
    def clears_zero(self) -> bool:
        return self.ci_low > 0 if self.direction == Direction.UP else self.ci_high < 0


class Exclusion(BaseModel):
    """A planted script left out of recall as not_observable, with the numbers why."""

    script_id: str
    cause: Cause
    rule: ExclusionRule
    observables: list[ObservableCheck] = Field(min_length=1)

    @model_validator(mode="after")
    def _rule_fits_numbers(self) -> "Exclusion":
        cleared = any(o.clears_zero for o in self.observables)
        if self.rule == ExclusionRule.PAIRED_EFFECT and cleared:
            raise ValueError(f"{self.script_id}: an observable's CI clears zero its way")
        if self.rule == ExclusionRule.SINGLE_MATCH:
            if not cleared:
                raise ValueError(f"{self.script_id}: the paired-effect rule applies first")
            if any(o.separation >= VISIBILITY_SDS for o in self.observables):
                raise ValueError(f"{self.script_id}: an observable separates enough to count")
        return self
```

in `EvalRun`, between `foundry_eval_run` and `notes`, add:

```python
    not_observable: list[Exclusion] = Field(
        default_factory=list, description="planted scripts excluded from recall (spec §7.2)"
    )
```

and after `_metrics_from_run_suites`:

```python
    @model_validator(mode="after")
    def _exclusions_from_planted_runs(self) -> "EvalRun":
        if self.not_observable and Suite.PLANTED not in self.suites:
            raise ValueError("only a run of the planted suite excludes scripts")
        ids = [x.script_id for x in self.not_observable]
        if len(ids) != len(set(ids)):
            raise ValueError("each excluded script is listed once")
        return self
```

- [ ] **Step 4: Export and check.** As in Task 1; `docs/eval-run.schema.json` gains the exclusion types.

- [ ] **Step 5: Commit.**

```bash
git add contracts/eval_run.py tests/test_contracts.py docs/*.schema.json
git commit -m "Record which planted scripts were excluded, and why" -m "Spec 7.2 lists every not_observable script with its numbers from eval_runs records, but the record had no field for them. Each exclusion now carries its class, its rule and every observable's direction, separation and paired-effect interval, and the contract checks the numbers fit the rule named."
```

---

### Task 5: Make insight cues name their insight

**Files:** Modify `contracts/cue.py`; Test `tests/test_contracts.py`.

- [ ] **Step 1: Write the failing test.** Add directly after `test_cue_slot_cannot_close_before_it_opens`:

```python
def test_cues_tied_to_an_insight_name_it():
    cue = json.loads(_spec_example("### 12.3 Broadcast Cue Feed"))
    for kind in ("insight", "update", "withdrawal"):
        with pytest.raises(ValidationError, match="names its insight_id"):
            Cue.model_validate(dict(cue, kind=kind, insight_id=None))
    key_event = dict(cue, kind="key_event", insight_id=None, insight_revision=None)
    assert Cue.model_validate(key_event).kind == "key_event"
```

- [ ] **Step 2: Run it.** → fails (no validator).

- [ ] **Step 3: Implement.** At the end of `Cue` in `contracts/cue.py`, after one blank line:

```python
    @model_validator(mode="after")
    def _names_its_insight(self) -> "Cue":
        if self.kind != CueKind.KEY_EVENT and (
            self.insight_id is None or self.insight_revision is None
        ):
            raise ValueError(f"a {self.kind} cue names its insight_id and insight_revision")
        return self
```

- [ ] **Step 4: Check.** `uv run pytest -q && uv run ruff check . && uv run ruff format --check .`.

- [ ] **Step 5: Commit.**

```bash
git add contracts/cue.py tests/test_contracts.py
git commit -m "Make insight cues name their insight" -m "An insight, update or withdrawal cue could omit the card it belongs to, which the correction path needs to cancel or replace it. Key-event cues, built from deterministic facts, still need none."
```

---

### Task 6: Show the demo match's 63' card in the spec

**Files:** Modify `docs/spec.md` (§5, §8.1, §9.1, §12.3).

- [ ] **Step 1: Edit §5.** Replace the sentence `The Insight Card is the single unit of truth every surface renders.` with `The Insight Card is the single unit of truth every surface renders. The example is the demo match's 63' card, with the numbers seed 4434 measures.` Then, in the JSON example:
  - p1: `"metric": "ppda"` → `"metric": "pressure_rate"` and `"direction": "down"` → `"direction": "up"`;
  - p4: `"effect": "p2"` → `"effect": "p1"`;
  - the first evidence entry becomes `{ "metric": "pressure_rate", "subject": "Harbour City", "window": "58:00-63:00", "value": 0.83, "baseline": { "window": "first_half", "value": 0.32 }, "n_events": 18, "tool_call_id": "tc-8841" }` (keep the existing three-line layout);
  - the second evidence entry: value `0.59`, baseline value `0.11`, `n_events` `17`;
  - the rejected alternative's reason: `"Harbour City's sprints fell too (-25%, against Northvale's -34% since the first half): the usual second-half decline, not Northvale tiring."`;
  - the analyst variant: `"Pressure rate 0.32 → 0.83 since 58'. Northvale long-ball share 11% → 59%. Consistent with the press disrupting their build-up. Fatigue ruled out: Harbour City's sprints fell too. Support: moderate."`;
  - the broadcast cue's fields line: `"stat_label": "Pressures per Northvale action", "before": 0.32, "after": 0.83 }`.

- [ ] **Step 2: Edit §12.3.** In the cue example, `"before": 11.4, "after": 6.1` → `"before": 0.32, "after": 0.83`.

- [ ] **Step 3: Edit §8.1.** Below the `Press intensity` row add:

```markdown
| Pressure rate | A team's pressures in the opponent's first 60% of the pitch per opponent on-ball action there (passes, carries and dribbles starting at x < 63 in the opponent's frame) | Build |
```

- [ ] **Step 4: Edit §9.1.** Replace `Changes are signed: a prediction holds only when the change points the predicted way by at least \`min_change\`.` with `Changes are signed: a prediction holds only when the change points the predicted way by at least \`min_change\`; a \`flat\` prediction holds when the change stays within \`min_change\` either way, which is how a counter-test says "no change".` Replace step 4 of the protocol's text `Result: holds, weakened or refuted.` with `Code scores the result from the counter-test, not any agent: refuted when the counter-prediction holds, weakened when it reaches half its threshold, holds otherwise.`

- [ ] **Step 5: Check.** `uv run pytest -q` (the spec examples are validated by `test_spec_examples_validate`; the demo-script copy by `test_the_spec_shows_the_demo_script_as_it_is`) and `grep -n "11.4\|6\.1\|ppda" docs/spec.md` → only the §8.1 PPDA row remains.

- [ ] **Step 6: Commit.**

```bash
git add docs/spec.md
git commit -m "Show the demo match's 63' card in the spec" -m "The example card quoted PPDA and long-ball numbers the engine never produced, a flat sprint count the demo match does not have, and a chasing-the-result cause pinned on Northvale, who lead 3-1. It now carries seed 4434's measured numbers, refutes fatigue with a counter-test that holds on that match, and pins the secondary cause on Harbour City's press. The protocol text says flat predictions exist and code scores cross-examination."
```

---

### Task 7: Reserve evaluation seeds nothing else touches

**Files:** Modify `docs/spec.md` (§11.1), `DATASET.md`.

- [ ] **Step 1: Edit.** In §11.1, after `Headline numbers come from the held-out split.` add: ` Engine seeds are partitioned once: 0–79 tuned the engine; 100–139 check realism and visibility and set the demo-seed medians, so they are validation seeds; the evaluation suites draw dev seeds from 1000–1999 and held-out seeds from 2000–2999, which nothing else touches.` In `DATASET.md`, replace `The visibility and realism figures use held-out seeds 100–139, which played no part in tuning the engine.` with `The visibility and realism figures use held-out seeds 100–139, which played no part in tuning the engine; the evaluation suites use seeds from 1000 up, which none of this touches (spec §11.1).`

- [ ] **Step 2: Commit.**

```bash
git add docs/spec.md DATASET.md
git commit -m "Reserve evaluation seeds nothing else touches" -m "Seeds 100-139 now gate realism, set the visibility bars and feed the demo-seed medians, which makes them validation seeds. The scoreboard's dev and held-out splits get their own ranges."
```

---

### Task 8: Keep real league names out of the spec

**Files:** Modify `docs/spec.md` (header, §24).

- [ ] **Step 1: Edit.** In the header line, drop the sponsors' names from the hackathon's name and the sentence naming the build tool; keep the rest. In §24 delete the three links whose text names a real league.

- [ ] **Step 2: Check.** A case-insensitive search of `docs/spec.md` for the removed league names and the build tool's name finds nothing.

- [ ] **Step 3: Commit.**

```bash
git add docs/spec.md
git commit -m "Keep real league names out of the spec" -m "CLAUDE.md allows a real league's name only in the README, to name the hackathon; the spec's header and three prior-art links broke that. The header also named the build tool, which the README deliberately does not."
```

---

### Task 9: Close two holes in CI and the isolation guard

**Files:** Modify `.github/workflows/ci.yml`, `scripts/check_engine_isolation.py`, `tests/test_engine_isolation.py`.

- [ ] **Step 1: Write the failing test.** In `tests/test_engine_isolation.py`, replace `test_eval_is_exempt` (which repeated `test_clean_tree_passes`) with:

```python
def test_eval_may_read_ground_truth(tmp_path):
    guard = _load()
    repo = _repo(tmp_path)
    (repo / "eval" / "truth.py").write_text('p = "engine/suites/planted/ground_truth.yaml"\n')
    assert guard.scan(repo) == []


def test_root_level_files_are_checked(tmp_path):
    guard = _load()
    repo = _repo(tmp_path)
    (repo / "app.py").write_text("import engine\n")
    found = guard.scan(repo)
    assert len(found) == 1 and "app.py" in found[0]
```

Run `uv run pytest tests/test_engine_isolation.py -q` → `test_root_level_files_are_checked` fails.

- [ ] **Step 2: Implement.** In `scripts/check_engine_isolation.py`, in the module docstring change `API under \`surfaces/\`, is product code and is checked.` to `API under \`surfaces/\` and loose files at the repo root, is product code and is checked.`, and in `scan`, directly after `found: list[str] = []`, add:

```python
    for py in sorted(root.glob("*.py")):
        found.extend(violations_in(py))
```

In `.github/workflows/ci.yml`, change `- run: uv sync` to `- run: uv sync --locked`, and in the schema step replace `git diff --exit-code -- docs/*.schema.json` with `test -z "$(git status --porcelain -- docs)" || { git status --porcelain -- docs; exit 1; }` (a new, untracked schema file now fails the check too).

- [ ] **Step 3: Check.** `uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run python scripts/check_engine_isolation.py && uv sync --locked`.

- [ ] **Step 4: Commit.**

```bash
git add .github/workflows/ci.yml scripts/check_engine_isolation.py tests/test_engine_isolation.py
git commit -m "Close two holes in CI and the isolation guard" -m "CI installed without checking the lockfile, and its schema check ignored newly exported files that were never committed. The guard skipped Python files at the repo root, and one of its tests repeated another instead of checking that eval may read ground truth."
```

---

### Task 10: Record what this plan resolved

**Files:** Modify `docs/plans/2026-10-22-planted-signal.md`, this plan.

- [ ] **Step 1: Edit the planted-signal plan.** Under its `## Follow-ups for later plans` heading add:

```markdown
> Resolved by `docs/plans/2026-10-22-contract-hygiene.md`: channel share and pressure rate in the contracts, and spec §5's example card (now the demo match's measured card, with fatigue refuted by a counter-test that holds on it).
```

and replace the bullet that starts `- **Support bands for channel share.**` with:

```markdown
- **Support bands for channel share.** Set them on the dev split, never to make the demo come out a particular way. On the demo match the corrected right-channel share is 38% against 24% in the first half (+14 points): if the bands still support that, the demo shows a revision of the 55' card rather than a withdrawal, or the seed rule is extended openly in `DATASET.md`.
```

- [ ] **Step 2: Add a status line to this plan** below its "For agentic workers" note: `> **Status:** executed in October 2026. Do not re-run it.`

- [ ] **Step 3: Verify and commit.** `uv sync --locked && uv run ruff check . && uv run ruff format --check . && uv run python scripts/check_engine_isolation.py && uv run pytest -q` (135 tests), then:

```bash
git add docs/plans/2026-10-22-planted-signal.md docs/plans/2026-10-22-contract-hygiene.md
git commit -m "Record what the contract-hygiene plan resolved" -m "The planted-signal plan's follow-ups now point at the fixes, and the support-band follow-up says the bands are set on the dev split rather than tuned to the demo."
```


---

## Review fixes during execution

| Task | Fix | Commit |
|---|---|---|
| 1 | The threshold-kind docstring says bounded shares and rates are pinned absolute | `ce0e1b3` |
| 2 | Expired and killed cards need a passing verification; rejected and withdrawn ones carry the rejected verdict; a fast-lane card must be a key event with no causes and no verification (it was a full bypass); a revised card is at revision 2 or later | `60dd4bc` |
| 3 | A counter-test cannot choose its own verdict: `check_counter_test` holds every counter on the hypothesis's metric to its threshold kind and claim (flat counters change only the baseline and are tighter than the claim; same-way counters are controls on another subject); hypotheses cannot be flat; changes and thresholds must be finite; only domain agents cross-examine; a stored result must agree with the computed one | `3c18ea6`, `e87b45c` |
| 4 | Separation is stored with the engine's sign and judged in the observable's direction, and must agree with an interval that clears zero; NaN, infinity, empty subjects and fallback causes are refused; the rules are named `no_paired_effect` and `no_separation` | `bdd36d1` |
| 5 | A cue's insight revision is at least 1; the test drops each required field and shows a key-event cue may name its fast-lane card | `45e2c4d` |
| 6 | §9.1 states exactly what `check_counter_test` enforces; the card's sprint falls use the first half's played length (−21%, −30%, not −25%, −34%), and the rejection says only what a control shows; the example hypothesis is about Northvale | `e4f5a1c` |
| 7 | Seeds 100–139 are called validation seeds wherever the demo-seed rule or the realism and visibility tests mention them | `3927840` |
| 9 | The CI schema check looks at `docs/*.schema.json` rather than all of `docs/`, which still catches a new, uncommitted schema file | `43a7264` |
| 3 | An opposite-way counter-test keeps the hypothesis's subject and window, so minutes or teams the hypothesis never mentioned cannot refute it; §9.1 states the subject-and-unit rules as the code applies them; Northvale's sprint fall is −30% with the first half's exact length | `9e26841` |

## Follow-ups for later plans

**Paired-run tooling (rest of plan 2)**
- **Where flags came from.** *Resolved by the planted-suites plan (`4fbc23c`, `a97ef83`), except that `VariantComparison` does not yet compare flag sets; that is carried there.* A frozen flag-set record (id, split, seeds, number of seed pairs, `frozen_at_ms`, the exclusions) that every planted `EvalRun` points to, frozen before either variant starts; a `VariantComparison` refuses two runs with different flag sets. An empty `not_observable` list cannot yet tell "nothing excluded" from "flags never attached".
- **Each class's observables.** *Pinned in `contracts/planted.py` by the planted-suites plan (`ea0a428`); checking an exclusion against them is carried there.* Pin them, with directions, as data in `contracts/taxonomy.py`, and check that an exclusion lists exactly its class's set: leaving out the one observable that clears zero, or recording a wrong direction, would hide a script today.
- **Recall denominators.** Fixed metric names for headline and all-script recall, and a check that the headline's count plus the exclusions equals the all-script count.
- **One threshold.** *Resolved: `engine/visibility.py` imports it (`479e689`).* `engine/visibility.py` should use `contracts.eval_run.VISIBILITY_SDS`.

**Agents and orchestration**
- **Per-metric minimum thresholds** in `docs/support-rules.md`, for hypotheses and counter-tests alike; `check_counter_test` then checks counters on other metrics, which it skips today.
- **One counter-test per challenger per hypothesis**, recorded by the orchestrator, so a challenger cannot register several and keep the one that refutes.
- **Player ids and teams.** `check_counter_test` groups a team with its units ("Northvale.defence") but not with its players ("NV-03").
- **`HypothesisTest.outcome` is still set freely.** Compute it from the prediction, as cross-examination now is.
- **The fatigue rejection's strength.** A control refutes whatever the gap; on validation seeds Harbour City's 58–63' sprints fall at least 15% in 70% of matches. The planned same-window season baseline gives the Physical agent and its challengers a sharper test.

**Ledger**
- **Re-validate a card before every write.** `InsightCard` has no `validate_assignment`, so a status set after construction skips the rule-6 gate.
- **Keep a document per card revision.** A withdrawn card replaces its earlier passing verification with the rejected one; only per-revision documents keep the history spec §10 promises.

**Surfaces**
- **Fast-lane cards** always carry `case_outcome: none`; check the lane and moment type before the outcome, so a goal is never labelled "No clear cause — normal variation". The contract still lets a fast-lane card be marked `investigating`, `cross_examined`, `verified` or `rejected`; refuse those if the Director ever sets them.

**Repo**
- The schema check does not catch a stale schema file for a model removed from `SCHEMAS`.
- When `CrossExamination` is exported, export it in serialization mode, or its computed `result` is missing from the schema although every stored record has it.
- Spec §11.1 does not yet assign seeds to `state/season_baselines.json`, which the rest of plan 2 generates; pick a range no evaluation split uses.
