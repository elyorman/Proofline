"""Evaluation run record. Every number in the README comes from one of these."""

import hashlib
import json
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from contracts.card import Verification
from contracts.prediction import Direction
from contracts.taxonomy import CaseOutcome, Cause, Metric

VISIBILITY_SDS = 2.0  # spec §7.2: separation a script needs on at least one observable
MIN_SEED_PAIRS = 20  # spec §7.2: each script is estimated over 20-30 seed pairs


class Variant(StrEnum):
    A_PROOFLINE = "A"
    B_SINGLE_AGENT = "B"
    C_NO_CROSS_EXAM = "C"  # stretch


class Suite(StrEnum):
    PLANTED = "planted"
    DECOYS = "decoys"
    CORRECTIONS = "corrections"
    CONFOUNDED = "confounded"  # stretch
    SEEDED_FALSE_CLAIMS = "seeded_false_claims"
    QUESTIONS = "questions"


class Split(StrEnum):
    DEV = "dev"
    HELDOUT = "heldout"


# Spec §11.1: the seeds each split's suites and paired runs are drawn from.
SEED_RANGES = {Split.DEV: range(1000, 2000), Split.HELDOUT: range(2000, 3000)}


class MetricEstimate(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    name: str
    suite: Suite | Literal["combined"]
    value: float
    ci_low: float | None = None
    ci_high: float | None = None
    n: int = Field(ge=0)
    ci_method: Literal["wilson", "paired_match_bootstrap"] | None = None

    @model_validator(mode="after")
    def _ci_brackets_value(self) -> "MetricEstimate":
        if (self.ci_low is None) != (self.ci_high is None):
            raise ValueError("ci_low and ci_high come together")
        if self.ci_low is not None and not (self.ci_low <= self.value <= self.ci_high):
            raise ValueError("confidence interval must contain the point estimate")
        return self


class ExclusionRule(StrEnum):
    """Spec §7.2. Each excluded script is counted once, under the first rule it meets."""

    NO_PAIRED_EFFECT = "no_paired_effect"  # no observable's paired CI clears zero its way
    NO_SEPARATION = "no_separation"  # one does, but none separates by VISIBILITY_SDS its way


class ObservableCheck(BaseModel):
    """One observable of an excluded script, with the numbers spec §7.2 judges it by.

    `separation` is signed like the engine's (engine/visibility.py) and like the
    paired-effect interval: positive when the observable rose. Both are judged in
    `direction`, the way the observable moves when the class is present.
    """

    model_config = ConfigDict(allow_inf_nan=False)

    metric: Metric
    subject: str = Field(min_length=1)
    direction: Direction
    separation: float = Field(description="natural sds, signed: positive when it rose")
    ci_low: float
    ci_high: float

    @model_validator(mode="after")
    def _checkable(self) -> "ObservableCheck":
        if self.direction == Direction.FLAT:
            raise ValueError("an observable of a cause moves up or down")
        if self.ci_low > self.ci_high:
            raise ValueError("ci_low is above ci_high")
        if (self.ci_low > 0 and self.separation < 0) or (self.ci_high < 0 and self.separation > 0):
            raise ValueError("separation points against the paired-effect interval")
        return self

    @property
    def clears_zero(self) -> bool:
        return self.ci_low > 0 if self.direction == Direction.UP else self.ci_high < 0

    @property
    def separates(self) -> bool:
        """Visible in one match: VISIBILITY_SDS or more in the observable's direction."""
        way = self.separation if self.direction == Direction.UP else -self.separation
        return way >= VISIBILITY_SDS


class Exclusion(BaseModel):
    """A planted match left out of recall as not_observable, with the numbers why."""

    match_id: str
    cause: Cause
    rule: ExclusionRule
    observables: list[ObservableCheck] = Field(min_length=1)

    @model_validator(mode="after")
    def _rule_fits_numbers(self) -> "Exclusion":
        if self.cause.domain == "fallback":
            raise ValueError("'other' and 'none' are outcomes, never planted causes")
        # Imported here because planted truth also uses Suite and Split from this module.
        from contracts.planted import CAUSE_OBSERVABLES

        if self.cause not in CAUSE_OBSERVABLES:
            raise ValueError(f"{self.match_id}: {self.cause} cannot be planted")
        cleared = any(o.clears_zero for o in self.observables)
        if self.rule == ExclusionRule.NO_PAIRED_EFFECT and cleared:
            raise ValueError(f"{self.match_id}: an observable's CI clears zero its way")
        if self.rule == ExclusionRule.NO_SEPARATION:
            if not cleared:
                raise ValueError(f"{self.match_id}: the paired-effect rule applies first")
            if any(o.separates for o in self.observables):
                raise ValueError(f"{self.match_id}: an observable separates enough to count")
        expected = CAUSE_OBSERVABLES[self.cause]
        if [(o.metric, o.direction) for o in self.observables] != [
            (o.metric, o.direction) for o in expected
        ]:
            raise ValueError(f"{self.match_id}: observables must be {self.cause}'s, in order")
        subjects: dict[str, str] = {}
        for role, observable in zip(expected, self.observables, strict=True):
            if subjects.setdefault(role.subject, observable.subject) != observable.subject:
                raise ValueError("observables for the same role must use the same subject")
        if len(set(subjects.values())) != len(subjects):
            raise ValueError("observables for different roles must use different subjects")
        return self


class FlagSet(BaseModel):
    """The frozen not_observable flags of one planted suite split, with their provenance.

    Every planted EvalRun embeds the same flag set, frozen before either variant ran, so
    both variants exclude the same matches and the scoreboard can show why.
    """

    split: Split
    match_ids: list[str] = Field(min_length=1, description="every planted match considered")
    paired_seeds: dict[str, list[int]] = Field(description="per match, the seeds measured")
    frozen_at_ms: int = Field(ge=0, description="epoch milliseconds")
    exclusions: list[Exclusion] = Field(default_factory=list)

    @computed_field
    @property
    def flag_set_id(self) -> str:
        content = self.model_dump(
            mode="json", include={"split", "match_ids", "paired_seeds", "exclusions"}
        )
        digest = hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()
        return f"flags-{digest[:16]}"

    @model_validator(mode="after")
    def _covers_its_matches(self) -> "FlagSet":
        if len(self.match_ids) != len(set(self.match_ids)):
            raise ValueError("each planted match is listed once")
        if set(self.paired_seeds) != set(self.match_ids):
            raise ValueError("every planted match, and only those, has its paired seeds")
        for m, seeds in self.paired_seeds.items():
            if len(seeds) != len(set(seeds)):
                raise ValueError(f"{m}: a seed is measured once")
            if len(seeds) < MIN_SEED_PAIRS:
                raise ValueError(f"fewer than {MIN_SEED_PAIRS} seed pairs for {m}")
            if not set(seeds) <= set(SEED_RANGES[self.split]):
                raise ValueError(f"{m}: paired seeds outside the {self.split} range")
        excluded = [x.match_id for x in self.exclusions]
        if len(excluded) != len(set(excluded)):
            raise ValueError("each excluded match is listed once")
        unknown = sorted(set(excluded) - set(self.match_ids))
        if unknown:
            raise ValueError(f"exclusions name matches outside the set: {unknown}")
        return self


class CardOutcome(BaseModel):
    """One final published card's result. `correct` is the recall match, in time; `holds`
    is what precision counts: the card names the planted change while it runs, which it does
    from its start to full time (spec §11.1)."""

    card_id: str
    revision: int = Field(ge=1)
    outcome: CaseOutcome
    correct: bool
    holds: bool
    reason: str

    @model_validator(mode="after")
    def _a_match_in_time_holds(self) -> "CardOutcome":
        if self.correct and not self.holds:
            raise ValueError("a card that matches in time names the change while it runs")
        return self


class MatchOutcome(BaseModel):
    match_id: str
    suite: Suite
    correct: bool
    reason: str
    excluded: bool = False
    cards: list[CardOutcome] = Field(default_factory=list)
    case_errors: dict[str, str] = Field(default_factory=dict)
    failed_cases: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _failure_count(self) -> "MatchOutcome":
        if self.failed_cases != len(self.case_errors):
            raise ValueError("failed_cases must count the recorded case errors")
        return self


class EvalRun(BaseModel):
    run_id: str = Field(min_length=1)
    variant: Variant
    suites: list[Suite] = Field(min_length=1)
    split: Split
    model_tier: str = Field(description="dev | final")
    match_ids: list[str] = Field(min_length=1)
    metrics: list[MetricEstimate] = Field(min_length=1)
    started_at_ms: int = Field(ge=0, description="epoch milliseconds")
    finished_at_ms: int = Field(ge=0, description="epoch milliseconds")
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    cost_usd: float | None = Field(default=None, ge=0)
    foundry_eval_run: str | None = None
    flags: FlagSet | None = Field(
        default=None, description="the planted suite's frozen not_observable flags (spec §7.2)"
    )
    outcomes: list[MatchOutcome] = Field(default_factory=list)
    suite_digest: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$", description="SHA-256 of scripts and truth"
    )
    batch_digest: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$", description="SHA-256 of scored batch files"
    )
    failed_cases: int = Field(default=0, ge=0)
    model_id: str | None = Field(default=None, min_length=1)
    tool_call_budget: int | None = Field(default=None, ge=1)
    wall_time_budget_s: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    bootstrap_seed: int = 0
    bootstrap_resamples: int = Field(default=2000, ge=1)
    undefined_metrics: list[str] = Field(default_factory=list)
    notes: str = ""

    @model_validator(mode="after")
    def _timing(self) -> "EvalRun":
        if self.finished_at_ms < self.started_at_ms:
            raise ValueError("finished before started")
        return self

    @model_validator(mode="after")
    def _metrics_from_run_suites(self) -> "EvalRun":
        if len(set(self.suites)) != len(self.suites):
            raise ValueError("each evaluated suite is listed once")
        keys = [(m.name, m.suite) for m in self.metrics]
        if len(set(keys)) != len(keys):
            raise ValueError("each metric is recorded once per suite")
        if len(set(self.undefined_metrics)) != len(self.undefined_metrics) or set(
            self.undefined_metrics
        ) & {m.name for m in self.metrics}:
            raise ValueError("undefined metrics are distinct and carry no estimate")
        for m in self.metrics:
            if m.suite == "combined" and len(self.suites) > 1:
                continue
            if m.suite not in self.suites:
                raise ValueError(f"metric {m.name} is from {m.suite}, a suite this run did not run")
        return self

    @model_validator(mode="after")
    def _outcomes_cover_cohort(self) -> "EvalRun":
        if len(set(self.match_ids)) != len(self.match_ids):
            raise ValueError("each evaluated match is listed once")
        if self.outcomes:
            configuration = (self.model_id, self.tool_call_budget, self.wall_time_budget_s)
            if self.suite_digest is None or (
                self.batch_digest is None and any(value is None for value in configuration)
            ):
                raise ValueError("scored outcomes require suite, model and budget provenance")
            if self.failed_cases != sum(o.failed_cases for o in self.outcomes):
                raise ValueError("run failed_cases must count every match's failed cases")
            ids = [o.match_id for o in self.outcomes]
            if len(set(ids)) != len(ids) or set(ids) != set(self.match_ids):
                raise ValueError("outcomes must cover the cohort exactly once")
            if any(o.suite not in self.suites for o in self.outcomes):
                raise ValueError("an outcome belongs to a suite this run did not run")
            if self.flags is not None:
                planted = {o.match_id for o in self.outcomes if o.suite == Suite.PLANTED}
                excluded = {o.match_id for o in self.outcomes if o.excluded}
                if planted != set(self.flags.match_ids) or excluded != {
                    e.match_id for e in self.flags.exclusions
                }:
                    raise ValueError("outcomes must reconcile with the frozen flags")
            elif any(o.excluded for o in self.outcomes):
                raise ValueError("only frozen flags can exclude a match")
        return self

    @model_validator(mode="after")
    def _planted_runs_carry_frozen_flags(self) -> "EvalRun":
        planted = Suite.PLANTED in self.suites
        if planted != (self.flags is not None):
            raise ValueError("a planted-suite run carries its flag set, and only such a run")
        if self.flags is not None:
            if self.flags.split != self.split:
                raise ValueError("the flag set is for another split")
            if self.flags.frozen_at_ms > self.started_at_ms:
                raise ValueError("flags must be frozen before the run starts")
            missing = sorted(set(self.flags.match_ids) - set(self.match_ids))
            if missing:
                raise ValueError(f"a planted run scores every flagged match; missing {missing}")
        return self


