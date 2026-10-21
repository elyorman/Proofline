"""Proofline contracts: the source of truth for every layer.

Change a schema here first, add a test, export to docs/*.schema.json,
then update producers and consumers.
"""

from contracts.card import InsightCard
from contracts.case import Case
from contracts.clock import MatchClock, Window
from contracts.cue import Cue
from contracts.eval_run import EvalRun
from contracts.event import Event, EventAmendment, EventRef, TrackingSample
from contracts.prediction import CrossExamination, Hypothesis, HypothesisTest, Prediction
from contracts.profile import Profile
from contracts.taxonomy import (
    AgentRole,
    BaselineScope,
    CardStatus,
    CaseOutcome,
    Cause,
    LanguageLevel,
    Metric,
    MomentType,
    OverlayTemplate,
    SupportLevel,
    ThresholdKind,
)
from contracts.tool_result import DependencyEntry, EvidenceSet, ToolResult

__all__ = [
    "AgentRole",
    "BaselineScope",
    "CardStatus",
    "Case",
    "CaseOutcome",
    "Cause",
    "CrossExamination",
    "Cue",
    "DependencyEntry",
    "EvalRun",
    "Event",
    "EventAmendment",
    "EventRef",
    "EvidenceSet",
    "Hypothesis",
    "HypothesisTest",
    "InsightCard",
    "LanguageLevel",
    "MatchClock",
    "Metric",
    "MomentType",
    "OverlayTemplate",
    "Prediction",
    "Profile",
    "SupportLevel",
    "ThresholdKind",
    "ToolResult",
    "TrackingSample",
    "Window",
]
