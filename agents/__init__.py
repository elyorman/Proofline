"""The Why Engine's agents (spec §9.1).

Agents never compute a number. They pre-register predictions, which code tests against the
State Builder's tools, and they rank what survives; every number on a card comes from a
tool call the Verifier can re-run.
"""
