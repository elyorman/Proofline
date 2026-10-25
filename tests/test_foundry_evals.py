"""What Foundry's evaluators are given: every text a viewer reads in the demo take, beside the
facts the Verifier saw. Building the items needs no model; running them does, so it is not
tested here."""

import json
from pathlib import Path

from engine.io import match_meta
from engine.script import load_script
from engine.sim import MatchSim
from eval.foundry_evals import items

ROOT = Path(__file__).resolve().parents[1]


def test_every_published_text_is_judged_against_what_the_verifier_saw():
    ledger = json.loads((ROOT / "surfaces/web/src/fixtures/ledger.json").read_text())
    meta = match_meta(MatchSim(load_script(ROOT / "engine/scripts/planted/m01.yaml")))
    rows = items(ledger, meta)
    judged_cards = [
        c for c in ledger["cards"] if c["lane"] == "full" and c["verification"]["support_level"]
    ]
    turned_away = [a for a in ledger["answers"] if a["outcome"] == "premise_false"]
    # Casual and analyst text, in English and Spanish, per card; both languages per answer.
    assert len(rows) == 4 * len(judged_cards) + 2 * len(turned_away)
    assert len({r["id"] for r in rows}) == len(rows)
    first = next(r for r in rows if r["id"].endswith(":casual:es"))
    card = next(c for c in judged_cards if first["id"].startswith(f"{c['id']}:r{c['revision']}"))
    assert first["response"] == card["variants"]["casual"]["es"]
    context = json.loads(first["context"])
    assert context["support_level"] == card["verification"]["support_level"]
    answer = next(r for r in rows if r["id"].startswith(turned_away[0]["question"]["question_id"]))
    assert json.loads(answer["context"])["holds"] is False
    assert "Ambrel" in json.loads(rows[-1]["context"])["names"].values()
