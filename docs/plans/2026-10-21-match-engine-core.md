# Match Engine Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A deterministic match simulator that turns a tactical script and a seed into a realistic, versioned event stream in which each scripted mechanism (a raised press, a tiring player) measurably moves the metrics that later layers detect.

**Architecture:** A possession-chain simulator (`engine/sim.py`) drives a lightweight positional model (`engine/teams.py`) with parameters that ramp in over time (`engine/params.py`) from a YAML script (`engine/script.py`). Every random draw comes from a stream keyed by decision type and match minute (`engine/rng.py`), so a run and its counterfactual without one intervention stay aligned. Output is `events.jsonl` (one `contracts.Event` per line) plus `meta.json`, written by a `proofline-engine generate` CLI.

**Tech Stack:** Python 3.12, pydantic v2 (existing contracts), PyYAML (**new dependency; CLAUDE.md requires approval before adding it**), stdlib `random`/`hashlib`/`argparse`, pytest, ruff, uv.

---

## Where this plan sits

Gate 2 is: *a scripted match streams through Event Hubs into Cosmos and the detector fires on the planted moment.* It is split into five plans, each producing working, tested software:

1. **Match Engine core** (this plan): simulator, script DSL, mechanisms, `proofline-engine generate`.
2. **Engine proof tooling:** apply amendments (v1 feed displaced, correction batch later), paired runs with CIs and `not_observable`, realism report, planted/decoy/correction suites with sealed ground truth, tracking samples.
3. **Streaming and ledger:** Match Clock (Replay, Studio, Batch) → Event Hubs → Cosmos `events` container.
4. **State Builder and `tools_server`:** metrics incl. Rhythm as pure functions, `ToolResult`s with evidence sets, MCP catalog, `state/season_baselines.json`.
5. **Moment Detector** and the gate-2 end-to-end check.

## Design decisions (review these)

