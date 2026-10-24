"""Narrator templates (spec §9.3): each variant is written from a card's verified
propositions and evidence at its language level, in English and Spanish. Every number in
the text comes from the card's evidence, so the Verifier's number check can hold it to that.
A model-written narrator replaces these later; they stay as its fallback.
"""

from agents.confirm import PERSIST_SD
from contracts.card import InsightCard
from contracts.case_file import Persistence
from contracts.meta import MatchMeta
from contracts.prediction import Direction
from contracts.question import Premise
from contracts.taxonomy import LANGUAGE_FOR_SUPPORT, Cause, LanguageLevel, Metric, SupportLevel
from state.subjects import resolve

CHANGE = {  # (metric, direction) -> (English with {is}, Spanish)
    (Metric.PRESSURE_RATE, Direction.UP): ("{is} pressing harder", "presiona con más intensidad"),
    (Metric.PRESSURE_RATE, Direction.DOWN): ("{is} pressing less", "presiona menos"),
    (Metric.LONG_BALL_SHARE, Direction.UP): (
        "{is} going long more often",
        "juega en largo más a menudo",
    ),
    (Metric.LONG_BALL_SHARE, Direction.DOWN): (
        "{is} going long less often",
        "juega menos en largo",
    ),
    (Metric.SPRINT_COUNT, Direction.DOWN): ("{is} sprinting less", "esprinta menos"),
    (Metric.SPRINT_COUNT, Direction.UP): ("{is} sprinting more", "esprinta más"),
    (Metric.SPRINT_SPEED, Direction.DOWN): ("{is} sprinting more slowly", "esprinta más despacio"),
    (Metric.SPRINT_SPEED, Direction.UP): ("{is} sprinting faster", "esprinta más rápido"),
    (Metric.CHANNEL_SHARE_LEFT, Direction.UP): (
        "{is} playing more down the left",
        "juega más por la izquierda",
    ),
    (Metric.CHANNEL_SHARE_LEFT, Direction.DOWN): (
        "{is} playing less down the left",
        "juega menos por la izquierda",
    ),
    (Metric.CHANNEL_SHARE_CENTRE, Direction.UP): (
        "{is} playing more through the middle",
        "juega más por el centro",
    ),
    (Metric.CHANNEL_SHARE_CENTRE, Direction.DOWN): (
        "{is} playing less through the middle",
        "juega menos por el centro",
    ),
    (Metric.CHANNEL_SHARE_RIGHT, Direction.UP): (
        "{is} playing more down the right",
        "juega más por la derecha",
    ),
    (Metric.CHANNEL_SHARE_RIGHT, Direction.DOWN): (
        "{is} playing less down the right",
        "juega menos por la derecha",
    ),
}
CAUSE = {  # {team} is the team the cause is about
    Cause.PRESS_INTENSITY_UP: (
        "a deliberate step up in {team}'s press",
        "un aumento deliberado de la presión de {team}",
    ),
    Cause.PRESS_INTENSITY_DOWN: (
        "a deliberate drop in {team}'s press",
        "una bajada deliberada de la presión de {team}",
    ),
    Cause.BLOCK_DEEPER: ("{team} sitting in a deeper block", "{team} defendiendo más atrás"),
    Cause.BLOCK_HIGHER: ("{team} pushing their block higher", "{team} adelantando su bloque"),
    Cause.FORMATION_CHANGE: ("a change of shape by {team}", "un cambio de sistema de {team}"),
    Cause.FLANK_OVERLOAD: ("{team} overloading one flank", "{team} sobrecargando una banda"),
    Cause.UNIT_FATIGUE: ("tiring legs in {team}'s side", "el cansancio en {team}"),
    Cause.PLAYER_FATIGUE: ("a tiring {team} player", "un jugador de {team} que se cansa"),
    Cause.FRESH_LEGS_SUBSTITUTION: (
        "fresh legs off {team}'s bench",
        "piernas frescas del banquillo de {team}",
    ),
    Cause.PROTECTING_LEAD: ("{team} protecting their lead", "{team} protegiendo su ventaja"),
    Cause.CHASING_RESULT: ("{team} chasing the result", "{team} buscando el resultado"),
    Cause.NUMERICAL_CHANGE: (
        "a change in numbers on the pitch",
        "un cambio en el número de jugadores",
    ),
    Cause.OTHER: ("something outside the usual explanations", "algo fuera de lo habitual"),
}


