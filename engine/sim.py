"""Possession-chain match simulator (spec §7.1).

A possession is a chain of actions (pass, carry, dribble, shot) by the team on the
ball while the other team presses according to its press height. Pressure makes
passes riskier and pushes the team on the ball to go long: the mechanism behind a
pressure shift. Every random draw comes from a keyed stream (engine.rng), so a run
without one intervention stays aligned with the run that has it. Coordinates are
in the acting team's attacking frame (engine.teams).
"""

import math

from contracts.clock import MatchClock
from contracts.event import Event, EventType, Outcome, PassQualifiers, Point, ShotQualifiers
from engine.params import ParamTimeline
from engine.rng import Streams
from engine.script import MatchScript, Side
from engine.teams import SPRINT_RATE, Player, build_lineup, position

PITCH_X, PITCH_Y = 105.0, 68.0
HALF = 45 * 60
HALF_TIME_BREAK_S = 15 * 60
KICKOFF_MS = 1_800_000_000_000
MAX_ACTIONS = 40
OPEN_PLAY_MAX_X = 97.0  # open play rarely reaches the six-yard box
FATIGUE_PER_MIN = 0.25 / 90


def other(side: Side) -> Side:
    return "away" if side == "home" else "home"


def mirror(p: tuple[float, float]) -> tuple[float, float]:
    return PITCH_X - p[0], PITCH_Y - p[1]


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def on_pitch(x: float, y: float) -> tuple[float, float]:
    return clamp(x, 0.5, PITCH_X - 0.5), clamp(y, 0.5, PITCH_Y - 0.5)


def ahead(x: float, y: float, dist: float, angle: float) -> tuple[float, float]:
    """A point `dist` metres away at `angle` radians, kept out of the six-yard box."""
    return on_pitch(min(x + dist * math.cos(angle), OPEN_PLAY_MAX_X), y + dist * math.sin(angle))


