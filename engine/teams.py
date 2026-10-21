"""Formations, line-ups and where players stand (the lightweight positional model).

Coordinates are in each team's own attacking frame: x=0 is its own goal line and
x=105 the opponent's; y=0 is the left touchline and y=68 the right, looking
towards the opponent's goal. Every event a team performs uses that team's frame.
"""

from dataclasses import dataclass

from engine.script import TeamSpec

FORMATIONS: dict[str, list[tuple[str, float, float]]] = {
    "4-3-3": [
        ("GK", 5, 34),
        ("RB", 32, 58),
        ("RCB", 26, 43),
        ("LCB", 26, 25),
        ("LB", 32, 10),
        ("RCM", 50, 48),
        ("CM", 45, 34),
        ("LCM", 50, 20),
        ("RW", 74, 60),
        ("ST", 80, 34),
        ("LW", 74, 8),
    ],
    "4-2-3-1": [
        ("GK", 5, 34),
        ("RB", 32, 58),
        ("RCB", 26, 43),
        ("LCB", 26, 25),
        ("LB", 32, 10),
        ("RDM", 44, 42),
        ("LDM", 44, 26),
        ("RAM", 64, 56),
        ("CAM", 66, 34),
        ("LAM", 64, 12),
        ("ST", 80, 34),
    ],
    "4-4-2": [
        ("GK", 5, 34),
        ("RB", 32, 58),
        ("RCB", 26, 43),
        ("LCB", 26, 25),
        ("LB", 32, 10),
        ("RM", 56, 58),
        ("RCM", 48, 42),
        ("LCM", 48, 26),
        ("LM", 56, 10),
        ("RS", 76, 42),
        ("LS", 76, 26),
    ],
    "3-5-2": [
        ("GK", 5, 34),
        ("RCB", 27, 48),
        ("CB", 25, 34),
        ("LCB", 27, 20),
        ("RWB", 52, 62),
        ("RCM", 48, 44),
        ("CM", 44, 34),
        ("LCM", 48, 24),
        ("LWB", 52, 6),
        ("RS", 76, 42),
        ("LS", 76, 26),
    ],
}

UNIT_OF_ROLE = {
    "GK": "goalkeeper",
    **dict.fromkeys(("RB", "RCB", "CB", "LCB", "LB", "RWB", "LWB"), "defence"),
    **dict.fromkeys(
        ("RCM", "CM", "LCM", "RDM", "LDM", "RAM", "CAM", "LAM", "RM", "LM"), "midfield"
    ),
    **dict.fromkeys(("RW", "ST", "LW", "RS", "LS"), "attack"),
}

# Off-ball sprints per minute at full energy, by unit.
SPRINT_RATE = {"goalkeeper": 0.02, "defence": 0.40, "midfield": 0.45, "attack": 0.55}

# Fictional surnames for the two curated clubs; other codes get numbered names.
NAMES = {
    "HC": [
        "Arvenne",
        "Bostrik",
        "Callodan",
        "Derrowe",
        "Eskmoor",
        "Farrelin",
        "Gollan",
        "Haverick",
        "Ilsom",
        "Jarrent",
        "Kesterby",
    ],
    "NV": [
        "Quillon",
        "Rastor",
        "Sevrin",
        "Tallowen",
        "Udrick",
        "Valcourt",
        "Wenlo",
        "Yarrick",
        "Zandor",
        "Ambrel",
        "Brennow",
    ],
}


@dataclass
class Player:
    player_id: str
    name: str
    role: str
    unit: str
    base_x: float
    base_y: float
    energy: float = 1.0


def build_lineup(team: TeamSpec) -> list[Player]:
    names = NAMES.get(team.code, [])
    lineup = []
    for i, (role, x, y) in enumerate(FORMATIONS[team.formation], start=1):
        name = names[i - 1] if i <= len(names) else f"{team.code} {i:02d}"
        lineup.append(Player(f"{team.code}-{i:02d}", name, role, UNIT_OF_ROLE[role], x, y))
    return lineup


def position(
    player: Player, *, attacking: bool, press_height: float, ball: tuple[float, float]
) -> tuple[float, float]:
    """Where a player stands right now, in his own team's frame."""
    if player.role == "GK":
        return (8.0 if attacking else 4.0), 34.0
    if attacking:
        x = player.base_x + 10
    else:
        x = player.base_x * (0.65 + 0.6 * press_height)  # a high press pushes the block up
    y = player.base_y + 0.25 * (ball[1] - 34)
    return min(max(x, 1.0), 104.0), min(max(y, 1.0), 67.0)
