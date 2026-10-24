"""Render Markdown from saved records; no feeds, answer keys or model calls."""

import html
import json
from pathlib import Path

from contracts.eval_run import (
    QUESTION_METRICS,
    EvalRun,
    MetricEstimate,
    QuestionRun,
    SeededRun,
    Split,
    VariantComparison,
)
from eval.records import Record, identity, load_records
from eval.seed_checks import failed_checks

START, END = "<!-- scoreboard:start -->", "<!-- scoreboard:end -->"


def cell(value: object) -> str:
    return (
        html.escape(str(value), quote=False)
        .replace("|", "&#124;")
        .replace("`", "&#96;")
        .replace("\n", " ")
    )


def estimate(metric: MetricEstimate | None, *, difference: bool = False) -> str:
    if metric is None:
        return "undefined / not run"
    unit = " pp" if difference else "%"
    point = f"{metric.value * 100:+.1f}" if difference else f"{metric.value * 100:.1f}"
    ci = (
        f"[{metric.ci_low * 100:.1f}, {metric.ci_high * 100:.1f}]"
        if metric.ci_low is not None
        else "CI unavailable"
    )
    return f"{point}{unit} ({ci}; n={metric.n})"


def scope(split: Split) -> str:
    return f"{split} — tuning only" if split == Split.DEV else f"{split} — reporting"


def question_groups(records: list[Record]) -> list[dict]:
    grouped = {}
    for record in records:
        if isinstance(record, QuestionRun):
            key = (record.split, record.question_set_digest, record.suite_digest)
            grouped.setdefault(key, []).append(record)
    result = []
    for (split, question_digest, suite_digest), runs in sorted(grouped.items()):
        metrics = []
        for name in QUESTION_METRICS:
            variants = {}
            for variant in ("A", "B", "P"):
                variants[variant] = [
                    dict(
                        run_id=r.run_id,
                        estimate=next(
                            (m.model_dump(mode="json") for m in r.metrics if m.name == name), None
                        ),
                    )
                    for r in sorted(runs, key=lambda r: r.run_id)
                    if r.variant == variant
                ]
            metrics.append(dict(name=name, variants=variants))
        coverage = [
            dict(
                run_id=r.run_id,
                answered=sum(q.answered for q in r.rows),
                total=len(r.rows),
                failed=sum(q.error is not None for q in r.rows),
                missing=sum(q.outcome == "missing" for q in r.rows),
                token_usage_complete=r.token_usage_complete,
            )
            for r in sorted(runs, key=lambda r: r.run_id)
        ]
        result.append(
            dict(
                split=split,
                label=scope(split),
                question_set_digest=question_digest,
                suite_digest=suite_digest,
                metrics=metrics,
                coverage=coverage,
            )
        )
    return result


def citations(record: Record, runs: dict) -> dict:
    missing, flag = [], None
    flags_applicable = True
    model = getattr(record, "model_id", None)
    if isinstance(record, VariantComparison):
        sources = [runs.get(record.run_a), runs.get(record.run_b)]
        if not all(sources):
            missing.append("source_runs")
        if model is None and all(sources) and sources[0].model_id == sources[1].model_id:
            model = sources[0].model_id
        flag = record.flag_set_id
        flags_applicable = record.comparison_type != "questions"
        if record.comparison_type == "questions" and any(
            isinstance(r, QuestionRun) and not r.suite_origin_verified for r in sources
        ):
            missing.append("suite_origin")
        missing += record.unverified_configuration
    elif isinstance(record, QuestionRun):
        flags_applicable = False
        if record.tool_call_budget is None:
            missing.append("tool_call_budget")
        if not record.suite_origin_verified:
            missing.append("suite_origin")
        if not record.token_usage_complete:
            missing.append("token_usage")
    elif isinstance(record, EvalRun):
        flag = record.flags.flag_set_id if record.flags else None
        flags_applicable = "planted" in record.suites
        missing += [
            name
            for name in ("tool_call_budget", "wall_time_budget_s")
            if getattr(record, name) is None
        ]
    else:
        flag = record.flag_set_id
    for name, value in (("suite_digest", record.suite_digest), ("model_id", model)):
        if value is None:
            missing.append(name)
    if flag is None and flags_applicable:
        missing.append("flag_set_id")
    return dict(
        record=f"{identity(record)}.json",
        suite_digest=record.suite_digest,
        question_set_digest=getattr(record, "question_set_digest", None),
        flag_set_id=flag,
        model_id=model,
        tool_call_budget=getattr(record, "tool_call_budget", None),
        unverified=sorted(set(missing)),
    )


def trial_result(trial) -> str:
    return (
        "no_answer"
        if trial.no_answer
        else "caught"
        if trial.caught
        else "missed"
        if trial.applied
        else "not_applicable"
    )