class VariantComparison(BaseModel):
    """Paired comparison of two runs on the same cases, e.g. Proofline vs single agent.

    `difference` is variant_a minus variant_b, with a paired bootstrap CI over the
    cases both runs scored; never derived from the two runs' separate CIs. Stored in
    eval_runs beside the runs it compares, so the README's A-vs-B number has a record.
    """

    comparison_id: str
    run_a: str = Field(description="run_id of variant_a's EvalRun")
    run_b: str = Field(description="run_id of variant_b's EvalRun")
    variant_a: Variant | Literal["P"]
    variant_b: Variant | Literal["P"]
    split: Split
    difference: MetricEstimate
    flag_set_id: str | None = None
    suite_digest: str | None = None
    match_ids: list[str] = Field(default_factory=list)
    bootstrap_seed: int = 0
    bootstrap_resamples: int = Field(default=2000, ge=1)
    unverified_configuration: list[str] = Field(
        default_factory=list, description="configuration absent from both batch inputs"
    )
    failed_cases_a: int = Field(default=0, ge=0)
    failed_cases_b: int = Field(default=0, ge=0)
    comparison_type: Literal["cases", "questions"] = "cases"
    question_set_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    question_ids: list[str] = Field(default_factory=list)
    unpaired_question_ids: list[str] = Field(default_factory=list)
    model_id: str | None = None
    tool_call_budget: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _two_variants(self) -> "VariantComparison":
        if self.run_a == self.run_b:
            raise ValueError("a comparison needs two different runs")
        if self.variant_a == self.variant_b:
            raise ValueError("a comparison needs two different variants")
        if self.comparison_type == "questions":
            if (
                not self.question_set_digest
                or not self.question_ids
                or self.difference.suite != Suite.QUESTIONS
            ):
                raise ValueError(
                    "a question comparison needs its question set and paired questions"
                )
            if self.variant_a not in ("A", "B", "P") or self.variant_b not in ("A", "B", "P"):
                raise ValueError("question comparisons use A, B or P")
            if len(set(self.question_ids)) != len(self.question_ids) or set(
                self.question_ids
            ) & set(self.unpaired_question_ids):
                raise ValueError(
                    "paired question IDs must be unique and distinct from unpaired IDs"
                )
        elif self.variant_a == "P" or self.variant_b == "P":
            raise ValueError("the plain baseline is only scored on questions")
        return self


