"""Deterministic scoring for validated, evidence-backed business signals."""
from __future__ import annotations

from .business_signal_analyzer import BusinessSignalAnalysis, SIGNAL_NAMES


def score_business_signals(analysis: BusinessSignalAnalysis) -> float:
    """Return the percent of distinct canonical signals confirmed with evidence.

    Each of the six signal types contributes exactly 1/6. Evidence count and
    confidence do not affect the score.
    """
    detected = {
        signal.name
        for signal in analysis.signals
        if signal.detected and signal.evidence
    }
    return round(100 * len(detected & set(SIGNAL_NAMES)) / len(SIGNAL_NAMES), 1)
