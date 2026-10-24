"""Role instructions and the prompts each step sends. The instructions are fixed per role,
so the model provider can cache them; the prompt carries the case."""

import json

from contracts.case import Case
from contracts.meta import MatchMeta
from contracts.taxonomy import DOMAIN_OF_AGENT, AgentRole, Cause

METRIC_LIST = """\
- pressure_rate (team): the team's pressures in the opponent's first 60% of the pitch per \
opponent pass, carry or dribble starting there. A first half is often 0.2-0.5.
- long_ball_share (team): share of the team's passes longer than 30 m. A first half is often \
0.05-0.2.
- channel_share_left / channel_share_centre / channel_share_right (team): share of the \
team's passes, carries and dribbles starting in that third of the width.
- sprint_count (team, "Team.defence", "Team.midfield", "Team.attack", or a player id): \
sprints per minute of play. Sprints fall late in every match; the normal range allows for it.
- sprint_speed (same subjects): mean sprint speed in km/h. It falls late in every match too."""

METRICS = f"""{METRIC_LIST}
Every change is measured against the first half and read in standard deviations (sd) of how \
far that metric moves in ordinary play over the same window and minute, so min_change is in \
sd: about 1 sd is a common swing, 2 sd an unusual one, 3 sd rare. A claim under 1 sd is \
refused."""

RULES = """\
You never compute or estimate a number. You pre-register predictions; code tests each one \
with deterministic tools, comparing the case's window with the first half, and judges it.
Code has already confirmed the change the detector saw, and the card will report it: every \
hypothesis is an explanation of that change. Each names one cause and one prediction that \
would hold if that cause were present: the metric, whose metric it is, the direction, and the \
smallest change that would count. The prediction is your cause's evidence, so think about \
what the cause would do on the pitch, to both teams, and choose one that would hold under it \
but not under the other causes: re-measuring the confirmed change proves nothing new. A \
change in one team is often the other team's doing.
The match's facts limit the causes: a team chases the result only when behind and protects \
a lead only when ahead, a change in numbers needs a sending-off, and fresh legs need a \
substitution by that team; code refuses each otherwise. Register nothing for a cause the \
case gives no reason to suspect, even if that leaves you nothing to register."""


def _causes(role: AgentRole) -> list[str]:
    plantable = [c for c in Cause if c.domain != "fallback"]
    if role == AgentRole.SINGLE:
        return [c.value for c in plantable]
    return [c.value for c in plantable if c.domain == DOMAIN_OF_AGENT[role]]


def instructions(role: AgentRole, max_hypotheses: int) -> str:
    scope = (
        "You investigate alone, across every domain: tactics, physical and game state."
        if role == AgentRole.SINGLE
        else f"You are the {DOMAIN_OF_AGENT[role].replace('_', ' ')} specialist."
    )
    return (
        "You investigate one detected moment in a football match, from event data.\n"
        f"{scope}\n\n{RULES}\n\nCauses you may register:\n- "
        + "\n- ".join(_causes(role))
        + f"\n\nMeasurable metrics:\n{METRICS}\n\nRegister at most {max_hypotheses} hypotheses."
    )


# Put to a specialist whose causes are all on one team's side (agents.investigation.register).
BOTH_SIDES = (
    "\nYour causes are all on {team}'s side. A change in one team's numbers is often the other "
    "team's doing: register your hypotheses again, with at least one cause on {other}'s side if "
    "the match gives any reason for one."
)

STATE_KEYS = ("goals", "sent_off", "substitutions")

RANKING = """\
You rank the hypotheses that survived testing for one detected moment in a football match.
Code has already tested each one against deterministic tools; you never compute or change a \
number. Weigh everything the investigation found: each hypothesis's own test, every \
corollary, control or counter-test other specialists ran on it, and the score. The primary \
cause is the one the evidence supports best and its rivals explain least well. A hypothesis \
whose own test only re-measured the detected change ("predicts_the_detected_change") has \
shown that the change happened, not that its cause made it; without a corollary or control \
on it that held, it is weaker than one with evidence of its own. A weakened test makes a \
cause less certain, not wrong. A secondary cause is real but explains less. If nothing \
survived, the outcome is 'none'. If the effect is real but the evidence contradicts every \
surviving cause, the outcome is 'other'. Otherwise it is 'explained', with the best \
supported cause as primary."""