class SeedType(StrEnum):
    EVIDENCE_VALUE = "evidence_value"
    BASELINE_VALUE = "baseline_value"
    UNSUPPORTED_NUMBER = "unsupported_number"
    CLAIM_DIRECTION = "claim_direction"
    WRONG_TEAM = "wrong_team"
    OVERCERTAINTY = "overcertainty"
    UNNAMED_CAUSE = "unnamed_cause"
    PRIMARY_DIRECTION = "primary_direction"


def verification_no_answer(verification: Verification | None) -> bool:
    return bool(
        verification
        and verification.rejection_reason
        and "the semantic check gave no answer" in verification.rejection_reason
    )


def verification_catches(verification: Verification | None) -> tuple[bool, bool]:
    """Independent deterministic/semantic rejection flags; unanswered is neither."""
    if (
        not verification
        or verification.status != "rejected"
        or verification_no_answer(verification)
    ):
        return False, False
    deterministic = (
        verification.recompute == "mismatch"
        or any(
            getattr(verification, name) == "failed"
            for name in (
                "baseline_check",
                "sample_size_check",
                "contradiction_check",
                "number_check",
            )
        )
        or verification.rejection_reason == "below support rules"
    )
    return deterministic, verification.semantic_check == "failed"


def check_rate(metric: MetricEstimate | None, numerator: int, denominator: int) -> None:
    if denominator == 0:
        if metric is not None:
            raise ValueError("a zero denominator must have no estimate")
    elif metric is None or (metric.n, metric.value) != (denominator, numerator / denominator):
        raise ValueError("rate must agree with the recorded outcomes")


