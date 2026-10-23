"""The Match Ledger (spec §11.3): what the feed delivered and what the system made of it.

`store` writes documents to Cosmos DB (or memory, in tests); `ingest` turns feed messages
into stored events and detector cases; `eventhubs` reads the feed from Event Hubs.
"""