def clock_at(period: int, s: float) -> MatchClock:
    total = (0 if period == 1 else HALF) + int(s)
    return MatchClock(period=period, minute=total // 60, second=total % 60)


class MatchSim:
    def __init__(self, script: MatchScript, seed: int | None = None) -> None:
        self.script = script
        self.seed = script.seed if seed is None else seed
        self.rng = Streams(self.seed)
        self.params = ParamTimeline(script)
        self.lineups = {side: build_lineup(script.teams[side]) for side in ("home", "away")}
        self.score = {"home": 0, "away": 0}
        self.period_lengths: dict[int, float] = {}
        self.period = 1
        self.t = 0.0
        self.att: Side = "home"
        self.ball = (52.5, 34.0)
        self._ticked = -1
        self._pending: list[tuple[int, float, int, dict]] = []

    def run(self) -> list[Event]:
        for period in (1, 2):
            self._play_period(period)
        self._pending.sort(key=lambda e: (e[0], e[1], e[2]))
        match_id = self.script.match_id
        return [
            Event(event_id=f"{match_id}-{i:05d}", **fields)
            for i, (_, _, _, fields) in enumerate(self._pending, start=1)
        ]

    # --- time -----------------------------------------------------------------

    @property
    def minute(self) -> int:
        return ((0 if self.period == 1 else HALF) + int(self.t)) // 60

    @property
    def bucket(self) -> int:
        """Random-stream key: first-half stoppage (45+) and the second half's 45-47 differ."""
        return self.period * 100 + self.minute

    def _advance(self, seconds: float) -> None:
        self.t += seconds
        while self._ticked + 1 < self.minute:
            self._ticked += 1
            self._physical_minute(self._ticked)

    def _physical_minute(self, m: int) -> None:
        """Fatigue and off-ball sprints for one completed minute."""
        start = m * 60 - (0 if self.period == 1 else HALF)
        m = self.period * 100 + m  # stream bucket from here on
        for side in ("home", "away"):
            press = self.params.team(side, self.period, start)["press_height"]
            for p in self.lineups[side]:
                pid = p.player_id
                decay = self.params.player(side, pid, self.period, start)["stamina_decay"]
                p.energy = max(0.2, p.energy - FATIGUE_PER_MIN * decay)
                if not self.rng.chance(f"sprint:{pid}", m, SPRINT_RATE[p.unit] * p.energy**2):
                    continue
                s = start + self.rng.uniform(f"sprint_at:{pid}", m, 0, 59)
                ball = self.ball if side == self.att else mirror(self.ball)
                x, y = position(p, attacking=side == self.att, press_height=press, ball=ball)
                dist = self.rng.uniform(f"sprint_dist:{pid}", m, 12, 40)
                ex = x + dist if x + dist <= PITCH_X - 0.5 else x - dist  # stay on the pitch
                speed = 25 + 8 * p.energy + self.rng.normal(f"sprint_speed:{pid}", m, 0, 1.5)
                self._emit(
                    EventType.SPRINT,
                    side,
                    p,
                    start=(x, y),
                    end=(ex, y),
                    at=s,
                    qualifiers={
                        "speed_kmh": round(clamp(speed, 24.5, 36.0), 1),
                        "distance_m": round(dist, 1),
                    },
                )

    # --- periods and possessions ----------------------------------------------

    def _play_period(self, period: int) -> None:
        self.period, self.t = period, 0.0
        self._ticked = (0 if period == 1 else 45) - 1
        stoppage_minutes = 1 + int(self.rng.uniform("stoppage", period, 0, 3 if period == 1 else 5))
        end = HALF + 60 * stoppage_minutes
        self.period_lengths[period] = end
        self._emit(EventType.PERIOD_START, "home", None, start=None)
        att: Side = "home" if period == 1 else "away"
        ball = (52.5, 34.0)
        self._emit(
            EventType.SET_PIECE,
            att,
            self._nearest(att, ball),
            start=ball,
            qualifiers={"kind": "kick_off"},
        )
        while self.t < end:
            att, ball = self._possession(att, ball, end)
        self._emit(EventType.PERIOD_END, "home", None, start=None)

    def _possession(self, att: Side, ball: tuple[float, float], end: float):
        deff = other(att)
        self.att, self.ball = att, ball
        carrier = self._nearest(att, ball)
        for _ in range(MAX_ACTIONS):
            if self.t >= end:
                break
            m = self.bucket
            tp = self.params.team(att, self.period, self.t)
            press = self.params.team(deff, self.period, self.t)["press_height"]
            press = clamp(press + self.rng.normal("press_jitter", m, 0, 0.03), 0, 1)
            pressure = self._maybe_press(deff, self.ball, press)
            x, y = self.ball
            shooting_zone = x > 80 and abs(y - 34) < 20
            if shooting_zone and self.rng.chance("shot_choice", m, 0.05 + 0.006 * (x - 80)):
                return self._shot(att, carrier)
            roll = self.rng.uniform("action_choice", m)
            if roll < 0.72:
                kept, who, where = self._pass(att, carrier, tp, pressure)
            elif pressure > 0 and roll < 0.82:
                kept, who, where = self._dribble(att, carrier)
            else:
                kept, who, where = self._carry(att, carrier, pressure)
            if not kept:
                return deff, where
            carrier, self.ball = who, where
        return deff, mirror(self.ball)

    def _maybe_press(self, deff: Side, ball: tuple[float, float], press: float) -> float:
        m = self.bucket
        if ball[0] < 63:  # the attacker's first 60%: where pressing happens
            p_press = 0.06 + 0.62 * press
            intensity = 0.25 + 0.6 * press + self.rng.normal("press_intensity", m, 0, 0.08)
        else:
            p_press = 0.30
            intensity = 0.45 + self.rng.normal("press_intensity", m, 0, 0.10)
        if not self.rng.chance("press_event", m, p_press):
            return 0.0
        where = mirror(ball)
        self._emit(EventType.PRESSURE, deff, self._nearest(deff, where), start=where)
        self._advance(0.8)
        return clamp(intensity, 0.0, 1.0)

    # --- actions: each returns (kept, player, ball position in the new owner's frame)

    def _pass(self, att: Side, carrier: Player, tp: dict[str, float], pressure: float):
        m = self.bucket
        x, y = self.ball
        long_p = clamp(tp["directness"] + 0.9 * pressure, 0.0, 0.9) if x < 70 else 0.05
        is_long = self.rng.chance("pass_length", m, long_p)
        if is_long:
            dist = self.rng.uniform("pass_dist", m, 30, 55)
            angle = self.rng.normal("pass_angle", m, 0, 0.35)
        else:
            dist = self.rng.uniform("pass_dist", m, 6, 24)
            angle = self.rng.normal("pass_angle", m, 0, 1.0)
        tx, ty = ahead(x, y, dist, angle)
        dist = math.hypot(tx - x, ty - y)
        receiver = self._nearest(att, (tx, ty), exclude=carrier)
        p_ok = 0.99 - 0.005 * dist - 0.28 * pressure + 0.16 * (tp["quality"] - 0.5)
        p_ok -= 0.10 if is_long else 0.0
        p_ok -= 0.15 if tx > 88 else 0.0  # passes into the box are contested
        ok = self.rng.chance("pass_success", m, clamp(p_ok, 0.05, 0.98))
        speed = clamp(30 + 1.1 * dist + self.rng.normal("ball_speed", m, 0, 6), 15, 120)
        self._emit(
            EventType.PASS,
            att,
            carrier,
            start=(x, y),
            end=(tx, ty),
            outcome=Outcome.COMPLETE if ok else Outcome.INCOMPLETE,
            pass_q=PassQualifiers(
                distance_m=round(dist, 1),
                ball_speed_kmh=round(speed, 1),
                pressure_on_passer=round(pressure, 2),
                receiver_id=receiver.player_id,
            ),
        )
        self._advance(1.6 + dist / 14)
        if ok:
            return True, receiver, (tx, ty)
        deff = other(att)
        lost_at = mirror((tx, ty))
        if ty < 3 or ty > PITCH_Y - 3:  # out for a throw-in
            spot = on_pitch(lost_at[0], 0.5 if lost_at[1] < 34 else PITCH_Y - 0.5)
            self._restart(deff, spot, "throw_in", self.rng.uniform("restart_delay", m, 10, 25))
            return False, None, spot
        winner = self._nearest(deff, lost_at)
        self._emit(EventType.INTERCEPTION, deff, winner, start=lost_at, outcome=Outcome.WON)
        self._emit(EventType.POSSESSION_CHANGE, deff, winner, start=lost_at)
        self._advance(1.0)
        return False, winner, lost_at

    def _carry(self, att: Side, carrier: Player, pressure: float):
        m = self.bucket
        x, y = self.ball
        dist = self.rng.uniform("carry_dist", m, 4, 14)
        ex, ey = ahead(x, y, dist, self.rng.normal("carry_angle", m, 0, 0.6))
        self._emit(EventType.CARRY, att, carrier, start=(x, y), end=(ex, ey))
        self._advance(dist / 4.0)
        if not self.rng.chance("tackle", m, 0.08 + 0.25 * pressure):
            return True, carrier, (ex, ey)
        return self._challenge(att, (ex, ey))

    def _dribble(self, att: Side, carrier: Player):
        m = self.bucket
        x, y = self.ball
        ex, ey = ahead(x, y, self.rng.uniform("dribble_dist", m, 3, 7), 0.0)
        won = self.rng.chance("dribble_success", m, 0.55)
        self._emit(
            EventType.DRIBBLE,
            att,
            carrier,
            start=(x, y),
            end=(ex, ey),
            outcome=Outcome.COMPLETE if won else Outcome.INCOMPLETE,
        )
        self._advance(2.0)
        return (True, carrier, (ex, ey)) if won else self._challenge(att, (ex, ey))

    def _challenge(self, att: Side, at: tuple[float, float]):
        """A defender wins the ball, or fouls and gives away a free kick."""
        m = self.bucket
        deff = other(att)
        where = mirror(at)
        defender = self._nearest(deff, where)
        if self.rng.chance("foul", m, 0.15):
            self._emit(EventType.FOUL, deff, defender, start=where)
            self._restart(att, at, "free_kick", self.rng.uniform("restart_delay", m, 15, 35))
            return True, self._nearest(att, at), at
        self._emit(EventType.TACKLE, deff, defender, start=where, outcome=Outcome.WON)
        self._emit(EventType.POSSESSION_CHANGE, deff, defender, start=where)
        self._advance(1.0)
        return False, defender, where

    def _shot(self, att: Side, shooter: Player):
        m = self.bucket
        x, y = self.ball
        dx, dy = PITCH_X - x, y - 34.0
        dist = math.hypot(dx, dy)
        angle = math.degrees(math.atan2(7.32 * dx, dx * dx + dy * dy - 3.66**2))
        defenders = max(0, round(self.rng.normal("shot_defenders", m, 1.2 + (x - 85) / 15, 0.9)))
        xg = 1 / (1 + math.exp(-(-1.15 - 0.10 * dist + 0.03 * angle - 0.30 * defenders)))
        r = self.rng.uniform("shot_outcome", m)
        if r < xg:
            outcome = Outcome.GOAL
        elif r < xg + 0.25:
            outcome = Outcome.ON_TARGET
        elif r < xg + 0.45:
            outcome = Outcome.BLOCKED
        else:
            outcome = Outcome.OFF_TARGET
        speed = clamp(self.rng.normal("shot_speed", m, 88, 14), 40, 135)
        self._emit(
            EventType.SHOT,
            att,
            shooter,
            start=(x, y),
            end=(PITCH_X, 34.0),
            outcome=outcome,
            body_part="head" if self.rng.chance("shot_body", m, 0.12) else "foot",
            shot_q=ShotQualifiers(
                shot_speed_kmh=round(speed, 1),
                distance_m=round(dist, 1),
                angle_deg=round(angle, 1),
                defenders_in_cone=defenders,
            ),
        )
        self._advance(2.0)
        deff = other(att)
        if outcome == Outcome.GOAL:
            self.score[att] += 1
            self._emit(EventType.GOAL, att, shooter, start=(x, y), outcome=Outcome.GOAL)
            self._restart(deff, (52.5, 34.0), "kick_off", 45.0)
            return deff, (52.5, 34.0)
        self._restart(deff, (6.0, 34.0), "goal_kick", self.rng.uniform("restart_delay", m, 8, 20))
        return deff, (6.0, 34.0)

    def _restart(self, side: Side, spot: tuple[float, float], kind: str, pause: float) -> None:
        self._advance(pause)
        self._emit(
            EventType.SET_PIECE,
            side,
            self._nearest(side, spot),
            start=spot,
            qualifiers={"kind": kind},
        )

    # --- helpers --------------------------------------------------------------

    def _nearest(
        self, side: Side, point: tuple[float, float], exclude: Player | None = None
    ) -> Player:
        press = self.params.team(side, self.period, self.t)["press_height"]
        attacking = side == self.att
        ball = self.ball if attacking else mirror(self.ball)
        best, best_d = None, math.inf
        for p in self.lineups[side]:
            if p is exclude:
                continue
            px, py = position(p, attacking=attacking, press_height=press, ball=ball)
            d = (px - point[0]) ** 2 + (py - point[1]) ** 2
            if d < best_d:
                best, best_d = p, d
        return best

    def _emit(
        self,
        etype: EventType,
        side: Side,
        player: Player | None,
        *,
        start: tuple[float, float] | None,
        end: tuple[float, float] | None = None,
        outcome: Outcome = Outcome.NA,
        body_part: str | None = None,
        pass_q: PassQualifiers | None = None,
        shot_q: ShotQualifiers | None = None,
        qualifiers: dict | None = None,
        at: float | None = None,
    ) -> None:
        s = self.t if at is None else at
        elapsed = s if self.period == 1 else self.period_lengths[1] + HALF_TIME_BREAK_S + s
        fields = {
            "match_id": self.script.match_id,
            "clock": clock_at(self.period, s),
            "wall_clock_ms": KICKOFF_MS + int(elapsed * 1000),
            "type": etype,
            "team": self.script.teams[side].name,
            "player_id": player.player_id if player else None,
            "position": player.role if player else None,
            "start": Point(x=round(start[0], 1), y=round(start[1], 1)) if start else None,
            "end": Point(x=round(end[0], 1), y=round(end[1], 1)) if end else None,
            "outcome": outcome,
            "body_part": body_part,
            "pass_q": pass_q,
            "shot_q": shot_q,
            "qualifiers": qualifiers or {},
        }
        self._pending.append((self.period, s, len(self._pending), fields))