class SeedTrial(BaseModel):
    kind: SeedType
    applied: bool
    field: str | None = None
    before: str | float | None = None
    after: str | float | None = None
    skip_reason: str | None = None
    verification: Verification | None = None
    caught: bool | None = None
    no_answer: bool = False

    @computed_field
    @property
    def deterministic_caught(self) -> bool:
        return bool(self.caught and verification_catches(self.verification)[0])

    @computed_field
    @property
    def semantic_caught(self) -> bool:
        return bool(self.caught and verification_catches(self.verification)[1])

    @model_validator(mode="after")
    def _verdict(self) -> "SeedTrial":
        if self.applied:
            if self.verification is None or self.field is None or self.before == self.after:
                raise ValueError("an applied seed records a changed field and its verification")
            if self.no_answer != verification_no_answer(self.verification):
                raise ValueError("no_answer must agree with the verification")
            expected = None if self.no_answer else self.verification.status == "rejected"
            if self.caught != expected or self.skip_reason:
                raise ValueError("caught must agree with the seeded verification")
        elif (
            self.no_answer
            or not self.skip_reason
            or any(
                value is not None
                for value in (self.field, self.before, self.after, self.verification, self.caught)
            )
        ):
            raise ValueError("an inapplicable seed records only its reason")
        return self