def cause_phrase(cause: Cause, team: str, locale: int) -> str:
    return CAUSE[cause][locale].format(team=team)


LEVEL = {
    LanguageLevel.ASSERTIVE: ("That is {cause}.", "Es {cause}."),
    LanguageLevel.MEASURED: ("It looks like {cause}.", "Parece {cause}."),
    LanguageLevel.TENTATIVE: ("It may be {cause}.", "Puede ser {cause}."),
}
LABEL = {
    Metric.PRESSURE_RATE: ("Pressure rate", "Tasa de presión"),
    Metric.LONG_BALL_SHARE: ("Long-ball share", "Proporción de balones largos"),
    Metric.SPRINT_COUNT: ("Sprints a minute", "Esprints por minuto"),
    Metric.SPRINT_SPEED: ("Sprint speed", "Velocidad de esprint"),
    Metric.CHANNEL_SHARE_LEFT: ("Share down the left", "Proporción por la izquierda"),
    Metric.CHANNEL_SHARE_CENTRE: ("Share through the middle", "Proporción por el centro"),
    Metric.CHANNEL_SHARE_RIGHT: ("Share down the right", "Proporción por la derecha"),
}
SUPPORT = {
    "strong": ("strong", "fuerte"),
    "moderate": ("moderate", "moderado"),
    "weak": ("weak", "débil"),
}
LOCALES = ("en", "es")


def number(metric: Metric, value: float) -> str:
    """How a value of `metric` is written, everywhere it appears."""
    if "share" in metric.value:  # long-ball and channel shares
        return f"{round(value * 100)}%"
    if metric == Metric.SPRINT_SPEED:
        return f"{value:.1f} km/h"
    return f"{value:.2f}"


def who(meta: MatchMeta, subject: str) -> tuple[str, bool]:
    """(the subject as written, whether it takes a singular verb in English)."""
    who = resolve(meta, subject)
    if who.player_id:
        team = next(t for t in meta.teams.values() if t.name == who.team)
        return next(p.name for p in team.players if p.player_id == who.player_id), True
    if who.unit:
        return f"{who.team}'s {who.unit}", True
    return who.team, False


def _sentence(card: InsightCard, meta: MatchMeta, locale: int) -> str:
    change = next(p for p in card.propositions if p.type == "change")
    name, singular = who(meta, change.subject)
    en, es = CHANGE[change.metric, change.direction]
    start = change.window.start.minute
    if locale == 0:
        text = en.format(
            **{"is": "is" if singular else "are", "has": "has" if singular else "have"}
        )
        return f"{name} {text} since {start}'."
    return f"{name} {es} desde el minuto {start}."


def claim(card: InsightCard, meta: MatchMeta) -> str:
    return _sentence(card, meta, 0)


def variants(
    card: InsightCard, meta: MatchMeta, support: SupportLevel
) -> dict[str, dict[str, str]]:
    """Casual and analyst text in every locale, at the language level `support` allows."""
    level = LANGUAGE_FOR_SUPPORT[support]
    primary = card.primary_cause
    out: dict[str, dict[str, str]] = {"casual": {}, "analyst": {}}
    for i, locale in enumerate(LOCALES):
        team = card.subject.team
        because = LEVEL[level][i].format(cause=cause_phrase(primary.cause, team, i))
        out["casual"][locale] = f"{_sentence(card, meta, i)} {because}"
        facts = []
        for ev in card.evidence:
            facts.append(
                f"{LABEL[ev.metric][i]} ({who(meta, ev.subject)[0]}): "
                f"{number(ev.metric, ev.baseline.value)} → {number(ev.metric, ev.value)}"
            )
        ruled = [cause_phrase(r.taxonomy, r.team or team, i) for r in card.rejected_alternatives]
        strength = SUPPORT[support.value][i]
        window = (
            f"{card.timing.change_window.start.minute}'-{card.timing.change_window.end.minute}'"
        )
        if i == 0:
            text = f"{'; '.join(facts)}, {window} against the first half. {because}"
            text += f" Ruled out: {', '.join(ruled)}." if ruled else ""
            text += f" Support: {strength}."
        else:
            text = f"{'; '.join(facts)}, {window} frente a la primera parte. {because}"
            text += f" Descartado: {', '.join(ruled)}." if ruled else ""
            text += f" Apoyo: {strength}."
        out["analyst"][locale] = text
    return out


