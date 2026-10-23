"""Planted and decoy suites, with their sealed ground truth and frozen flags (spec §7.3).

Each planted match carries one intervention whose mechanism belongs to one plantable
class; the class itself is written only to the sealed ground truth. Match ids are
opaque: they name neither the cause, nor whether anything was planted, nor the split.
Seeds come from the split's own range (spec §11.1), every match has seeds of its own,
and a match seed is used only when the planted change
is unambiguous there, from its start to the end of its window: a press change is not
planted while the score gives the team a game-state reason for it, and a score-triggered
change must start in time and keep the score that triggered it.
"""

import random
import time
from dataclasses import dataclass
from multiprocessing import Pool
from pathlib import Path

import yaml

from contracts.clock import MatchClock
from contracts.eval_run import SEED_RANGES, FlagSet, Split, Suite
from contracts.planted import CAUSE_OBSERVABLES, GroundTruth, PlantedTruth
from contracts.taxonomy import Cause
from engine.paired import LATEST_START, judge, measure, resolve, window_after
from engine.script import Intervention, MatchScript, TeamSpec
from engine.sim import MatchSim
from engine.teams import FORMATIONS, UNIT_OF_ROLE

MATCH_OFFSET, DECOY_OFFSET, PAIRED_OFFSET = 0, 300, 500
PER_CLASS = {Split.DEV: 2, Split.HELDOUT: 5}
DECOYS = {Split.DEV: 4, Split.HELDOUT: 10}
PAIRS = 30
SCAN = 200  # seeds tried before a planted match's pairs are given up
ID_BLOCK = 200  # the most matches one suite split can hold

# Match ids are drawn from one seeded shuffle for every suite and split, so an id says
# nothing about which it belongs to.
_ID_SLOT = {
    (Suite.PLANTED, Split.DEV): 0,
    (Suite.DECOYS, Split.DEV): 1,
    (Suite.PLANTED, Split.HELDOUT): 2,
    (Suite.DECOYS, Split.HELDOUT): 3,
}
_IDS = random.Random("match-ids").sample(range(100, 1000), len(_ID_SLOT) * ID_BLOCK)


