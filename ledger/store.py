"""Ledger documents and where they go. Every container is partitioned by match id; every
version of an event is kept, under its own id."""

import os
from dataclasses import dataclass, field
from typing import Any, Protocol

from azure.cosmos import CosmosClient
from azure.identity import DefaultAzureCredential

from contracts.case import Case
from contracts.event import Event
from contracts.meta import MatchMeta

COSMOS_BATCH = 100  # the most operations one transactional batch takes


def meta_doc(meta: MatchMeta) -> dict[str, Any]:
    return {"id": "meta", "kind": "meta", **meta.model_dump(mode="json")}


def event_doc(event: Event) -> dict[str, Any]:
    doc = event.model_dump(mode="json")
    return {"id": f"{event.event_id}:v{event.version}", "kind": "event", **doc}


def case_doc(case: Case) -> dict[str, Any]:
    return {"id": case.case_id, **case.model_dump(mode="json")}


class Ledger(Protocol):
    def put(self, container: str, match_id: str, docs: list[dict[str, Any]]) -> None: ...


@dataclass
class MemoryLedger:
    containers: dict[str, dict[tuple[str, str], dict[str, Any]]] = field(default_factory=dict)

    def put(self, container: str, match_id: str, docs: list[dict[str, Any]]) -> None:
        stored = self.containers.setdefault(container, {})
        for doc in docs:
            stored[match_id, doc["id"]] = doc


@dataclass
class CosmosLedger:
    """The deployed ledger, reached with the default Azure credential (no keys)."""

    endpoint: str
    database: str
    _client: CosmosClient | None = None

    def _container(self, name: str):
        if self._client is None:
            credential = DefaultAzureCredential(
                managed_identity_client_id=os.getenv("AZURE_CLIENT_ID")
            )
            self._client = CosmosClient(self.endpoint, credential=credential)
        return self._client.get_database_client(self.database).get_container_client(name)

    def put(self, container: str, match_id: str, docs: list[dict[str, Any]]) -> None:
        target = self._container(container)
        for i in range(0, len(docs), COSMOS_BATCH):
            operations = [("upsert", (doc,)) for doc in docs[i : i + COSMOS_BATCH]]
            target.execute_item_batch(batch_operations=operations, partition_key=match_id)