class SeedCardResult(BaseModel):
    match_id: str
    case_id: str
    card_id: str
    revision: int = Field(ge=1)
    card_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    control: Verification
    control_no_answer: bool = False
    trials: list[SeedTrial]

    @model_validator(mode="after")
    def _all_types(self) -> "SeedCardResult":
        if self.control_no_answer != verification_no_answer(self.control):
            raise ValueError("control_no_answer must agree with the control verification")
        kinds = [t.kind for t in self.trials]
        if len(kinds) != len(SeedType) or set(kinds) != set(SeedType):
            raise ValueError("every card records each seed type exactly once")
        return self


class SeedTypeResult(BaseModel):
    kind: SeedType
    seeded: int = Field(ge=0)
    caught: int = Field(ge=0)
    no_answer: int = Field(default=0, ge=0)
    eligible: int = Field(default=0, ge=0)
    eligible_caught: int = Field(default=0, ge=0)
    deterministic_caught: int | None = Field(default=None, ge=0)
    semantic_caught: int | None = Field(default=None, ge=0)
    both_caught: int | None = Field(default=None, ge=0)
    unclassified_caught: int | None = Field(default=None, ge=0)
    checks: dict[str, int] = Field(default_factory=dict)
    estimate: MetricEstimate | None = None
    all_cards_estimate: MetricEstimate | None = None