def match_id(suite: Suite, split: Split, k: int) -> str:
    if not 0 <= k < ID_BLOCK:
        raise ValueError(f"a suite split holds at most {ID_BLOCK} matches")
    return f"m{_IDS[_ID_SLOT[suite, split] * ID_BLOCK + k]}"


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
    # Score-triggered classes start at the first possession from `at`, by 65:00.
    if cause == Cause.CHASING_RESULT:
        return {"press_height": _r(rng, 0.35, 0.5)}, {
            "at": _clock(rng, 55, 64),
            "when": "trailing",
            "ramp": "2m",
            "set": {"press_height": _r(rng, 0.85, 0.95), "directness": _r(rng, 0.4, 0.5)},
        }
    if cause == Cause.PROTECTING_LEAD:
        return {"press_height": _r(rng, 0.6, 0.7)}, {
            "at": _clock(rng, 55, 64),
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


def _styled(cause: Cause, rng: random.Random) -> tuple[dict, str, dict]:
    """Two teams, one of them (`side`) set up in the starting style of `cause`'s template,
    and that template's intervention fields."""
    teams = _teams(rng)
    side = rng.choice(["home", "away"])
    params, fields = _template(cause, rng, teams[side])
    teams[side] = teams[side].model_copy(update=params)
    return teams, side, fields


def _score_at(events: list, team: str, clock: MatchClock) -> int:
    return sum(e.type == "goal" and e.team == team and e.clock < clock for e in events)


def _leads(events: list, team: str, rival: str, since: MatchClock, until: MatchClock) -> list:
    """The team's goal difference at `since`, then after each goal up to `until`."""
    lead = _score_at(events, team, since) - _score_at(events, rival, since)
    leads = [lead]
    for e in events:
        if e.type == "goal" and since <= e.clock <= until:
            lead += 1 if e.team == team else -1
            leads.append(lead)
    return leads


# The goal differences under which each class is the only fair answer.
FAIR_LEAD = {
    Cause.PRESS_INTENSITY_UP: lambda lead: lead >= 0,  # trailing: chasing would fit
    Cause.PRESS_INTENSITY_DOWN: lambda lead: lead <= 0,  # leading: protecting would fit
    Cause.CHASING_RESULT: lambda lead: lead < 0,
    Cause.PROTECTING_LEAD: lambda lead: lead > 0,
}


def _unambiguous(cause: Cause, script: MatchScript, sim: MatchSim, events: list) -> bool:
    """The planted change is the only fair answer in this match, through its window."""
    iv = script.scripts[0]
    start = sim.params.started[iv.id]
    if start is None or LATEST_START < start:
        return False
    if cause not in FAIR_LEAD:
        return True
    team = script.teams[iv.team].name
    rival = next(t.name for t in script.teams.values() if t.name != team)
    end = window_after(start, WINDOW[cause]).end
    return all(FAIR_LEAD[cause](lead) for lead in _leads(events, team, rival, start, end))


@dataclass
class BuiltSuite:
    suite: Suite
    split: Split
    scripts: list[MatchScript]
    truth: GroundTruth
    flags: FlagSet | None = None


def _planted_match(args: tuple) -> tuple[MatchScript, PlantedTruth]:
    """Match `i` of `n` tries seeds i, i + n, i + 2n, ... of the split's match block, so no
    two matches share a seed."""
    split, cause, k, i, n = args
    mid = match_id(Suite.PLANTED, split, i)
    teams, side, fields = _styled(cause, random.Random(f"planted:{split}:{cause}:{k}"))
    iv = Intervention.model_validate({"id": "s1", "team": side, **fields})
    first, block_end = (SEED_RANGES[split].start + o for o in (MATCH_OFFSET, DECOY_OFFSET))
    for seed in range(first + i, block_end, n):
        script = MatchScript(match_id=mid, seed=seed, teams=teams, scripts=[iv])
        sim = MatchSim(script)
        events = sim.run()
        if _unambiguous(cause, script, sim, events):
            start = sim.params.started[iv.id]
            truth = PlantedTruth(
                match_id=mid,
                cause=cause,
                team=teams[side].name,
                script_id=iv.id,
                started=start,
                window=window_after(start, WINDOW[cause]),
                observables=resolve(cause, script, iv),
            )
            return script, truth
    raise ValueError(f"{mid}: no seed of its own plants {cause} unambiguously")


def _flag(args: tuple):
    split, script, truth, pairs = args
    first = SEED_RANGES[split].start + PAIRED_OFFSET
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
    if not 0 < len(jobs) <= ID_BLOCK:
        raise ValueError(f"a planted suite split holds 1 to {ID_BLOCK} matches")
    random.Random(f"order:{split}").shuffle(jobs)
    args = [(split, c, k, i, len(jobs)) for i, (c, k) in enumerate(jobs)]
    with Pool(processes) as pool:
        built = pool.map(_planted_match, args)
        flagged = pool.map(_flag, [(split, s, t, pairs) for s, t in built])
    scripts = [s for s, _ in built]
    flags = FlagSet(
        split=split,
        match_ids=[s.match_id for s in scripts],
        paired_seeds={s.match_id: seeds for s, (_, seeds) in zip(scripts, flagged, strict=True)},
        frozen_at_ms=int(time.time() * 1000),
        exclusions=[x for x, _ in flagged if x is not None],
    )
    truth = GroundTruth(suite=Suite.PLANTED, split=split, entries=[t for _, t in built])
    return BuiltSuite(Suite.PLANTED, split, scripts, truth, flags)


def decoys(split: Split, count: int | None = None) -> BuiltSuite:
    """Matches with nothing planted: natural swings only. Each decoy sets a team up in the
    starting style of one class's template, the classes taken in turn, so a team's style
    before the change never tells a planted match from a decoy."""
    count = DECOYS[split] if count is None else count
    if not 0 < count <= PAIRED_OFFSET - DECOY_OFFSET:
        raise ValueError(f"a decoy suite split holds 1 to {PAIRED_OFFSET - DECOY_OFFSET} matches")
    styles = list(CAUSE_OBSERVABLES)
    random.Random(f"decoy-styles:{split}").shuffle(styles)
    scripts, entries = [], []
    for k in range(count):
        teams, _, _ = _styled(styles[k % len(styles)], random.Random(f"decoy:{split}:{k}"))
        mid = match_id(Suite.DECOYS, split, k)
        seed = SEED_RANGES[split].start + DECOY_OFFSET + k
        scripts.append(MatchScript(match_id=mid, seed=seed, teams=teams))
        entries.append(PlantedTruth(match_id=mid, cause=Cause.NONE))
    truth = GroundTruth(suite=Suite.DECOYS, split=split, entries=entries)
    return BuiltSuite(Suite.DECOYS, split, scripts, truth)


def dump_script(script: MatchScript) -> str:
    """The script as YAML in the hand-written style: clocks as quoted text."""
    if script.amendments:
        raise ValueError(f"{script.match_id}: amendments are not written yet")

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
    for old in (out / "scripts").glob("*.yaml"):  # a rebuild replaces the whole suite
        old.unlink()
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