def scoreboard_data(records: list[Record]) -> dict:
    runs = {r.run_id: r for r in records if isinstance(r, (EvalRun, QuestionRun))}
    entries = []
    for record in sorted(records, key=identity):
        data = record.model_dump(mode="json")
        data["id"] = identity(record)
        data["citations"] = citations(record, runs)
        data["bootstrap_unit"] = "card" if isinstance(record, SeededRun) else "match"
        data["exclusions"] = (
            data.get("flags", {}).get("exclusions", []) if data.get("flags") else []
        )
        data["differences"] = []
        if isinstance(record, VariantComparison):
            data["record_type"] = (
                "question_comparison"
                if record.comparison_type == "questions"
                else "variant_comparison"
            )
            data["differences"] = [data["difference"]]
            data["metrics"] = [data["difference"]]
        elif isinstance(record, SeededRun):
            rates = dict(
                verifier_catch_rate=record.catch_rate,
                all_cards_verifier_catch_rate=record.all_cards_catch_rate,
                control_false_rejection_rate=record.false_rejection_rate,
            )
            data["metrics"] = [
                m.model_dump(mode="json") | {"name": name}
                for name, m in rates.items()
                if m is not None
            ]
            data["undefined_metrics"] = [name for name, m in rates.items() if m is None]
            for card, encoded in zip(record.cards, data["cards"], strict=True):
                encoded["control_result"] = (
                    "no_answer" if card.control_no_answer else card.control.status
                )
                encoded["control_checks"] = failed_checks(card.control)
                for trial, output in zip(card.trials, encoded["trials"], strict=True):
                    output["result"] = trial_result(trial)
                    output["checks"] = failed_checks(trial.verification)
        elif isinstance(record, EvalRun):
            data["record_type"] = "detector_run"
        entries.append(data)
    return dict(schema_version=1, records=entries, question_suites=question_groups(records))


def render_questions(records: list[Record]) -> list[str]:
    lines = []
    for group in question_groups(records):
        lines += [
            "",
            f"Questions: {group['label']}; set {group['question_set_digest']}.",
            "",
            "| Metric (95% CI; n) | A | B | P |",
            "|---|---|---|---|",
        ]
        for row in group["metrics"]:
            values = [row["name"]]
            for variant in ("A", "B", "P"):
                formatted = []
                for item in row["variants"][variant]:
                    metric = (
                        MetricEstimate.model_validate(item["estimate"])
                        if item["estimate"]
                        else None
                    )
                    formatted.append(f"{item['run_id']}: {estimate(metric)}")
                values.append("; ".join(formatted) or "not run")
            lines.append("| " + " | ".join(cell(v) for v in values) + " |")
        lines.append("")
        for coverage in group["coverage"]:
            lines.append(
                f"- {cell(coverage['run_id'])}: "
                f"{coverage['answered']}/{coverage['total']} answered; "
                f"{coverage['failed']} failed; {coverage['missing']} missing; "
                f"token usage {'complete' if coverage['token_usage_complete'] else 'incomplete'}."
            )
    return lines


