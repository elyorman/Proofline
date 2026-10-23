"""Render Markdown from saved records; no feeds, answer keys or model calls."""

import html
from pathlib import Path

from contracts.eval_run import EvalRun, MetricEstimate, SeededRun, Split, VariantComparison
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


def render(records: list[Record]) -> str:
    lines = ["Generated from evaluation records. Dev is tuning only; heldout is for reporting.", ""]
    if not records:
        return "\n".join(lines + ["No evaluation records.", ""])
    runs = {r.run_id: r for r in records if isinstance(r, EvalRun)}
    seeded = [r for r in records if isinstance(r, SeededRun)]
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
        "| Record | Split | Variants | Metric | Difference (95% CI) | Unverified configuration |",
        "|---|---|---|---|---|---|",
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
            f"Catch rate: {estimate(record.catch_rate)}. "
            f"Controls rejected: {estimate(record.false_rejection_rate)}.",
            "",
            "| Type | Seeded | Caught | Catch rate (95% CI) | Checks that rejected seeds |",
            "|---|---|---|---|---|",
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
                        estimate(result.estimate),
                        ", ".join(f"{k}: {v}" for k, v in sorted(result.checks.items())) or "none",
                    ]
                )
                + " |"
            )
        total_seeded = sum(t.seeded for t in record.types)
        total_caught = sum(t.caught for t in record.types)
        lines.append(
            f"| Total | {total_seeded} | {total_caught} | {estimate(record.catch_rate)} "
            "| See per-type checks |"
        )
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
                card.control.status,
                control_checks,
            ]
            lines.append("| " + " | ".join(cell(v) for v in control_row) + " |")
            for trial in card.trials:
                reason = (
                    ", ".join(failed_checks(trial.verification))
                    if trial.applied
                    else trial.skip_reason
                )
                result = (
                    "caught" if trial.caught else "missed" if trial.applied else "not applicable"
                )
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
    for record in sorted(records, key=identity):
        missing = []
        if isinstance(record, VariantComparison):
            sources = [runs.get(record.run_a), runs.get(record.run_b)]
            model = (
                sources[0].model_id
                if all(sources) and sources[0].model_id == sources[1].model_id
                else None
            )
            if not all(sources):
                missing.append("source runs")
            flag = record.flag_set_id
            missing += record.unverified_configuration
        else:
            model = record.model_id
            flag = (
                record.flags.flag_set_id
                if isinstance(record, EvalRun) and record.flags
                else getattr(record, "flag_set_id", None)
            )
            if isinstance(record, EvalRun):
                missing += [
                    name
                    for name in ("tool_call_budget", "wall_time_budget_s")
                    if getattr(record, name) is None
                ]
        for name, value in (("suite_digest", record.suite_digest), ("model_id", model)):
            if value is None:
                missing.append(name)
        if flag is None and not (isinstance(record, EvalRun) and "planted" not in record.suites):
            missing.append("flag_set_id")
        lines.append(
            "| "
            + " | ".join(
                cell(v)
                for v in [
                    identity(record),
                    scope(record.split),
                    record.suite_digest or "unverified",
                    flag or "not recorded",
                    model or "unverified",
                    ", ".join(sorted(set(missing))) or "none",
                ]
            )
            + " |"
        )
    return "\n".join(lines).rstrip() + "\n"


def scoreboard(folder: Path, check: Path | None = None) -> str:
    text = render(load_records(folder))
    if check is not None:
        document = check.read_bytes().decode("utf-8")
        if document.count(START) != 1 or document.count(END) != 1:
            raise ValueError("README must contain exactly one pair of scoreboard markers")
        _, tail = document.split(START)
        middle, _ = tail.split(END)
        if middle != "\n" + text:
            raise ValueError("README scoreboard differs from the evaluation records")
    return text