class SeededRun(BaseModel):
    """Verifier benchmark with every trial and its proportion intervals retained."""

    record_type: Literal["seeded_verifier"] = "seeded_verifier"
    record_version: Literal[2] = 2
    run_id: str = Field(min_length=1)
    split: Split
    variant: Variant
    model_id: str | None = None
    batch_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    exchanges_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    data_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    verifier_exchanges_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    suite_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    flag_set_id: str | None = None
    started_at_ms: int = Field(ge=0)
    finished_at_ms: int = Field(ge=0)
    bootstrap_seed: int = 0
    bootstrap_resamples: int = Field(default=2000, ge=1)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    cards: list[SeedCardResult] = Field(min_length=1)
    types: list[SeedTypeResult]
    catch_rate: MetricEstimate | None
    all_cards_catch_rate: MetricEstimate | None = None
    false_rejection_rate: MetricEstimate | None
    seed_no_answers: int = Field(default=0, ge=0)
    control_no_answers: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _reconciles(self) -> "SeededRun":
        if self.finished_at_ms < self.started_at_ms:
            raise ValueError("seeded run finished before it started")
        identities = [(c.match_id, c.case_id, c.card_id, c.revision) for c in self.cards]
        if len(set(identities)) != len(identities):
            raise ValueError("each seeded card is recorded once")
        if len(self.types) != len(SeedType) or {t.kind for t in self.types} != set(SeedType):
            raise ValueError("all seed types are reported, including inapplicable types")
        for result in self.types:
            trials = [
                t for c in self.cards for t in c.trials if t.kind == result.kind and t.applied
            ]
            unanswered = sum(t.no_answer for t in trials)
            eligible = [
                t
                for c in self.cards
                if c.control.status == "passed"
                for t in c.trials
                if t.kind == result.kind and t.applied and not t.no_answer
            ]
            if (result.seeded, result.caught, result.no_answer) != (
                len(trials),
                sum(bool(t.caught) for t in trials),
                unanswered,
            ):
                raise ValueError("seeded counts must agree with the recorded trials")
            if (result.eligible, result.eligible_caught) != (
                len(eligible),
                sum(bool(t.caught) for t in eligible),
            ):
                raise ValueError("headline counts must use sound controls only")
            categories = {
                "deterministic_caught": sum(t.deterministic_caught for t in trials),
                "semantic_caught": sum(t.semantic_caught for t in trials),
                "both_caught": sum(t.deterministic_caught and t.semantic_caught for t in trials),
                "unclassified_caught": sum(
                    bool(t.caught) and not (t.deterministic_caught or t.semantic_caught)
                    for t in trials
                ),
            }
            for name, count in categories.items():
                if getattr(result, name) is not None and getattr(result, name) != count:
                    raise ValueError("catch categories must agree with the recorded checks")
            check_rate(result.estimate, result.eligible_caught, result.eligible)
            check_rate(result.all_cards_estimate, result.caught, len(trials) - unanswered)
        seeded, caught = sum(t.seeded for t in self.types), sum(t.caught for t in self.types)
        seed_no_answers = sum(t.no_answer for t in self.types)
        controls_no_answer = sum(c.control_no_answer for c in self.cards)
        if (self.seed_no_answers, self.control_no_answers) != (seed_no_answers, controls_no_answer):
            raise ValueError("no-answer counts must agree with recorded outcomes")
        check_rate(self.all_cards_catch_rate, caught, seeded - seed_no_answers)
        check_rate(
            self.catch_rate,
            sum(t.eligible_caught for t in self.types),
            sum(t.eligible for t in self.types),
        )
        rejected = sum(
            c.control.status == "rejected" and not c.control_no_answer for c in self.cards
        )
        check_rate(self.false_rejection_rate, rejected, len(self.cards) - controls_no_answer)
        return self


QuestionVariant = Literal["A", "B", "P"]
QUESTION_METRICS = (
    "true_premise_accuracy",
    "false_premise_rejection",
    "false_claims_per_question",
    "claim_precision",
)


class QuestionOutcome(BaseModel):
    question_id: str
    match_id: str
    question_text: str
    locale: Literal["en", "es"] = "en"
    premise_true: bool
    answered: bool
    outcome: str
    claimed: bool
    right: bool
    false_claim: bool
    cause: Cause | None = None
    team: str | None = None
    expected_cause: Cause | None = None
    expected_team: str | None = None
    error: str | None = None
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    tool_calls: int | None = Field(default=None, ge=0)
    usage_known: bool = True
    excluded: bool = Field(
        default=False,
        description="its planted change is flagged not observable: counted in no metric",
    )

    @model_validator(mode="after")
    def _right(self) -> "QuestionOutcome":
        if self.premise_true and (self.expected_cause is None or self.expected_team is None):
            raise ValueError("a true premise records its expected cause and team")
        expected = self.answered and (
            self.claimed and (self.cause, self.team) == (self.expected_cause, self.expected_team)
            if self.premise_true
            else not self.claimed
        )
        if self.right != expected or self.false_claim != (self.claimed and not self.right):
            raise ValueError("question outcome does not agree with its claim and premise")
        if self.error is not None and self.answered:
            raise ValueError("a failed question is not an answered question")
        if not self.answered and self.claimed:
            raise ValueError("a missing or failed answer cannot publish a claim")
        return self


