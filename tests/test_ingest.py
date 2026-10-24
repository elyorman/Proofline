from pathlib import Path

import pytest
from pydantic import ValidationError

from contracts.feed import FeedMessage
from detector.cusum import detect
from engine.clock import BATCH, messages, publish
from engine.io import read_events, read_meta, write_match
from engine.script import load_script
from engine.sim import MatchSim
from ledger.ingest import Ingest
from ledger.store import MemoryLedger

M01 = Path(__file__).resolve().parents[1] / "engine" / "scripts" / "planted" / "m01.yaml"


@pytest.fixture(scope="module")
def m01_dir(tmp_path_factory):
    out = tmp_path_factory.mktemp("feed") / "m01"
    sim = MatchSim(load_script(M01))
    write_match(sim, sim.run(), out)
    return out


def test_a_feed_message_carries_exactly_its_body(m01_dir):
    meta = read_meta(m01_dir / "meta.json")
    event = read_events(m01_dir / "events.jsonl")[0]
    assert FeedMessage(run_id="r", match_id="m01", kind="meta", meta=meta).meta == meta
    for broken in (
        dict(kind="meta", event=event),
        dict(kind="event", meta=meta, event=event),
        dict(kind="event", event=event, match_id="m02"),
    ):
        with pytest.raises(ValidationError):
            FeedMessage(**(dict(run_id="r", match_id="m01") | broken))


def test_the_clock_sends_the_metadata_first_then_every_event_on_one_partition(m01_dir):
    sent = []
    feed = messages(m01_dir, "run-1")
    assert publish(feed, lambda bodies, key: sent.append((len(bodies), key)), speed=0) == 2975
    assert feed[0].kind == "meta" and all(m.kind == "event" for m in feed[1:])
    assert {key for _, key in sent} == {"m01"} and max(n for n, _ in sent) == BATCH


def test_streaming_opens_the_cases_batch_detection_does(m01_dir):
    ledger = MemoryLedger()
    run = Ingest(ledger, "run-1")
    feed = messages(m01_dir, "run-1")
    stale = messages(m01_dir, "run-0")[:50]  # an earlier run's messages still on the hub
    opened = []
    for i in range(0, len(feed), 300):
        opened += run.take(stale + feed[i : i + 300])
        stale = []
    events = read_events(m01_dir / "events.jsonl")
    expected = detect(read_meta(m01_dir / "meta.json"), events)
    assert [c.model_dump() for c in run.matches["m01"].detector.cases] == [
        c.model_dump() for c in expected
    ]
    assert run.finished("m01") and len(ledger.containers["events"]) == len(events) + 1
    cases = ledger.containers["cases"]
    assert ("m01", "case-m01-063-pressure_shift") in cases
    assert {c["id"] for _, c in cases.items()} == {c.case_id for c in expected}


def test_an_event_before_its_metadata_is_refused(m01_dir):
    with pytest.raises(ValueError, match="before its metadata"):
        Ingest(MemoryLedger(), "run-1").take(messages(m01_dir, "run-1")[1:3])
