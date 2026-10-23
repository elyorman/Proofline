"""Read the match feed from Event Hubs into an Ingest until the match has ended."""

import os
import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from azure.eventhub import EventHubConsumerClient
from azure.identity import DefaultAzureCredential

from contracts.case import Case
from contracts.feed import FeedMessage
from ledger.ingest import Ingest


def consume(
    namespace: str,
    hub: str,
    ingest: Ingest,
    match_id: str,
    on_cases: Callable[[list[Case]], None],
    timeout_s: float = 900,
) -> bool:
    """Feed every batch from now on into `ingest`; True once `match_id` has ended."""
    credential = DefaultAzureCredential(managed_identity_client_id=os.getenv("AZURE_CLIENT_ID"))
    client = EventHubConsumerClient(
        fully_qualified_namespace=namespace,
        eventhub_name=hub,
        consumer_group="$Default",
        credential=credential,
    )
    ended, lock = threading.Event(), threading.Lock()

    def on_batch(_partition, events) -> None:
        batch = [FeedMessage.model_validate_json(e.body_as_str()) for e in events]
        with lock:  # partitions call back on their own threads
            on_cases(ingest.take(batch))
            if ingest.finished(match_id):
                ended.set()

    reader = threading.Thread(
        target=client.receive_batch,
        kwargs={
            "on_event_batch": on_batch,
            "starting_position": datetime.now(UTC) - timedelta(seconds=5),
            "max_batch_size": 300,
            "max_wait_time": 5,
        },
        daemon=True,
    )
    reader.start()
    try:
        return ended.wait(timeout_s)
    finally:
        client.close()
        reader.join(timeout=30)