def render(records: list[Record]) -> str:
    lines = ["Generated from evaluation records. Dev is tuning only; heldout is for reporting.", ""]
    if not records:
        return "\n".join(lines + ["No evaluation records.", ""])
    runs = {r.run_id: r for r in records if isinstance(r, EvalRun)}
    seeded = [r for r in records if isinstance(r, SeededRun)]
    lines += render_questions(records)
    lines += ["", "Detector suites:", ""]
    lines += [
        "| Split | Variant | Run | Headline planted recall (95% CI) | All-planted recall (95% CI) "
        "| Cause precision (95% CI) | Decoy restraint (95% CI) "
        "| Verifier catch rate (95% CI) | Failed cases |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for run in sorted(runs.values(), key=lambda r: (r.split, r.variant, r.run_id)):
        metrics = {m.name: m for m in run.metrics}
        linked = [
            s
            for s in seeded
            if (s.split, s.variant, s.batch_digest) == (run.split, run.variant, run.batch_digest)
        ]
        catch = (
            "; ".join(f"{cell(s.run_id)}: {estimate(s.catch_rate)}" for s in linked) or "not run"
        )
        values = (
            [scope(run.split), run.variant, run.run_id]
            + [
                estimate(metrics.get(name))
                for name in (
                    "planted_recall",
                    "all_planted_recall",
                    "cause_precision",
                    "decoy_restraint",
                )
            ]
            + [catch, str(run.failed_cases)]
        )
        lines.append("| " + " | ".join(cell(v) for v in values) + " |")
    for run in sorted(runs.values(), key=lambda r: (r.split, r.variant, r.run_id)):
        if run.flags:
            lines += ["", f"Exclusions for {cell(run.run_id)} ({len(run.flags.exclusions)}):"]
            for excluded in run.flags.exclusions:
                details = "; ".join(
                    f"{o.metric}/{o.subject}: separation {o.separation:+.3f} SD, "
                    f"paired-effect CI [{o.ci_low:.3f}, {o.ci_high:.3f}]"
                    for o in excluded.observables
                )
                lines.append(
                    f"- {cell(excluded.match_id)}: {cell(excluded.cause)}; "
                    f"{cell(excluded.rule)}; {cell(details)}"
                )
            if not run.flags.exclusions:
                lines.append("- None.")
    lines += [
        "",
        "Paired differences (first variant minus second; paired match bootstrap):",
        "",
        "| Record | Split | Variants | Suite | Metric | Difference (95% CI) "
        "| Unverified configuration |",
        "|---|---|---|---|---|---|---|",
    ]
    for record in sorted((r for r in records if isinstance(r, VariantComparison)), key=identity):
        lines.append(
            "| "
            + " | ".join(
                cell(v)
                for v in [
                    record.comparison_id,
                    scope(record.split),
                    f"{record.variant_a} − {record.variant_b}",
                    record.difference.suite,
                    record.difference.name,
                    estimate(record.difference, difference=True),
                    ", ".join(record.unverified_configuration) or "none recorded",
                ]
            )
            + " |"
        )
    for record in sorted(seeded, key=lambda r: r.run_id):
        lines += [
            "",
            f"Seeded Verifier run: {cell(record.run_id)} "
            f"({scope(record.split)}, {record.variant}; {len(record.cards)} card clusters).",
            f"Sound-control catch rate: {estimate(record.catch_rate)}. "
            f"All-cards catch rate: {estimate(record.all_cards_catch_rate)}. "
            f"Controls rejected: {estimate(record.false_rejection_rate)}.",
            f"No answer: {record.seed_no_answers} seeded trials; "
            f"{record.control_no_answers} controls.",
            "",
            "| Type | Seeded | Caught | No answer | Sound-control trials | Headline rate (95% CI) "
            "| All-cards rate (95% CI) "
            "| Checks that rejected seeds |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for result in record.types:
            lines.append(
                "| "
                + " | ".join(
                    cell(v)
                    for v in [
                        result.kind,
                        result.seeded,
                        result.caught,
                        result.no_answer,
                        result.eligible,
                        estimate(result.estimate),
                        estimate(result.all_cards_estimate),
                        ", ".join(f"{k}: {v}" for k, v in sorted(result.checks.items())) or "none",
                    ]
                )
                + " |"
            )
        total_seeded = sum(t.seeded for t in record.types)
        total_caught = sum(t.caught for t in record.types)
        totals = [
            "Total",
            total_seeded,
            total_caught,
            record.seed_no_answers,
            sum(t.eligible for t in record.types),
            estimate(record.catch_rate),
            estimate(record.all_cards_catch_rate),
            "See per-type checks",
        ]
        lines.append("| " + " | ".join(cell(v) for v in totals) + " |")
        lines += [
            "",
            "| Card / case | Type | Result | Check / applicability |",
            "|---|---|---|---|",
        ]
        for card in record.cards:
            control_checks = ", ".join(failed_checks(card.control)) or "none"
            control_row = [
                f"{card.match_id}/{card.case_id}/{card.card_id}",
                "control",
                "no answer" if card.control_no_answer else card.control.status,
                control_checks,
            ]
            lines.append("| " + " | ".join(cell(v) for v in control_row) + " |")
            for trial in card.trials:
                reason = (
                    ", ".join(failed_checks(trial.verification))
                    if trial.applied
                    else trial.skip_reason
                )
                result = trial_result(trial).replace("_", " ")
                lines.append(
                    "| "
                    + " | ".join(
                        cell(v)
                        for v in [
                            f"{card.match_id}/{card.case_id}/{card.card_id}",
                            trial.kind,
                            result,
                            reason or "none",
                        ]
                    )
                    + " |"
                )
    lines += [
        "",
        "Record provenance:",
        "",
        "| Record | Split | Suite digest | Flag set | Model ID | Unverified |",
        "|---|---|---|---|---|---|",
    ]
    all_runs = {r.run_id: r for r in records if isinstance(r, (EvalRun, QuestionRun))}
    for record in sorted(records, key=identity):
        citation = citations(record, all_runs)
        lines.append(
            "| "
            + " | ".join(
                cell(v)
                for v in [
                    identity(record),
                    scope(record.split),
                    record.suite_digest or "unverified",
                    citation["flag_set_id"] or "not applicable / unrecorded",
                    citation["model_id"] or "unverified",
                    ", ".join(citation["unverified"]) or "none",
                ]
            )
            + " |"
        )
    return "\n".join(lines).rstrip() + "\n"


def scoreboard(folder: Path, check: Path | None = None, *, json_output: bool = False) -> str:
    records = load_records(folder)
    text = render(records)
    if check is not None:
        document = check.read_bytes().decode("utf-8")
        if document.count(START) != 1 or document.count(END) != 1:
            raise ValueError("README must contain exactly one pair of scoreboard markers")
        _, tail = document.split(START)
        middle, _ = tail.split(END)
        if middle != "\n" + text:
            raise ValueError("README scoreboard differs from the evaluation records")
    return (
        json.dumps(scoreboard_data(records), ensure_ascii=False, indent=2) + "\n"
        if json_output
        else text
    )