- **Coordinate frame.** Every event is in the acting team's attacking frame: x=0 its own goal line, x=105 the opponent's; y=0 the left touchline, y=68 the right, looking towards the opponent's goal. Pressing "in the opponent's first 60%" is therefore x > 42 in the pressing team's frame. Task 2 writes this into the event contract's docstring and the spec.
- **Mechanisms, not labels.** Team parameters: `press_height`, `directness`, `quality`. Player parameter: `stamina_decay`. A raised `press_height` makes pressure events more frequent and more intense in the opponent's first 60%; pressure lowers pass completion and raises the chance the opponent goes long. `stamina_decay` drains a player's energy faster, and sprint probability scales with energy².
- **Keyed randomness.** `Streams(seed).uniform("pass_length", minute)`: one generator per (decision, minute), seeded with BLAKE2b, never Python's salted `hash()`. Proven by a test that the match before an intervention is identical with and without it.
- **Amendments are parsed now and applied in plan 2.** The script's amendment filter selects events by their *true* position; the v1 feed shows them displaced by the inverse shift, and the correction batch restores truth. This replaces the spec's v1-position filter (`y_min: 50`), which would also have caught genuine right-flank carries.
- **No xG in the feed.** The engine uses its own chance-quality model to decide goals but never writes xG into events; the State Builder computes xG independently.
- **Not in this plan:** tracking samples (plan 2); clearance, duel, card and substitution events; formation changes mid-match; forced events such as a scripted goal (later engine work, driven by the planted suite's needs).

## Calibration (measured on the prototype of exactly this code)

20 seeds, m01 teams without interventions, per team per match unless noted:

| Measure | Engine | Typical top flight |
|---|---|---|
| Passes | 490 (448–545) | 400–600 |
| Pass completion | 78.4% | 75–88% |
| Shots | 14.9 | 10–16 |
| Goals per match | 2.9 | 2.6–2.9 |
| Mean shot distance | ~15 m | ~16 m |
| Sprints (>24.5 km/h) | ~330 | 250–400 |
| Events per match | ~3,000 | n/a |
| Time per match | ~0.12 s | n/a |

Paired runs, 25 seeds (with intervention minus without, 95% CI):

| Observable | Without | Effect |
|---|---|---|
| Harbour City pressures in Northvale's first 60%, 62–68' (s1) | 7.0 | +3.8 [+2.7, +5.0] |
| Northvale long-ball share, 62–68' (s1) | 15.4% | +10.4 pts [+6.0, +14.7] |
| NV-03 sprints, 66–90' (s2) | 6.3 | −0.9 [−1.3, −0.5] |
| Harbour City pressures 30–36' (control, before s1) | 7.7 | exactly 0 |

`proofline-engine generate --script engine/scripts/planted/m01.yaml` prints `m01 seed 4417: 2949 events, Harbour City 2-2 Northvale`.

## File structure

| File | Responsibility |
|---|---|
| `pyproject.toml`, `uv.lock` | Add PyYAML; package `engine`; `proofline-engine` entry point |
| `contracts/event.py` | Docstring only: the coordinate frame (schemas unchanged) |
| `docs/spec.md` | §7.1: frame sentence; the m01 script example |
| `engine/__init__.py` | Package marker and isolation reminder |
| `engine/rng.py` | Keyed deterministic random streams |
| `engine/script.py` | Script DSL: pydantic models and `load_script` |
| `engine/params.py` | Team and player parameter values over time, with ramps |
| `engine/teams.py` | Formations, line-ups, fictional names, positional model |
| `engine/sim.py` | The possession-chain simulator |
| `engine/io.py` | `events.jsonl` and `meta.json` writer and reader |
| `engine/cli.py` | `proofline-engine generate` |
| `engine/scripts/planted/m01.yaml` | The demo match script |
| `tests/test_engine_*.py` | One test file per module, plus mechanisms and realism |

Run every command from the repository root. `engine/` and `tests/` are exempt from the isolation guard; product packages must never import `engine`.

---

### Task 1: Packaging: PyYAML, the `engine` package, the CLI entry point

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock` (by `uv add`)
- Create: `engine/__init__.py`

- [ ] **Step 1: Add PyYAML**

Run: `uv add "pyyaml>=6"`
Expected: `pyproject.toml` dependencies now list `"pyyaml>=6"`; `uv.lock` updated.

- [ ] **Step 2: Package `engine` and register the CLI**

In `pyproject.toml`, change the wheel packages line:

```toml
[tool.hatch.build.targets.wheel]
packages = ["contracts", "engine"]
```

and add this block directly above `[build-system]`:

```toml
[project.scripts]
proofline-engine = "engine.cli:main"
```

- [ ] **Step 3: Create the package**

`engine/__init__.py`:

```python
"""Match Engine: synthetic matches with sealed ground truth. Never imported by product code."""
```

- [ ] **Step 4: Sync and check imports**

Run: `uv sync && uv run python -c "import yaml, engine; print('ok')"`
Expected: `ok`

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock engine/__init__.py
git commit -m "Add the engine package and PyYAML for tactical scripts" -m "The Match Engine reads tactical scripts written in YAML, as spec 7.1 shows, and ships a proofline-engine command."
```

---

### Task 2: Write the coordinate frame into the event contract and the spec

Contracts first: every later layer depends on what x and y mean.

**Files:**
- Modify: `contracts/event.py:1-5` (module docstring only)
- Modify: `docs/spec.md` §7.1

- [ ] **Step 1: Replace the module docstring of `contracts/event.py`**

Old:

```python
"""Match event contract. Every event is versioned; amendments bump `version`.

Coordinates are the truth: `zone` is derived from start/end x/y by the State
Builder and is only a cache. An amendment that relocates events changes x/y.
"""
```

New:

```python
"""Match event contract. Every event is versioned; amendments bump `version`.

Coordinates are the truth, in the acting team's attacking frame: x=0 is its own
goal line and x=105 the opponent's; y=0 is the left touchline and y=68 the right,
looking towards the opponent's goal. Tracking samples use the player's own team
frame. Pitch zones are derived from x/y by the State Builder; an amendment that
relocates events changes x/y.
"""
```

- [ ] **Step 2: Confirm the exported schemas do not change**

Run: `uv run python scripts/export_schemas.py && git diff --exit-code -- 'docs/*.schema.json'`
Expected: exit code 0 (a module docstring is not part of any schema).

- [ ] **Step 3: Update spec §7.1**

In `docs/spec.md`, at the end of the line that starts `**Every event carries:**`, after `never stored as input.`, append:

```markdown
 Coordinates are in the acting team's attacking frame: x=0 its own goal line, x=105 the opponent's; y=0 the left touchline and y=68 the right, looking towards the opponent's goal.
```

Then replace the body of the YAML block that starts `match_id: m01` (everything between its opening and closing fences) with the demo script, which Task 4 also saves as `engine/scripts/planted/m01.yaml`:

```yaml
# Demo match. Mechanisms only: which cause each intervention represents lives in
# the planted suite's sealed ground truth, never here.
match_id: m01
seed: 4417
teams:
  home: { name: "Harbour City", code: HC, formation: "4-3-3", press_height: 0.45 }
  away: { name: "Northvale", code: NV, formation: "4-2-3-1", press_height: 0.55 }

scripts:
  - id: s1
    at: "60:00"
    ramp: "3m"
    team: home
    set: { press_height: 0.75 }

  - id: s2
    at: "62:00"
    ramp: "6m"
    team: away
    player: "NV-03"
    set: { stamina_decay: 2.5 }

amendments:
  - id: a1
    at: "68:00"   # after the 63' press card, so the demo shows a published card withdrawn
    batch:
      # Selects carries by their true position; the v1 feed shows them 18 m to the right.
      filter: { type: carry, team: away, window: "48:00-55:00", y_min: 32, y_max: 50 }
      shift: { dy_m: -18 }
    reason: "provider coordinate recalibration"
```

- [ ] **Step 4: Commit**

```bash
git add contracts/event.py docs/spec.md
git commit -m "Define the event coordinate frame" -m "Metrics such as PPDA depend on which half an action is in; every event now states it uses the acting team's attacking frame. The spec's script example matches the engine's DSL, and its amendment filter selects events by true position so genuine right-flank carries are not corrected by mistake."
```

---

### Task 3: Keyed random streams

**Files:**
- Create: `engine/rng.py`
- Test: `tests/test_engine_rng.py`

- [ ] **Step 1: Write the failing test**

`tests/test_engine_rng.py`:

```python
from engine.rng import Streams


def test_same_seed_gives_same_draws():
    a, b = Streams(7), Streams(7)
    assert [a.uniform("pass_length", 61) for _ in range(5)] == [
        b.uniform("pass_length", 61) for _ in range(5)
    ]


def test_extra_draws_do_not_shift_other_minutes_or_decisions():
    plain, busy = Streams(7), Streams(7)
    for _ in range(50):  # e.g. an intervention adds passes in minute 61
        busy.uniform("pass_length", 61)
    assert plain.uniform("pass_length", 62) == busy.uniform("pass_length", 62)
    assert plain.uniform("shot_outcome", 61) == busy.uniform("shot_outcome", 61)


def test_different_seeds_differ():
    assert Streams(1).uniform("pass_length", 10) != Streams(2).uniform("pass_length", 10)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_engine_rng.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'engine.rng'`

- [ ] **Step 3: Implement**

`engine/rng.py`:

```python
"""Deterministic random streams keyed by decision type and match-minute bucket.

A draw for "pass_length" in minute 61 comes from its own generator, seeded from
(match seed, decision, minute). A script that changes how many passes happen in
minute 61 leaves every other minute's draws untouched, which keeps a run and its
counterfactual aligned (spec §7.2).
"""

import hashlib
import random


class Streams:
    def __init__(self, seed: int) -> None:
        self.seed = seed
        self._generators: dict[tuple[str, int], random.Random] = {}

    def _gen(self, decision: str, minute: int) -> random.Random:
        key = (decision, minute)
        gen = self._generators.get(key)
        if gen is None:
            text = f"{self.seed}:{decision}@{minute}".encode()
            digest = hashlib.blake2b(text, digest_size=8).digest()
            gen = random.Random(int.from_bytes(digest, "big"))
            self._generators[key] = gen
        return gen

    def uniform(self, decision: str, minute: int, low: float = 0.0, high: float = 1.0) -> float:
        return self._gen(decision, minute).uniform(low, high)

    def normal(self, decision: str, minute: int, mu: float, sigma: float) -> float:
        return self._gen(decision, minute).normalvariate(mu, sigma)

    def chance(self, decision: str, minute: int, p: float) -> bool:
        return self._gen(decision, minute).random() < p
```

- [ ] **Step 4: Run it to verify it passes**

Run: `uv run pytest tests/test_engine_rng.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add engine/rng.py tests/test_engine_rng.py
git commit -m "Add keyed random streams for the match engine" -m "Draws are keyed by decision and match minute so a run without one intervention stays aligned with the run that has it, which paired runs rely on."
```

---

### Task 4: Script DSL and the demo match script

**Files:**
- Create: `engine/script.py`
- Create: `engine/scripts/planted/m01.yaml`
- Test: `tests/test_engine_script.py`

- [ ] **Step 1: Write the failing test**

`tests/test_engine_script.py`:

```python
from pathlib import Path

import pytest
from pydantic import ValidationError

from engine.script import MatchScript, load_script

M01 = Path(__file__).resolve().parents[1] / "engine" / "scripts" / "planted" / "m01.yaml"


def _script(**overrides):
    base = {
        "match_id": "t01",
        "seed": 1,
        "teams": {
            "home": {"name": "Harbour City", "code": "HC"},
            "away": {"name": "Northvale", "code": "NV"},
        },
    }
    base.update(overrides)
    return MatchScript.model_validate(base)


def test_demo_script_loads():
    script = load_script(M01)
    s1, s2 = script.scripts
    assert (s1.at.period, s1.at.minute, s1.ramp_seconds) == (2, 60, 180)
    assert s2.player == "NV-03"
    assert script.amendments[0].batch.shift.dy_m == -18


def test_unknown_parameter_is_rejected():
    with pytest.raises(ValidationError):
        _script(scripts=[{"id": "s1", "at": "60:00", "team": "home", "set": {"pres": 0.7}}])


def test_player_must_be_on_the_named_team():
    player_on_wrong_team = {
        "id": "s1",
        "at": "60:00",
        "team": "home",
        "player": "NV-03",
        "set": {"stamina_decay": 2.0},
    }
    with pytest.raises(ValidationError):
        _script(scripts=[player_on_wrong_team])


def test_unquoted_yaml_time_is_rejected():
    # YAML reads an unquoted 60:00 as the integer 3600; the clock must refuse it.
    with pytest.raises(ValidationError):
        _script(scripts=[{"id": "s1", "at": 3600, "team": "home", "set": {"press_height": 0.7}}])
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_engine_script.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'engine.script'`

- [ ] **Step 3: Write the demo script**

`engine/scripts/planted/m01.yaml` (times must be quoted: YAML reads `60:00` as the integer 3600):

```yaml
# Demo match. Mechanisms only: which cause each intervention represents lives in
# the planted suite's sealed ground truth, never here.
match_id: m01
seed: 4417
teams:
  home: { name: "Harbour City", code: HC, formation: "4-3-3", press_height: 0.45 }
  away: { name: "Northvale", code: NV, formation: "4-2-3-1", press_height: 0.55 }

scripts:
  - id: s1
    at: "60:00"
    ramp: "3m"
    team: home
    set: { press_height: 0.75 }

  - id: s2
    at: "62:00"
    ramp: "6m"
    team: away
    player: "NV-03"
    set: { stamina_decay: 2.5 }

amendments:
  - id: a1
    at: "68:00"   # after the 63' press card, so the demo shows a published card withdrawn
    batch:
      # Selects carries by their true position; the v1 feed shows them 18 m to the right.
      filter: { type: carry, team: away, window: "48:00-55:00", y_min: 32, y_max: 50 }
      shift: { dy_m: -18 }
    reason: "provider coordinate recalibration"
```

- [ ] **Step 4: Implement the DSL**

`engine/script.py`:

```python
"""Tactical script DSL: mechanisms, not labels (spec §7.1).

A script names two teams and their starting parameters, then interventions that
ramp a parameter to a new value from a match time. Cause-taxonomy names never
appear here; the mapping from an intervention to a cause lives in the suite's
sealed ground-truth file, which only eval/ reads.
"""

import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from contracts.clock import MatchClock, Window
from contracts.event import CoordinateShift

Side = Literal["home", "away"]
TEAM_PARAMS = frozenset({"press_height", "directness", "quality"})
PLAYER_PARAMS = frozenset({"stamina_decay"})
_RAMP_RE = re.compile(r"^(\d+)(m|s)$")


class TeamSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    code: str = Field(pattern=r"^[A-Z]{2}$", description="player id prefix, e.g. HC")
    formation: Literal["4-3-3", "4-2-3-1", "4-4-2", "3-5-2"] = "4-3-3"
    press_height: float = Field(default=0.5, ge=0, le=1)
    directness: float = Field(default=0.08, ge=0, le=1)
    quality: float = Field(default=0.5, ge=0, le=1)


class Intervention(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    at: MatchClock
    ramp: str = Field(default="0m", pattern=_RAMP_RE.pattern)
    team: Side
    player: str | None = None
    set: dict[str, float] = Field(min_length=1)

    @property
    def ramp_seconds(self) -> int:
        amount, unit = _RAMP_RE.match(self.ramp).groups()
        return int(amount) * (60 if unit == "m" else 1)

    @model_validator(mode="after")
    def _known_params(self) -> "Intervention":
        allowed = PLAYER_PARAMS if self.player else TEAM_PARAMS
        unknown = sorted(set(self.set) - allowed)
        if unknown:
            raise ValueError(f"{self.id}: unknown parameter(s) {unknown}")
        return self


class AmendmentFilter(BaseModel):
    """Selects events by their true position; v1 of the feed shows them displaced."""

    model_config = ConfigDict(extra="forbid")

    type: str
    team: Side
    window: Window
    y_min: float = Field(default=0, ge=0, le=68)
    y_max: float = Field(default=68, ge=0, le=68)


class AmendmentBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filter: AmendmentFilter
    shift: CoordinateShift


class AmendmentSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    at: MatchClock
    batch: AmendmentBatch
    reason: str


class MatchScript(BaseModel):
    model_config = ConfigDict(extra="forbid")

    match_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    seed: int = Field(ge=0)
    teams: dict[Side, TeamSpec]
    scripts: list[Intervention] = Field(default_factory=list)
    amendments: list[AmendmentSpec] = Field(default_factory=list)

    @model_validator(mode="after")
    def _consistent(self) -> "MatchScript":
        if set(self.teams) != {"home", "away"}:
            raise ValueError("a script needs exactly a home and an away team")
        if self.teams["home"].code == self.teams["away"].code:
            raise ValueError("home and away need different player-id codes")
        ids = [s.id for s in self.scripts] + [a.id for a in self.amendments]
        if len(ids) != len(set(ids)):
            raise ValueError("script and amendment ids must be unique")
        for s in self.scripts:
            if s.player and not s.player.startswith(f"{self.teams[s.team].code}-"):
                raise ValueError(f"{s.id}: player {s.player} is not on the {s.team} team")
        return self


def load_script(path: str | Path) -> MatchScript:
    return MatchScript.model_validate(yaml.safe_load(Path(path).read_text(encoding="utf-8")))
```

- [ ] **Step 5: Run it to verify it passes**

Run: `uv run pytest tests/test_engine_script.py -v`
Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add engine/script.py engine/scripts/planted/m01.yaml tests/test_engine_script.py
git commit -m "Add the tactical script DSL and the demo match script" -m "Scripts declare mechanisms with ramps, never cause labels, so the mapping to causes can stay sealed in ground truth. Unknown parameters, players on the wrong team and unquoted YAML times are rejected at load."
```

---

### Task 5: Parameter timeline with ramps

**Files:**
- Create: `engine/params.py`
- Test: `tests/test_engine_params.py`

- [ ] **Step 1: Write the failing test**

`tests/test_engine_params.py`:

```python
import pytest

from engine.params import ParamTimeline
from engine.script import MatchScript

SCRIPT = MatchScript.model_validate(
    {
        "match_id": "t01",
        "seed": 1,
        "teams": {
            "home": {"name": "Harbour City", "code": "HC", "press_height": 0.45},
            "away": {"name": "Northvale", "code": "NV"},
        },
        "scripts": [
            {
                "id": "s1",
                "at": "60:00",
                "ramp": "3m",
                "team": "home",
                "set": {"press_height": 0.75},
            },
            {
                "id": "s2",
                "at": "62:00",
                "ramp": "6m",
                "team": "away",
                "player": "NV-03",
                "set": {"stamina_decay": 2.5},
            },
        ],
    }
)
TL = ParamTimeline(SCRIPT)
SECOND_HALF = 45 * 60


def at(minute: float) -> float:
    """Seconds into the second half for a display minute."""
    return minute * 60 - SECOND_HALF


def test_value_is_base_before_the_intervention():
    assert TL.team("home", 2, at(59.9))["press_height"] == pytest.approx(0.45)
    assert TL.team("home", 1, 30 * 60)["press_height"] == pytest.approx(0.45)


def test_value_ramps_linearly_then_holds():
    assert TL.team("home", 2, at(61.5))["press_height"] == pytest.approx(0.60)
    assert TL.team("home", 2, at(63))["press_height"] == pytest.approx(0.75)
    assert TL.team("home", 2, at(85))["press_height"] == pytest.approx(0.75)


def test_other_team_and_players_are_untouched():
    assert TL.team("away", 2, at(70))["press_height"] == pytest.approx(0.5)
    assert TL.player("away", "NV-04", 2, at(70))["stamina_decay"] == pytest.approx(1.0)


def test_player_parameter_ramps():
    assert TL.player("away", "NV-03", 2, at(65))["stamina_decay"] == pytest.approx(1.75)
    assert TL.player("away", "NV-03", 2, at(70))["stamina_decay"] == pytest.approx(2.5)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_engine_params.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'engine.params'`

- [ ] **Step 3: Implement**

`engine/params.py`:

```python
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
```

- [ ] **Step 4: Run it to verify it passes**

Run: `uv run pytest tests/test_engine_params.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add engine/params.py tests/test_engine_params.py
git commit -m "Ramp script parameters in over match time" -m "Spec 7.1 has every change ramp in over a few minutes; a linear ramp within the intervention's period gives the detector a realistic onset rather than a step."
```

---

### Task 6: Formations, line-ups and the positional model

**Files:**
- Create: `engine/teams.py`
- Test: `tests/test_engine_teams.py`

- [ ] **Step 1: Write the failing test**

`tests/test_engine_teams.py`:

```python
from engine.script import TeamSpec
from engine.teams import FORMATIONS, build_lineup, position

NORTHVALE = TeamSpec(name="Northvale", code="NV", formation="4-2-3-1")


def test_every_formation_fields_eleven_with_one_keeper():
    for roles in FORMATIONS.values():
        assert len(roles) == 11
        assert [r for r, _, _ in roles].count("GK") == 1


def test_lineup_ids_names_and_units():
    lineup = build_lineup(NORTHVALE)
    assert [p.player_id for p in lineup][:3] == ["NV-01", "NV-02", "NV-03"]
    assert lineup[2].role == "RCB" and lineup[2].unit == "defence"
    assert all(p.name for p in lineup)


def test_a_higher_press_pushes_the_defensive_block_up():
    rcb = build_lineup(NORTHVALE)[2]
    low, _ = position(rcb, attacking=False, press_height=0.3, ball=(50, 34))
    high, _ = position(rcb, attacking=False, press_height=0.8, ball=(50, 34))
    assert high > low


def test_positions_stay_on_the_pitch():
    for p in build_lineup(NORTHVALE):
        for attacking in (True, False):
            x, y = position(p, attacking=attacking, press_height=1.0, ball=(100, 68))
            assert 0 <= x <= 105 and 0 <= y <= 68
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_engine_teams.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'engine.teams'`

- [ ] **Step 3: Implement**

`engine/teams.py` (player names are invented; never use a real player's name):

```python
"""Formations, line-ups and where players stand (the lightweight positional model).

Coordinates are in each team's own attacking frame: x=0 is its own goal line and
x=105 the opponent's; y=0 is the left touchline and y=68 the right, looking
towards the opponent's goal. Every event a team performs uses that team's frame.
"""

from dataclasses import dataclass

from engine.script import TeamSpec

FORMATIONS: dict[str, list[tuple[str, float, float]]] = {
    "4-3-3": [
        ("GK", 5, 34),
        ("RB", 32, 58),
        ("RCB", 26, 43),
        ("LCB", 26, 25),
        ("LB", 32, 10),
        ("RCM", 50, 48),
        ("CM", 45, 34),
        ("LCM", 50, 20),
        ("RW", 74, 60),
        ("ST", 80, 34),
        ("LW", 74, 8),
    ],
    "4-2-3-1": [
        ("GK", 5, 34),
        ("RB", 32, 58),
        ("RCB", 26, 43),
        ("LCB", 26, 25),
        ("LB", 32, 10),
        ("RDM", 44, 42),
        ("LDM", 44, 26),
        ("RAM", 64, 56),
        ("CAM", 66, 34),
        ("LAM", 64, 12),
        ("ST", 80, 34),
    ],
    "4-4-2": [
        ("GK", 5, 34),
        ("RB", 32, 58),
        ("RCB", 26, 43),
        ("LCB", 26, 25),
        ("LB", 32, 10),
        ("RM", 56, 58),
        ("RCM", 48, 42),
        ("LCM", 48, 26),
        ("LM", 56, 10),
        ("RS", 76, 42),
        ("LS", 76, 26),
    ],
    "3-5-2": [
        ("GK", 5, 34),
        ("RCB", 27, 48),
        ("CB", 25, 34),
        ("LCB", 27, 20),
        ("RWB", 52, 62),
        ("RCM", 48, 44),
        ("CM", 44, 34),
        ("LCM", 48, 24),
        ("LWB", 52, 6),
        ("RS", 76, 42),
        ("LS", 76, 26),
    ],
}

UNIT_OF_ROLE = {
    "GK": "goalkeeper",
    **dict.fromkeys(("RB", "RCB", "CB", "LCB", "LB", "RWB", "LWB"), "defence"),
    **dict.fromkeys(
        ("RCM", "CM", "LCM", "RDM", "LDM", "RAM", "CAM", "LAM", "RM", "LM"), "midfield"
    ),
    **dict.fromkeys(("RW", "ST", "LW", "RS", "LS"), "attack"),
}

# Off-ball sprints per minute at full energy, by unit.
SPRINT_RATE = {"goalkeeper": 0.02, "defence": 0.40, "midfield": 0.45, "attack": 0.55}

# Fictional surnames for the two curated clubs; other codes get numbered names.
NAMES = {
    "HC": [
        "Arvenne",
        "Bostrik",
        "Callodan",
        "Derrowe",
        "Eskmoor",
        "Farrelin",
        "Gollan",
        "Haverick",
        "Ilsom",
        "Jarrent",
        "Kesterby",
    ],
    "NV": [
        "Quillon",
        "Rastor",
        "Sevrin",
        "Tallowen",
        "Udrick",
        "Valcourt",
        "Wenlo",
        "Yarrick",
        "Zandor",
        "Ambrel",
        "Brennow",
    ],
}


@dataclass
class Player:
    player_id: str
    name: str
    role: str
    unit: str
    base_x: float
    base_y: float
    energy: float = 1.0


def build_lineup(team: TeamSpec) -> list[Player]:
    names = NAMES.get(team.code, [])
    lineup = []
    for i, (role, x, y) in enumerate(FORMATIONS[team.formation], start=1):
        name = names[i - 1] if i <= len(names) else f"{team.code} {i:02d}"
        lineup.append(Player(f"{team.code}-{i:02d}", name, role, UNIT_OF_ROLE[role], x, y))
    return lineup


def position(
    player: Player, *, attacking: bool, press_height: float, ball: tuple[float, float]
) -> tuple[float, float]:
    """Where a player stands right now, in his own team's frame."""
    if player.role == "GK":
        return (8.0 if attacking else 4.0), 34.0
    if attacking:
        x = player.base_x + 10
    else:
        x = player.base_x * (0.65 + 0.6 * press_height)  # a high press pushes the block up
    y = player.base_y + 0.25 * (ball[1] - 34)
    return min(max(x, 1.0), 104.0), min(max(y, 1.0), 67.0)
```

- [ ] **Step 4: Run it to verify it passes**

Run: `uv run pytest tests/test_engine_teams.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add engine/teams.py tests/test_engine_teams.py
git commit -m "Add formations and the positional model" -m "Events and player positions must agree, so actors, receivers and pressers are chosen from where each player stands; a higher press pushes the defensive block up."
```

---

### Task 7: The possession-chain simulator

The three test files below all fail until `engine/sim.py` exists. The mechanism tests run paired seeds (about 8 s); the realism test checks calibration (about 1 s).

**Files:**
- Create: `engine/sim.py`
- Test: `tests/test_engine_sim.py`
- Test: `tests/test_engine_mechanisms.py`
- Test: `tests/test_engine_realism.py`

- [ ] **Step 1: Write the failing behaviour tests**

`tests/test_engine_sim.py`:

```python
from pathlib import Path

from engine.script import load_script
from engine.sim import MatchSim

M01_PATH = Path(__file__).resolve().parents[1] / "engine" / "scripts" / "planted" / "m01.yaml"
M01 = load_script(M01_PATH)


def _dump(events):
    return [e.model_dump_json() for e in events]


def test_same_script_and_seed_is_deterministic():
    assert _dump(MatchSim(M01, seed=3).run()) == _dump(MatchSim(M01, seed=3).run())


def test_seed_changes_the_match():
    assert _dump(MatchSim(M01, seed=3).run()) != _dump(MatchSim(M01, seed=4).run())


def test_events_are_ordered_with_sequential_ids():
    events = MatchSim(M01, seed=3).run()
    assert [e.event_id for e in events] == [f"m01-{i:05d}" for i in range(1, len(events) + 1)]
    keys = [e.clock.sort_key for e in events]
    assert keys == sorted(keys)


def test_two_periods_with_stoppage_time():
    events = MatchSim(M01, seed=3).run()
    markers = [e.type for e in events if e.type in ("period_start", "period_end")]
    assert markers == ["period_start", "period_end", "period_start", "period_end"]
    assert any(e.clock.period == 1 and e.clock.stoppage for e in events)


def test_every_player_is_on_a_roster():
    sim = MatchSim(M01, seed=3)
    events = sim.run()
    roster = {p.player_id for side in sim.lineups.values() for p in side}
    assert {e.player_id for e in events if e.player_id} <= roster
    assert {e.team for e in events} == {"Harbour City", "Northvale"}


def test_intervention_leaves_the_match_before_it_untouched():
    without_s1 = M01.model_copy(update={"scripts": [s for s in M01.scripts if s.id != "s1"]})

    def before_60(events):
        return _dump([e for e in events if e.clock.minute < 60])

    assert before_60(MatchSim(M01, seed=3).run()) == before_60(MatchSim(without_s1, seed=3).run())
```

- [ ] **Step 2: Write the failing mechanism tests**

`tests/test_engine_mechanisms.py`:

```python
"""Paired runs show each scripted mechanism moves its observable (spec §7.2)."""

import statistics
from pathlib import Path

from engine.script import load_script
from engine.sim import MatchSim

M01_PATH = Path(__file__).resolve().parents[1] / "engine" / "scripts" / "planted" / "m01.yaml"
M01 = load_script(M01_PATH)
SEEDS = range(12)


def _without(sid):
    return M01.model_copy(update={"scripts": [s for s in M01.scripts if s.id != sid]})


def _paired_ci(sid, observable):
    """Mean with-minus-without difference over seeds, with a normal 95% CI."""
    diffs = [
        observable(MatchSim(M01, seed=s).run()) - observable(MatchSim(_without(sid), seed=s).run())
        for s in SEEDS
    ]
    mean = statistics.mean(diffs)
    half = 1.96 * statistics.stdev(diffs) / len(diffs) ** 0.5
    return mean - half, mean + half


def _in(e, lo, hi):
    return lo <= e.clock.minute < hi


def hc_pressures_in_nv_half(events):
    # Harbour City pressures in Northvale's first 60% are at x > 42 in Harbour City's frame.
    return sum(
        e.type == "pressure" and e.team == "Harbour City" and e.start.x > 42 and _in(e, 62, 68)
        for e in events
    )


def nv_long_ball_share(events):
    passes = [e for e in events if e.type == "pass" and e.team == "Northvale" and _in(e, 62, 68)]
    return sum(p.pass_q.distance_m > 30 for p in passes) / len(passes)


def nv03_sprints(events):
    return sum(e.type == "sprint" and e.player_id == "NV-03" and _in(e, 66, 90) for e in events)


def test_raised_press_means_more_pressure():
    low, _ = _paired_ci("s1", hc_pressures_in_nv_half)
    assert low > 0


def test_raised_press_pushes_the_opponent_long():
    low, _ = _paired_ci("s1", nv_long_ball_share)
    assert low > 0


def test_stamina_decay_costs_sprints():
    _, high = _paired_ci("s2", nv03_sprints)
    assert high < 0
```

- [ ] **Step 3: Write the failing realism test**

`tests/test_engine_realism.py`:

```python
"""Match totals stay within typical top-flight ranges (spec §7.3 realism controls)."""

import statistics
from pathlib import Path

from engine.script import load_script
from engine.sim import MatchSim

M01_PATH = Path(__file__).resolve().parents[1] / "engine" / "scripts" / "planted" / "m01.yaml"
BASE = load_script(M01_PATH).model_copy(update={"scripts": []})


def test_totals_per_team_are_realistic():
    passes, completion, shots, goals = [], [], [], []
    for seed in range(10):
        events = MatchSim(BASE, seed=seed).run()
        for team in ("Harbour City", "Northvale"):
            team_passes = [e for e in events if e.type == "pass" and e.team == team]
            passes.append(len(team_passes))
            completion.append(sum(p.outcome == "complete" for p in team_passes) / len(team_passes))
            shots.append(sum(e.type == "shot" and e.team == team for e in events))
            goals.append(sum(e.type == "goal" and e.team == team for e in events))
    assert 400 <= statistics.mean(passes) <= 600
    assert 0.74 <= statistics.mean(completion) <= 0.86
    assert 9 <= statistics.mean(shots) <= 18
    assert 1.8 <= 2 * statistics.mean(goals) <= 3.8
```

- [ ] **Step 4: Run them to verify they fail**

Run: `uv run pytest tests/test_engine_sim.py tests/test_engine_mechanisms.py tests/test_engine_realism.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'engine.sim'` (collection errors for all three files)

- [ ] **Step 5: Implement the simulator**

`engine/sim.py`. The constants are calibrated (see the calibration table above); change them only together with the realism and mechanism tests.

```python
"""Possession-chain match simulator (spec §7.1).

A possession is a chain of actions (pass, carry, dribble, shot) by the team on the
ball while the other team presses according to its press height. Pressure makes
passes riskier and pushes the team on the ball to go long: the mechanism behind a
pressure shift. Every random draw comes from a keyed stream (engine.rng), so a run
without one intervention stays aligned with the run that has it. Coordinates are
in the acting team's attacking frame (engine.teams).
"""

import math

from contracts.clock import MatchClock
from contracts.event import Event, EventType, Outcome, PassQualifiers, Point, ShotQualifiers
from engine.params import ParamTimeline
from engine.rng import Streams
from engine.script import MatchScript, Side
from engine.teams import SPRINT_RATE, Player, build_lineup, position

PITCH_X, PITCH_Y = 105.0, 68.0
HALF = 45 * 60
HALF_TIME_BREAK_S = 15 * 60
KICKOFF_MS = 1_800_000_000_000
MAX_ACTIONS = 40
OPEN_PLAY_MAX_X = 97.0  # open play rarely reaches the six-yard box
FATIGUE_PER_MIN = 0.25 / 90


def other(side: Side) -> Side:
    return "away" if side == "home" else "home"


def mirror(p: tuple[float, float]) -> tuple[float, float]:
    return PITCH_X - p[0], PITCH_Y - p[1]


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def on_pitch(x: float, y: float) -> tuple[float, float]:
    return clamp(x, 0.5, PITCH_X - 0.5), clamp(y, 0.5, PITCH_Y - 0.5)


def ahead(x: float, y: float, dist: float, angle: float) -> tuple[float, float]:
    """A point `dist` metres away at `angle` radians, kept out of the six-yard box."""
    return on_pitch(min(x + dist * math.cos(angle), OPEN_PLAY_MAX_X), y + dist * math.sin(angle))


def clock_at(period: int, s: float) -> MatchClock:
    total = (0 if period == 1 else HALF) + int(s)
    return MatchClock(period=period, minute=total // 60, second=total % 60)


class MatchSim:
    def __init__(self, script: MatchScript, seed: int | None = None) -> None:
        self.script = script
        self.seed = script.seed if seed is None else seed
        self.rng = Streams(self.seed)
        self.params = ParamTimeline(script)
        self.lineups = {side: build_lineup(script.teams[side]) for side in ("home", "away")}
        self.score = {"home": 0, "away": 0}
        self.period_lengths: dict[int, float] = {}
        self.period = 1
        self.t = 0.0
        self.att: Side = "home"
        self.ball = (52.5, 34.0)
        self._ticked = -1
        self._pending: list[tuple[int, float, int, dict]] = []

    def run(self) -> list[Event]:
        for period in (1, 2):
            self._play_period(period)
        self._pending.sort(key=lambda e: (e[0], e[1], e[2]))
        match_id = self.script.match_id
        return [
            Event(event_id=f"{match_id}-{i:05d}", **fields)
            for i, (_, _, _, fields) in enumerate(self._pending, start=1)
        ]

    # --- time -----------------------------------------------------------------

    @property
    def minute(self) -> int:
        return ((0 if self.period == 1 else HALF) + int(self.t)) // 60

    def _advance(self, seconds: float) -> None:
        self.t += seconds
        while self._ticked + 1 < self.minute:
            self._ticked += 1
            self._physical_minute(self._ticked)

    def _physical_minute(self, m: int) -> None:
        """Fatigue and off-ball sprints for one completed minute."""
        start = m * 60 - (0 if self.period == 1 else HALF)
        for side in ("home", "away"):
            press = self.params.team(side, self.period, start)["press_height"]
            for p in self.lineups[side]:
                pid = p.player_id
                decay = self.params.player(side, pid, self.period, start)["stamina_decay"]
                p.energy = max(0.2, p.energy - FATIGUE_PER_MIN * decay)
                if not self.rng.chance(f"sprint:{pid}", m, SPRINT_RATE[p.unit] * p.energy**2):
                    continue
                s = start + self.rng.uniform(f"sprint_at:{pid}", m, 0, 59)
                ball = self.ball if side == self.att else mirror(self.ball)
                x, y = position(p, attacking=side == self.att, press_height=press, ball=ball)
                dist = self.rng.uniform(f"sprint_dist:{pid}", m, 12, 40)
                speed = 25 + 8 * p.energy + self.rng.normal(f"sprint_speed:{pid}", m, 0, 1.5)
                self._emit(
                    EventType.SPRINT,
                    side,
                    p,
                    start=(x, y),
                    end=on_pitch(x + dist, y),
                    at=s,
                    qualifiers={
                        "speed_kmh": round(clamp(speed, 24.5, 36.0), 1),
                        "distance_m": round(dist, 1),
                    },
                )

    # --- periods and possessions ----------------------------------------------

    def _play_period(self, period: int) -> None:
        self.period, self.t = period, 0.0
        self._ticked = (0 if period == 1 else 45) - 1
        stoppage_minutes = 1 + int(self.rng.uniform("stoppage", period, 0, 3 if period == 1 else 5))
        end = HALF + 60 * stoppage_minutes
        self.period_lengths[period] = end
        self._emit(EventType.PERIOD_START, "home", None, start=None)
        att: Side = "home" if period == 1 else "away"
        ball = (52.5, 34.0)
        self._emit(
            EventType.SET_PIECE,
            att,
            self._nearest(att, ball),
            start=ball,
            qualifiers={"kind": "kick_off"},
        )
        while self.t < end:
            att, ball = self._possession(att, ball, end)
        self._emit(EventType.PERIOD_END, "home", None, start=None)

    def _possession(self, att: Side, ball: tuple[float, float], end: float):
        deff = other(att)
        self.att, self.ball = att, ball
        carrier = self._nearest(att, ball)
        for _ in range(MAX_ACTIONS):
            if self.t >= end:
                break
            m = self.minute
            tp = self.params.team(att, self.period, self.t)
            press = self.params.team(deff, self.period, self.t)["press_height"]
            press = clamp(press + self.rng.normal("press_jitter", m, 0, 0.03), 0, 1)
            pressure = self._maybe_press(deff, self.ball, press)
            x, y = self.ball
            shooting_zone = x > 80 and abs(y - 34) < 20
            if shooting_zone and self.rng.chance("shot_choice", m, 0.05 + 0.006 * (x - 80)):
                return self._shot(att, carrier)
            roll = self.rng.uniform("action_choice", m)
            if roll < 0.72:
                kept, who, where = self._pass(att, carrier, tp, pressure)
            elif pressure > 0 and roll < 0.82:
                kept, who, where = self._dribble(att, carrier)
            else:
                kept, who, where = self._carry(att, carrier, pressure)
            if not kept:
                return deff, where
            carrier, self.ball = who, where
        return deff, mirror(self.ball)

    def _maybe_press(self, deff: Side, ball: tuple[float, float], press: float) -> float:
        m = self.minute
        if ball[0] < 63:  # the attacker's first 60%: where pressing happens
            p_press = 0.06 + 0.62 * press
            intensity = 0.25 + 0.6 * press + self.rng.normal("press_intensity", m, 0, 0.08)
        else:
            p_press = 0.30
            intensity = 0.45 + self.rng.normal("press_intensity", m, 0, 0.10)
        if not self.rng.chance("press_event", m, p_press):
            return 0.0
        where = mirror(ball)
        self._emit(EventType.PRESSURE, deff, self._nearest(deff, where), start=where)
        self._advance(0.8)
        return clamp(intensity, 0.0, 1.0)

    # --- actions: each returns (kept, player, ball position in the new owner's frame)

    def _pass(self, att: Side, carrier: Player, tp: dict[str, float], pressure: float):
        m = self.minute
        x, y = self.ball
        long_p = clamp(tp["directness"] + 0.9 * pressure, 0.0, 0.9) if x < 70 else 0.05
        is_long = self.rng.chance("pass_length", m, long_p)
        if is_long:
            dist = self.rng.uniform("pass_dist", m, 30, 55)
            angle = self.rng.normal("pass_angle", m, 0, 0.35)
        else:
            dist = self.rng.uniform("pass_dist", m, 6, 24)
            angle = self.rng.normal("pass_angle", m, 0, 1.0)
        tx, ty = ahead(x, y, dist, angle)
        dist = math.hypot(tx - x, ty - y)
        receiver = self._nearest(att, (tx, ty), exclude=carrier)
        p_ok = 0.99 - 0.005 * dist - 0.28 * pressure + 0.16 * (tp["quality"] - 0.5)
        p_ok -= 0.10 if is_long else 0.0
        p_ok -= 0.15 if tx > 88 else 0.0  # passes into the box are contested
        ok = self.rng.chance("pass_success", m, clamp(p_ok, 0.05, 0.98))
        speed = clamp(30 + 1.1 * dist + self.rng.normal("ball_speed", m, 0, 6), 15, 120)
        self._emit(
            EventType.PASS,
            att,
            carrier,
            start=(x, y),
            end=(tx, ty),
            outcome=Outcome.COMPLETE if ok else Outcome.INCOMPLETE,
            pass_q=PassQualifiers(
                distance_m=round(dist, 1),
                ball_speed_kmh=round(speed, 1),
                pressure_on_passer=round(pressure, 2),
                receiver_id=receiver.player_id,
            ),
        )
        self._advance(1.6 + dist / 14)
        if ok:
            return True, receiver, (tx, ty)
        deff = other(att)
        lost_at = mirror((tx, ty))
        if ty < 3 or ty > PITCH_Y - 3:  # out for a throw-in
            spot = on_pitch(lost_at[0], 0.5 if lost_at[1] < 34 else PITCH_Y - 0.5)
            self._restart(deff, spot, "throw_in", self.rng.uniform("restart_delay", m, 10, 25))
            return False, None, spot
        winner = self._nearest(deff, lost_at)
        self._emit(EventType.INTERCEPTION, deff, winner, start=lost_at, outcome=Outcome.WON)
        self._emit(EventType.POSSESSION_CHANGE, deff, winner, start=lost_at)
        self._advance(1.0)
        return False, winner, lost_at

    def _carry(self, att: Side, carrier: Player, pressure: float):
        m = self.minute
        x, y = self.ball
        dist = self.rng.uniform("carry_dist", m, 4, 14)
        ex, ey = ahead(x, y, dist, self.rng.normal("carry_angle", m, 0, 0.6))
        self._emit(EventType.CARRY, att, carrier, start=(x, y), end=(ex, ey))
        self._advance(dist / 4.0)
        if not self.rng.chance("tackle", m, 0.08 + 0.25 * pressure):
            return True, carrier, (ex, ey)
        return self._challenge(att, (ex, ey))

    def _dribble(self, att: Side, carrier: Player):
        m = self.minute
        x, y = self.ball
        ex, ey = ahead(x, y, self.rng.uniform("dribble_dist", m, 3, 7), 0.0)
        won = self.rng.chance("dribble_success", m, 0.55)
        self._emit(
            EventType.DRIBBLE,
            att,
            carrier,
            start=(x, y),
            end=(ex, ey),
            outcome=Outcome.COMPLETE if won else Outcome.INCOMPLETE,
        )
        self._advance(2.0)
        return (True, carrier, (ex, ey)) if won else self._challenge(att, (ex, ey))

    def _challenge(self, att: Side, at: tuple[float, float]):
        """A defender wins the ball, or fouls and gives away a free kick."""
        m = self.minute
        deff = other(att)
        where = mirror(at)
        defender = self._nearest(deff, where)
        if self.rng.chance("foul", m, 0.15):
            self._emit(EventType.FOUL, deff, defender, start=where)
            self._restart(att, at, "free_kick", self.rng.uniform("restart_delay", m, 15, 35))
            return True, self._nearest(att, at), at
        self._emit(EventType.TACKLE, deff, defender, start=where, outcome=Outcome.WON)
        self._emit(EventType.POSSESSION_CHANGE, deff, defender, start=where)
        self._advance(1.0)
        return False, defender, where

    def _shot(self, att: Side, shooter: Player):
        m = self.minute
        x, y = self.ball
        dx, dy = PITCH_X - x, y - 34.0
        dist = math.hypot(dx, dy)
        angle = math.degrees(math.atan2(7.32 * dx, dx * dx + dy * dy - 3.66**2))
        defenders = max(0, round(self.rng.normal("shot_defenders", m, 1.2 + (x - 85) / 15, 0.9)))
        xg = 1 / (1 + math.exp(-(-0.75 - 0.10 * dist + 0.03 * angle - 0.30 * defenders)))
        r = self.rng.uniform("shot_outcome", m)
        if r < xg:
            outcome = Outcome.GOAL
        elif r < xg + 0.25:
            outcome = Outcome.ON_TARGET
        elif r < xg + 0.45:
            outcome = Outcome.BLOCKED
        else:
            outcome = Outcome.OFF_TARGET
        speed = clamp(self.rng.normal("shot_speed", m, 88, 14), 40, 135)
        self._emit(
            EventType.SHOT,
            att,
            shooter,
            start=(x, y),
            end=(PITCH_X, 34.0),
            outcome=outcome,
            body_part="head" if self.rng.chance("shot_body", m, 0.12) else "foot",
            shot_q=ShotQualifiers(
                shot_speed_kmh=round(speed, 1),
                distance_m=round(dist, 1),
                angle_deg=round(angle, 1),
                defenders_in_cone=defenders,
            ),
        )
        self._advance(2.0)
        deff = other(att)
        if outcome == Outcome.GOAL:
            self.score[att] += 1
            self._emit(EventType.GOAL, att, shooter, start=(x, y), outcome=Outcome.GOAL)
            self._restart(deff, (52.5, 34.0), "kick_off", 45.0)
            return deff, (52.5, 34.0)
        self._restart(deff, (6.0, 34.0), "goal_kick", self.rng.uniform("restart_delay", m, 8, 20))
        return deff, (6.0, 34.0)

    def _restart(self, side: Side, spot: tuple[float, float], kind: str, pause: float) -> None:
        self._advance(pause)
        self._emit(
            EventType.SET_PIECE,
            side,
            self._nearest(side, spot),
            start=spot,
            qualifiers={"kind": kind},
        )

    # --- helpers --------------------------------------------------------------

    def _nearest(
        self, side: Side, point: tuple[float, float], exclude: Player | None = None
    ) -> Player:
        press = self.params.team(side, self.period, self.t)["press_height"]
        attacking = side == self.att
        ball = self.ball if attacking else mirror(self.ball)
        best, best_d = None, math.inf
        for p in self.lineups[side]:
            if p is exclude:
                continue
            px, py = position(p, attacking=attacking, press_height=press, ball=ball)
            d = (px - point[0]) ** 2 + (py - point[1]) ** 2
            if d < best_d:
                best, best_d = p, d
        return best

    def _emit(
        self,
        etype: EventType,
        side: Side,
        player: Player | None,
        *,
        start: tuple[float, float] | None,
        end: tuple[float, float] | None = None,
        outcome: Outcome = Outcome.NA,
        body_part: str | None = None,
        pass_q: PassQualifiers | None = None,
        shot_q: ShotQualifiers | None = None,
        qualifiers: dict | None = None,
        at: float | None = None,
    ) -> None:
        s = self.t if at is None else at
        elapsed = s if self.period == 1 else self.period_lengths[1] + HALF_TIME_BREAK_S + s
        fields = {
            "match_id": self.script.match_id,
            "clock": clock_at(self.period, s),
            "wall_clock_ms": KICKOFF_MS + int(elapsed * 1000),
            "type": etype,
            "team": self.script.teams[side].name,
            "player_id": player.player_id if player else None,
            "position": player.role if player else None,
            "start": Point(x=round(start[0], 1), y=round(start[1], 1)) if start else None,
            "end": Point(x=round(end[0], 1), y=round(end[1], 1)) if end else None,
            "outcome": outcome,
            "body_part": body_part,
            "pass_q": pass_q,
            "shot_q": shot_q,
            "qualifiers": qualifiers or {},
        }
        self._pending.append((self.period, s, len(self._pending), fields))
```

- [ ] **Step 6: Run them to verify they pass**

Run: `uv run pytest tests/test_engine_sim.py tests/test_engine_mechanisms.py tests/test_engine_realism.py -v`
Expected: 10 passed

- [ ] **Step 7: Commit**

```bash
git add engine/sim.py tests/test_engine_sim.py tests/test_engine_mechanisms.py tests/test_engine_realism.py
git commit -m "Add the possession-chain match simulator" -m "Pressure from a raised press makes passes riskier and pushes the opponent long, and stamina decay costs sprints, so scripted mechanisms move the metrics the detector watches. Totals are calibrated to top-flight ranges, and keyed streams keep the match before an intervention identical with and without it."
```

---

### Task 8: Output files and the `proofline-engine` CLI

**Files:**
- Create: `engine/io.py`
- Create: `engine/cli.py`
- Test: `tests/test_engine_cli.py`

- [ ] **Step 1: Write the failing test**

`tests/test_engine_cli.py`:

```python
import json
from pathlib import Path

from engine.cli import main
from engine.io import read_events

M01 = Path(__file__).resolve().parents[1] / "engine" / "scripts" / "planted" / "m01.yaml"


def test_generate_writes_events_and_meta(tmp_path, capsys):
    assert main(["generate", "--script", str(M01), "--seed", "7", "--out", str(tmp_path)]) == 0
    events = read_events(tmp_path / "events.jsonl")
    meta = json.loads((tmp_path / "meta.json").read_text())
    assert meta["match_id"] == "m01" and meta["seed"] == 7
    assert len(meta["teams"]["home"]["players"]) == 11
    assert len(events) == meta["events"] > 2000
    assert "Harbour City" in capsys.readouterr().out
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_engine_cli.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'engine.cli'`

- [ ] **Step 3: Implement the writer and reader**

`engine/io.py`:

```python
"""Write a generated match to disk: events.jsonl plus meta.json (rosters, score).

Nothing here reveals the script's interventions; those stay in the YAML and the
sealed ground truth.
"""

import json
from pathlib import Path

from contracts.event import Event
from engine.sim import MatchSim


def write_match(sim: MatchSim, events: list[Event], out_dir: str | Path) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "events.jsonl").open("w", encoding="utf-8") as f:
        for event in events:
            f.write(event.model_dump_json() + "\n")
    meta = {
        "match_id": sim.script.match_id,
        "seed": sim.seed,
        "teams": {
            side: {
                "name": team.name,
                "code": team.code,
                "formation": team.formation,
                "players": [
                    {"player_id": p.player_id, "name": p.name, "role": p.role, "unit": p.unit}
                    for p in sim.lineups[side]
                ],
            }
            for side, team in sim.script.teams.items()
        },
        "period_lengths_s": sim.period_lengths,
        "score": sim.score,
        "events": len(events),
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return out


def read_events(path: str | Path) -> list[Event]:
    with Path(path).open(encoding="utf-8") as f:
        return [Event.model_validate_json(line) for line in f if line.strip()]
```

- [ ] **Step 4: Implement the CLI**

`engine/cli.py`:

```python
"""proofline-engine: generate synthetic matches from tactical scripts."""

import argparse
import sys

from engine.io import write_match
from engine.script import load_script
from engine.sim import MatchSim


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="proofline-engine", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    gen = sub.add_parser("generate", help="simulate one match from a script")
    gen.add_argument("--script", required=True, help="path to a tactical script (YAML)")
    gen.add_argument("--seed", type=int, default=None, help="overrides the script's seed")
    gen.add_argument("--out", required=True, help="output directory")
    args = parser.parse_args(argv)

    script = load_script(args.script)
    sim = MatchSim(script, seed=args.seed)
    events = sim.run()
    write_match(sim, events, args.out)
    home, away = script.teams["home"].name, script.teams["away"].name
    print(
        f"{script.match_id} seed {sim.seed}: {len(events)} events, "
        f"{home} {sim.score['home']}-{sim.score['away']} {away}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run it to verify it passes**

Run: `uv run pytest tests/test_engine_cli.py -v`
Expected: 1 passed

- [ ] **Step 6: Generate the demo match through the installed command**

Run: `uv run proofline-engine generate --script engine/scripts/planted/m01.yaml --out data/m01/`
Expected: `m01 seed 4417: 2949 events, Harbour City 2-2 Northvale`, and `data/m01/events.jsonl` (about 1 MB) plus `data/m01/meta.json`. `data/` is gitignored; do not commit it.

- [ ] **Step 7: Commit**

```bash
git add engine/io.py engine/cli.py tests/test_engine_cli.py
git commit -m "Add the proofline-engine generate command" -m "Writes one validated Event per line plus rosters and score, with nothing that reveals the script's interventions."
```

---

### Task 9: Full verification and the README

**Files:**
- Modify: `README.md` (Repository table)

- [ ] **Step 1: Add the engine to the README's Repository table**

In `README.md`, add this row directly below the `contracts/` row:

```markdown
| `engine/` | Match Engine: synthetic matches from tactical scripts (`proofline-engine generate`); never imported by product code |
```

- [ ] **Step 2: Run the whole CI sequence**

Run:

```bash
uv run ruff check . && uv run ruff format --check .
uv run python scripts/check_engine_isolation.py
uv run pytest
uv run python scripts/export_schemas.py && git diff --exit-code -- 'docs/*.schema.json'
```

Expected: `All checks passed!`, all files already formatted, `Engine isolation OK`, `75 passed`, and no schema diff.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "List the Match Engine in the README"
```
