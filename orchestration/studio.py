"""Studio mode (spec §7.4): a whole written match through the product, as the live pipeline
runs it, so a demo plays unattended. Each case is detected on the feed as it stood when the
case opened and goes through the Why Engine and the Verifier; each amendment is applied at
its time and the Correction Watcher corrects what depended on it; the Director schedules
every revision for one viewer and the broadcast. The result is one ledger the surfaces
replay, with no model call.
"""

import json
from pathlib import Path
from typing import Any

from agents.confirm import extended
from agents.director import direct
from agents.llm import MissingFixture, Model
from contracts.card import InsightCard
from contracts.eval_run import Variant
from contracts.profile import Profile
from contracts.taxonomy import CardStatus
from corrections.watcher import DependencyIndex, Published, correct
from detector.cusum import detect
from orchestration.case import case_file, run_case
from state.tools import Feed
from tools_server.server import DirectorySource

# The demo's viewer (docs/demo-script.md): a Northvale fan reading in Spanish, following NV-10.
DEMO_FAN = Profile(
    profile_id="demo-fan",
    expertise="core",
    language="es",
    favorite_club="Northvale",
    favorite_players=["NV-10"],
    mode="player_focus",
)


def _cases(source: DirectorySource, match_id: str):
    """Every case with the feed as it stood when the case opened, once its change was
    confirmed: detected on the feed as first delivered until the first amendment, then on the
    amended feed."""
    feed = source.feed(match_id)
    versions: list[tuple[Any, Feed]] = [(None, feed)]
    for amendment in source.amendments(match_id):
        feed = feed.amended(amendment)
        versions.append((amendment, feed))
    out = []
    for i, (applied, version) in enumerate(versions):
        until = versions[i + 1][0].at if i + 1 < len(versions) else None
        for case in detect(version.meta, version.events):
            opened = extended(case).window.end
            if (applied is None or not opened < applied.at) and (until is None or opened < until):
                out.append((case, version))
    return versions, sorted(out, key=lambda c: c[0].window.end.sort_key)


async def studio(
    source: DirectorySource,
    match_id: str,
    agents: Model,
    verifier: Model,
    variant: Variant = Variant.A_PROOFLINE,
    profile: Profile = DEMO_FAN,
) -> dict[str, Any]:
    versions, cases = _cases(source, match_id)
    revisions: list[InsightCard] = []
    published: dict[str, Published] = {}
    files, errors = [], []
    for case, feed in cases:
        try:
            outcome = await run_case(variant, agents, verifier, case, feed)
        except MissingFixture:  # a replay that no longer matches the code fails loudly
            raise
        except Exception as exc:  # one failed case is recorded; the match plays on
            errors.append({"case_id": case.case_id, "error": f"{type(exc).__name__}: {exc}"})
            continue
        files.append(case_file(outcome, variant))
        if outcome.verdict is None:
            continue
        card = outcome.verdict.card
        revisions.append(card)
        if card.status == CardStatus.VERIFIED:
            primary = card.primary_cause.hypothesis_id
            hypothesis = next(h for h in outcome.finding.hypotheses if h.hypothesis_id == primary)
            # The case the card was built on: its window runs on to the confirming minute.
            built_on = outcome.finding.case
            published[card.id] = Published(
                card, built_on, hypothesis, outcome.finding.evidence, outcome.finding.exams
            )
    index = DependencyIndex()
    for p in published.values():
        index.add(p)
    corrections = []
    for amendment, feed in versions[1:]:
        for card_id in sorted(index.dependents(amendment)):
            if card_id not in published:
                continue  # withdrawn by an earlier amendment
            p = published[card_id]
            if not (p.card.timing.verified_at or p.card.timing.detected_at) < amendment.at:
                continue  # published on the corrected feed already
            fixed = await correct(verifier, p, feed, amendment)
            if fixed is None:
                continue
            revisions.append(fixed.card)
            corrections.append(
                {
                    "card_id": card_id,
                    "decision": fixed.decision,
                    "revision": fixed.card.revision,
                    "amendment_id": amendment.amendment_id,
                }
            )
            if fixed.decision == "revise":  # later amendments re-check it on its new evidence
                published[card_id] = Published(
                    fixed.card, p.case, p.hypothesis, fixed.evidence, p.exams
                )
                index.add(published[card_id])
            else:
                del published[card_id]
    first = versions[0][1]
    schedule = direct(revisions, first.events, first.meta, profile)
    return {
        "match_id": match_id,
        "variant": variant.value,
        "profile": profile.model_dump(mode="json"),
        "cards": [c.model_dump(mode="json") for c in schedule.cards],
        "cues": [c.model_dump(mode="json") for c in schedule.cues],
        "case_files": [f.model_dump(mode="json") for f in files],
        "amendments": [a.model_dump(mode="json") for a, _ in versions[1:]],
        "dependencies": [d.model_dump(mode="json") for d in index.entries()],
        "corrections": corrections,
        "case_errors": errors,
    }


def write(ledger: dict[str, Any], out: Path) -> Path:
    path = Path(out) / ledger["match_id"] / "ledger.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ledger, indent=1) + "\n", encoding="utf-8")
    return path