WITHDRAWN = (
    "Corrected data no longer show that {sentence} This card is withdrawn.",
    "Los datos corregidos ya no muestran que {sentence} Retiramos esta tarjeta.",
)
WAS = ("was", "antes")
UPDATED = ("Updated after a data correction: ", "Actualizado tras una corrección de datos: ")


def withdrawal(
    card: InsightCard, was: InsightCard, meta: MatchMeta
) -> tuple[str, dict[str, dict[str, str]]]:
    """(claim, variants) for a card the corrected feed no longer supports: the change it
    claimed, and each number now against what was shown. Deterministic facts only."""
    shown = {(e.metric, e.subject): e for e in was.evidence}
    out: dict[str, dict[str, str]] = {"casual": {}, "analyst": {}}
    for i, locale in enumerate(LOCALES):
        notice = WITHDRAWN[i].format(sentence=_sentence(card, meta, i))
        facts = []
        for ev in card.evidence:
            line = (
                f"{LABEL[ev.metric][i]} ({who(meta, ev.subject)[0]}): "
                f"{number(ev.metric, ev.baseline.value)} → {number(ev.metric, ev.value)}"
            )
            before = shown.get((ev.metric, ev.subject))
            if before and before.value != ev.value:
                line += f", {WAS[i]} {number(ev.metric, before.value)}"
            facts.append(line)
        out["casual"][locale] = notice
        out["analyst"][locale] = f"{'; '.join(facts)}. {notice}"
    return out["casual"]["en"], out