def question_counts(
    rows: list[QuestionOutcome], *, explicit_rejection: bool = True
) -> dict[str, tuple[int, int]]:
    return {
        "true_premise_accuracy": (
            sum(r.right for r in rows if r.premise_true),
            sum(r.premise_true for r in rows),
        ),
        "false_premise_rejection": (
            sum(
                (r.outcome == "premise_false" if explicit_rejection else r.right)
                for r in rows
                if not r.premise_true
            ),
            sum(not r.premise_true for r in rows),
        ),
        "false_claims_per_question": (sum(r.false_claim for r in rows), len(rows)),
        "claim_precision": (sum(r.right for r in rows if r.claimed), sum(r.claimed for r in rows)),
    }


class QuestionRun(BaseModel):
    record_type: Literal["question_run"] = "question_run"
    record_version: Literal[1, 2] = 1
    run_id: str = Field(min_length=1)
    variant: QuestionVariant
    split: Split
    question_set_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    suite_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    answers_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    suite_origin_verified: bool = False
    after_follow_up: bool = Field(
        default=False, description="cards scored as their follow-ups left them"
    )
    model_id: str | None = Field(default=None, min_length=1)
    tool_call_budget: int | None = Field(default=None, ge=1)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    token_usage_complete: bool = True
    started_at_ms: int = Field(ge=0)
    finished_at_ms: int = Field(ge=0)
    bootstrap_seed: int = 0
    bootstrap_resamples: int = Field(default=2000, ge=1)
    metrics: list[MetricEstimate] = Field(min_length=1)
    undefined_metrics: list[str] = Field(default_factory=list)
    rows: list[QuestionOutcome] = Field(min_length=1)

    @computed_field
    @property
    def unanswerable(self) -> int:
        return sum(r.outcome == "unanswerable" for r in self.rows)

    @computed_field
    @property
    def premise_rejected(self) -> int:
        return sum(r.outcome == "premise_false" for r in self.rows)

    @model_validator(mode="after")
    def _records_agree(self) -> "QuestionRun":
        if self.finished_at_ms < self.started_at_ms:
            raise ValueError("question run finished before it started")
        ids = [r.question_id for r in self.rows]
        if len(set(ids)) != len(ids):
            raise ValueError("each question is scored once")
        identities = [(r.match_id, r.question_text) for r in self.rows]
        if len(set(identities)) != len(identities):
            raise ValueError("each match/text question is scored once")
        counts = question_counts(self.rows, explicit_rejection=self.record_version >= 2)
        by_name = {m.name: m for m in self.metrics}
        expected_names = {name for name, (_, denominator) in counts.items() if denominator}
        if set(by_name) != expected_names or len(by_name) != len(self.metrics):
            raise ValueError("question metrics must cover every defined metric exactly once")
        if set(self.undefined_metrics) != set(QUESTION_METRICS) - expected_names:
            raise ValueError("undefined question metrics must match zero denominators")
        for name, metric in by_name.items():
            if metric.suite != Suite.QUESTIONS:
                raise ValueError("question metrics belong to the question suite")
            check_rate(metric, *counts[name])
        if (self.input_tokens, self.output_tokens) != (
            sum(r.input_tokens for r in self.rows),
            sum(r.output_tokens for r in self.rows),
        ):
            raise ValueError("question token totals must sum the recorded rows")
        if self.token_usage_complete != all(r.usage_known for r in self.rows):
            raise ValueError("token completeness must agree with per-question usage")
        return self
