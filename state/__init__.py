"""Match State Builder (spec §8.1): pure analytics over the events a match has delivered.

`metrics` computes values from events, `subjects` resolves a team, unit or player through
the roster, and `tools` wraps both as the MCP tool catalog's results, each with the
evidence set it read. Nothing here imports the engine or reads ground truth.
"""