def both_teams(case: Case) -> list[dict]:
    """Each team's main numbers over the case's window, as code measured them."""
    return [
        {
            "metric": r.metric.value,
            "team": r.subject,
            "first_half": round(r.baseline_value, 3),
            "window": round(r.value, 3),
            "sd": r.sigmas,
        }
        for r in case.both_teams
    ]


def state_at(meta: MatchMeta, state: dict[str, float]) -> dict[str, dict[str, int]]:
    """Each team's goals, players sent off and substitutions so far."""
    return {
        meta.teams[s].name: {k: int(state.get(f"{s}_{k}", 0)) for k in STATE_KEYS}
        for s in ("home", "away")
    }


def match(meta: MatchMeta) -> dict:
    return {
        side: {
            "team": team.name,
            "players": [f"{p.player_id} {p.role} ({p.unit})" for p in team.players],
        }
        for side, team in meta.teams.items()
    }


def roster(meta: MatchMeta) -> dict:
    """The teams with each player's name, for whoever reads a viewer's words: a viewer asks
    about a player by name."""
    return {
        side: {
            "team": team.name,
            "players": [f"{p.player_id} {p.name}, {p.role} ({p.unit})" for p in team.players],
        }
        for side, team in meta.teams.items()
    }


def case_prompt(case: Case, meta: MatchMeta, score: dict[str, float]) -> str:
    """What a specialist pre-registers from: the change and the match's facts, never another
    number code has measured, so no prediction can copy one."""
    moment = {
        "moment": case.moment_type.value,
        "window": str(case.window),
        "detected_at": str(case.detected_at or case.window.end),
        "confirmed": (
            f"code re-measured the change over {case.detected_at}-{case.window.end}, after "
            "the detector fired, and it held beyond normal variation"
            if case.detected_at
            else "not re-measured after detection"
        ),
        "state_at_detection": state_at(meta, score),
        "what_the_detector_saw": [
            {
                "metric": t.metric.value,
                "subject": t.subject,
                "first_half": round(t.baseline_value, 3),
                "window": round(t.value, 3),
                "sample": t.n_events,
            }
            for t in case.triggers
        ],
        "match": match(meta),
    }
    return "Pre-register your hypotheses for this moment.\n" + json.dumps(moment, indent=1)


def ranking_prompt(
    case: Case, survivors: list[dict], score: dict[str, float], meta: MatchMeta
) -> str:
    return "Rank these surviving hypotheses.\n" + json.dumps(
        {
            "moment": case.moment_type.value,
            "window": str(case.window),
            "state_at_detection": state_at(meta, score),
            "both_teams": both_teams(case),
            "survivors": survivors,
        },
        indent=1,
    )


FOLLOW_UP = f"""\
You are one side of an open question about a moment in a football match. Several causes \
survived testing for the same change and the data so far cannot tell them apart: yours is \
"your_cause", the others are "rival_causes". You never compute or estimate a number.
Pre-register one prediction for "minutes_to_predict", which nobody has seen yet, that would \
come true under your cause and under none of the rivals': either a metric your cause moves \
and theirs would leave at ordinary play (direction "up" or "down"), or one your cause leaves \
at ordinary play where theirs would move it (direction "flat"). Think about what each cause \
would make each team do on the pitch from now on. Code measures it once those minutes \
are played, against the first half: a move counts at 1.5 sd or more, and ordinary play is \
within 1 sd. Only one side's prediction coming true settles the question.

Measurable metrics:
{METRIC_LIST}"""


def follow_up_prompt(
    case: Case,
    meta: MatchMeta,
    score: dict[str, float],
    own: dict,
    rivals: list[dict],
    minutes: str,
) -> str:
    return "Pre-register your decisive test.\n" + json.dumps(
        {
            "moment": case.moment_type.value,
            "window": str(case.window),
            "state_now": state_at(meta, score),
            "both_teams": both_teams(case),
            "your_cause": own,
            "rival_causes": rivals,
            "minutes_to_predict": minutes,
            "match": match(meta),
        },
        indent=1,
    )
