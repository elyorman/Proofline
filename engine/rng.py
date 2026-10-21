"""Deterministic random streams keyed by decision type and match-minute bucket.

A draw for "pass_length" in minute 61 comes from its own generator, seeded from
(match seed, decision, minute). A script that changes how many passes happen in
minute 61 leaves every other minute's draws untouched, which keeps a run and its
counterfactual aligned (spec §7.2).
"""

import hashlib
import random


class Streams:
    def __init__(self, seed: int) -> None:
        self.seed = seed
        self._generators: dict[tuple[str, int], random.Random] = {}

    def _gen(self, decision: str, minute: int) -> random.Random:
        key = (decision, minute)
        gen = self._generators.get(key)
        if gen is None:
            text = f"{self.seed}:{decision}@{minute}".encode()
            digest = hashlib.blake2b(text, digest_size=8).digest()
            gen = random.Random(int.from_bytes(digest, "big"))
            self._generators[key] = gen
        return gen

    def uniform(self, decision: str, minute: int, low: float = 0.0, high: float = 1.0) -> float:
        return self._gen(decision, minute).uniform(low, high)

    def normal(self, decision: str, minute: int, mu: float, sigma: float) -> float:
        return self._gen(decision, minute).normalvariate(mu, sigma)

    def chance(self, decision: str, minute: int, p: float) -> bool:
        return self._gen(decision, minute).random() < p
