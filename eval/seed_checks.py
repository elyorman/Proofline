"""Names of the checks that actually rejected a control or seeded card."""

from contracts.card import CheckResult, Verification
from contracts.eval_run import verification_no_answer


def failed_checks(verification: Verification | None) -> list[str]:
    if (
        verification is None
        or verification.status != "rejected"
        or verification_no_answer(verification)
    ):
        return []
    failed = ["recompute"] if verification.recompute == "mismatch" else []
    failed += [
        name
        for name in (
            "baseline_check",
            "sample_size_check",
            "contradiction_check",
            "number_check",
            "semantic_check",
        )
        if getattr(verification, name) == CheckResult.FAILED
    ]
    return failed or [
        "support_rules" if verification.rejection_reason == "below support rules" else "rejected"
    ]
