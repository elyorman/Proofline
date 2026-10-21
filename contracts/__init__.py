"""Proofline contracts: the source of truth for every layer.

Change a schema here first, add a test, export to docs/*.schema.json,
then update producers and consumers.
"""

from contracts.card import InsightCard
from contracts.cue import Cue
from contracts.event import Event, EventAmendment, TrackingSample
from contracts.prediction import CrossExamination, Hypothesis, HypothesisTest, Prediction
from contracts.profile import Profile
from contracts.taxonomy import (
    AgentRole,
    BaselineScope,
    CardStatus,
    Cause,
    LanguageLevel,
    Metric,
    MomentType,
    SupportLevel,
)

__all__ = [
    "AgentRole",
    "BaselineScope",
    "CardStatus",
    "Cause",
    "CrossExamination",
    "Cue",
    "Event",
    "EventAmendment",
    "Hypothesis",
    "HypothesisTest",
    "InsightCard",
    "LanguageLevel",
    "Metric",
    "MomentType",
    "Prediction",
    "Profile",
    "SupportLevel",
    "TrackingSample",
]