def updated(variants: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
    """A revision's text, marked as an update so every surface shows it replaced the card."""
    return {
        audience: {locale: UPDATED[LOCALES.index(locale)] + text for locale, text in texts.items()}
        for audience, texts in variants.items()
    }


# (metric, direction) -> a broadcast headline, English and Spanish. A headline names the
# change only: it airs whatever the card's cause and support, and the Verifier reads no headline.
HEADLINE = {
    (Metric.PRESSURE_RATE, Direction.UP): ("PRESS RAISED", "MÁS PRESIÓN"),
    (Metric.PRESSURE_RATE, Direction.DOWN): ("PRESS DROPPED", "MENOS PRESIÓN"),
    (Metric.LONG_BALL_SHARE, Direction.UP): ("GOING LONG", "JUEGO DIRECTO"),
    (Metric.LONG_BALL_SHARE, Direction.DOWN): ("PLAYING SHORT", "JUEGO CORTO"),
    (Metric.SPRINT_COUNT, Direction.DOWN): ("FEWER SPRINTS", "MENOS ESPRINTS"),
    (Metric.SPRINT_COUNT, Direction.UP): ("MORE SPRINTS", "MÁS ESPRINTS"),
    (Metric.SPRINT_SPEED, Direction.DOWN): ("SLOWER SPRINTS", "ESPRINTS MÁS LENTOS"),
    (Metric.SPRINT_SPEED, Direction.UP): ("FASTER SPRINTS", "ESPRINTS MÁS RÁPIDOS"),
    (Metric.CHANNEL_SHARE_LEFT, Direction.UP): ("DOWN THE LEFT", "POR LA IZQUIERDA"),
    (Metric.CHANNEL_SHARE_LEFT, Direction.DOWN): ("LESS DOWN THE LEFT", "MENOS POR LA IZQUIERDA"),
    (Metric.CHANNEL_SHARE_CENTRE, Direction.UP): ("THROUGH THE MIDDLE", "POR EL CENTRO"),
    (Metric.CHANNEL_SHARE_CENTRE, Direction.DOWN): ("LESS IN THE MIDDLE", "MENOS POR EL CENTRO"),
    (Metric.CHANNEL_SHARE_RIGHT, Direction.UP): ("DOWN THE RIGHT", "POR LA DERECHA"),
    (Metric.CHANNEL_SHARE_RIGHT, Direction.DOWN): ("LESS DOWN THE RIGHT", "MENOS POR LA DERECHA"),
}
CORRECTION_HEADLINE = {
    "revised": ("UPDATE", "ACTUALIZACIÓN"),
    "withdrawn": ("WITHDRAWN", "RETIRADA"),
}
GOAL = ("Goal for {team}! {score}.", "¡Gol del {team}! {score}.")


def broadcast(card: InsightCard, meta: MatchMeta, locale: int) -> dict[str, str | float]:
    """Fields for the card's overlay graphic: a headline, the stat and its two values."""
    change = next(p for p in card.propositions if p.type == "change")
    ev = card.evidence[0]
    if card.status in CORRECTION_HEADLINE:
        return {
            "team": card.subject.team,
            "headline": CORRECTION_HEADLINE[card.status][locale],
            "text": card.variants["casual"][LOCALES[locale]],
        }
    return {
        "team": card.subject.team,
        "headline": HEADLINE[change.metric, change.direction][locale],
        "stat_label": f"{LABEL[ev.metric][locale]} ({who(meta, ev.subject)[0]})",
        "metric": ev.metric.value,
        "before": ev.baseline.value,
        "after": ev.value,
    }


def goal(team: str, score: str) -> dict[str, str]:
    """A fast-lane goal line in every locale, from the event alone."""
    return {locale: GOAL[i].format(team=team, score=score) for i, locale in enumerate(LOCALES)}


# A viewer's question, answered from what code found (spec §9.3). Deterministic facts only.
NOT_HAPPENING = (
    "Not beyond ordinary play: {label} ({who}) has been {now} since {since}', against {then} "
    "in the first half.",
    "No más allá de lo normal: {label} ({who}) es {now} desde el minuto {since}, frente a {then} "
    "en la primera parte.",
)
OTHER_WAY = (  # the premise's change went the opposite way, beyond ordinary play
    "The other way: {label} ({who}) has been {now} since {since}', against {then} in the first "
    "half.",
    "Al contrario: {label} ({who}) es {now} desde el minuto {since}, frente a {then} en la "
    "primera parte.",
)
NO_CAUSE = (
    "{who} {change} since {since}', but no cause stands up to the evidence yet.",
    "{who} {change_es} desde el minuto {since}, pero ninguna causa resiste la evidencia todavía.",
)
UNVERIFIED = (
    "{who} {change} since {since}'; the explanation did not pass verification, so we hold it back.",
    "{who} {change_es} desde el minuto {since}; la explicación no superó la verificación, así que "
    "no la mostramos.",
)
CANNOT = (
    "Proofline cannot measure that from the match data.",
    "Proofline no puede medir eso con los datos del partido.",
)


def answer(
    outcome: str,
    premise: Premise | None,
    test: Persistence | None,
    card: InsightCard | None,
    meta: MatchMeta,
) -> dict[str, str]:
    """The answer a viewer reads, in each locale."""
    if premise is None:
        return dict(zip(LOCALES, CANNOT, strict=True))
    if card is not None:
        return dict(card.variants["casual"])
    name, singular = who(meta, premise.subject)
    since = premise.since.minute
    if outcome == "premise_false":
        facts = {"label": "", "who": name, "since": since, "now": "-", "then": "-"}
        up = premise.direction == Direction.UP
        if test is not None and test.value is not None and test.baseline is not None:
            facts |= {
                "now": number(premise.metric, test.value),
                "then": number(premise.metric, test.baseline),
            }
        z = test.sigmas if test is not None else None
        reversed_ = z is not None and (z <= -PERSIST_SD if up else z >= PERSIST_SD)
        template = OTHER_WAY if reversed_ else NOT_HAPPENING
        return {
            locale: template[i].format(**facts | {"label": LABEL[premise.metric][i]})
            for i, locale in enumerate(LOCALES)
        }
    en, es = CHANGE[premise.metric, premise.direction]
    change = en.format(**{"is": "is" if singular else "are"})
    template = NO_CAUSE if outcome in ("none", "other") else UNVERIFIED
    return {
        locale: template[i].format(who=name, change=change, change_es=es, since=since)
        for i, locale in enumerate(LOCALES)
    }
