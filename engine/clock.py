"""Match Clock: replay a written match onto the feed as a live provider would deliver it.

Messages go to Event Hubs keyed by match id, so one match stays on one partition, in
order. At speed 0 the match is sent as fast as the hub takes it (batch mode); at speed N
events are spaced by their wall-clock gaps divided by N.
"""

import os
import time
from collections.abc import Callable, Iterable
from pathlib import Path

from azure.eventhub import EventData, EventHubProducerClient
from azure.identity import DefaultAzureCredential

from contracts.feed import FeedMessage
from engine.io import read_events, read_meta

BATCH = 200


def messages(match_dir: str | Path, run_id: str) -> list[FeedMessage]:
    folder = Path(match_dir)
    meta = read_meta(folder / "meta.json")
    events = read_events(folder / "events.jsonl")
    opening = FeedMessage(run_id=run_id, match_id=meta.match_id, kind="meta", meta=meta)
    return [opening] + [
        FeedMessage(run_id=run_id, match_id=meta.match_id, kind="event", event=e) for e in events
    ]


def paced(feed: list[FeedMessage], speed: float) -> Iterable[list[FeedMessage]]:
    """Batches to send, waiting between them to keep the match's own timing at `speed`."""
    if speed <= 0:
        for i in range(0, len(feed), BATCH):
            yield feed[i : i + BATCH]
        return
    started, first_ms = time.monotonic(), None
    for message in feed:
        if message.event is not None:
            first_ms = message.event.wall_clock_ms if first_ms is None else first_ms
            due = (message.event.wall_clock_ms - first_ms) / 1000 / speed
            time.sleep(max(0.0, due - (time.monotonic() - started)))
        yield [message]


def publish(feed: list[FeedMessage], send: Callable[[list[str], str], None], speed: float) -> int:
    """Send the match through `send(bodies, partition_key)`; returns the messages sent."""
    sent = 0
    for batch in paced(feed, speed):
        send([m.model_dump_json() for m in batch], batch[0].match_id)
        sent += len(batch)
    return sent


def event_hubs_sender(
    namespace: str, hub: str
) -> tuple[Callable[[list[str], str], None], EventHubProducerClient]:
    """A `send` for Event Hubs with the default Azure credential, and the client to close."""
    credential = DefaultAzureCredential(managed_identity_client_id=os.getenv("AZURE_CLIENT_ID"))
    client = EventHubProducerClient(namespace, hub, credential=credential)

    def send(bodies: list[str], partition_key: str) -> None:
        batch = client.create_batch(partition_key=partition_key)
        for body in bodies:
            try:
                batch.add(EventData(body))
            except ValueError:  # full: send what fits and start another
                client.send_batch(batch)
                batch = client.create_batch(partition_key=partition_key)
                batch.add(EventData(body))
        client.send_batch(batch)

    return send, client
