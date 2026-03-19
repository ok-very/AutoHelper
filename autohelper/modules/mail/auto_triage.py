"""
Auto-triage — classify incoming emails based on project stage context.

Uses the project's ClickUp stage report to determine what kind of
correspondence is expected, then classifies the email accordingly.
The PM reviews and overrides — this provides the initial suggestion.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TriageResult:
    """Suggested triage classification for an email."""

    status: str  # pending, action_required, informational, archived
    confidence: float  # 0.0 - 1.0
    reasoning: list[str]
    suggested_template_key: str | None = None


# Keywords that suggest the email needs action
_ACTION_KEYWORDS = [
    "please review", "for your review", "action required", "urgent",
    "please confirm", "please provide", "deadline", "overdue",
    "approval needed", "sign", "signature required", "asap",
    "changes requested", "revisions", "comments",
]

# Keywords that suggest FYI / informational
_FYI_KEYWORDS = [
    "fyi", "for your information", "no action required",
    "update", "status update", "just a heads up",
    "thank you for", "confirmed", "received", "noted",
    "minutes from", "meeting notes", "recap",
]

# Keywords that suggest scheduling
_SCHEDULING_KEYWORDS = [
    "schedule", "meeting", "availability", "proposed date",
    "calendar invite", "zoom link", "agenda", "rsvp",
    "doodle", "when2meet",
]


def classify_email(
    subject: str,
    body_preview: str,
    project_stage: int | None,
    project_name: str | None,
    sender: str | None,
) -> TriageResult:
    """Classify an email based on content and project stage context.

    Args:
        subject: Email subject line
        body_preview: First ~500 chars of body text
        project_stage: Current stage number from ClickUp (None if unknown)
        project_name: Matched project name (None if unmatched)
        sender: Sender email address
    """
    text = (subject + " " + (body_preview or "")).lower()
    reasoning: list[str] = []
    confidence = 0.3  # Base confidence for keyword-only classification

    # Check keyword categories
    action_hits = sum(1 for kw in _ACTION_KEYWORDS if kw in text)
    fyi_hits = sum(1 for kw in _FYI_KEYWORDS if kw in text)
    sched_hits = sum(1 for kw in _SCHEDULING_KEYWORDS if kw in text)

    status = "pending"

    if action_hits > fyi_hits and action_hits > sched_hits:
        status = "action_required"
        reasoning.append(f"Contains {action_hits} action keyword(s)")
    elif sched_hits > 0 and sched_hits >= action_hits:
        status = "action_required"  # Scheduling still needs action
        reasoning.append(f"Scheduling request ({sched_hits} keyword(s))")
    elif fyi_hits > action_hits:
        status = "informational"
        reasoning.append(f"Informational ({fyi_hits} FYI keyword(s))")

    # Project context enrichment
    if project_name:
        reasoning.append(f"Matched to project: {project_name}")
        confidence += 0.2

    if project_stage:
        reasoning.append(f"Project is in stage {project_stage}")
        confidence += 0.1

        # Stage-specific heuristics
        if project_stage <= 2:
            # Early stages: city correspondence is likely action items
            if _is_city_sender(sender):
                status = "action_required"
                reasoning.append("City correspondence during early stage")
                confidence += 0.1

        elif project_stage in (5, 6):
            # Selection stages: artist and panel correspondence is active
            if "artist" in text or "selection" in text or "panel" in text:
                status = "action_required"
                reasoning.append("Selection-related during active selection stage")
                confidence += 0.1

        elif project_stage >= 10:
            # Close-out: documentation requests are action items
            if "documentation" in text or "final" in text or "plaque" in text:
                status = "action_required"
                reasoning.append("Documentation request during close-out stage")
                confidence += 0.1

    # Invoice detection
    if "invoice" in text:
        status = "action_required"
        reasoning.append("Invoice detected")
        confidence = max(confidence, 0.7)

    # Cap confidence
    confidence = min(confidence, 0.95)

    if not reasoning:
        reasoning.append("No strong signals — needs manual review")

    return TriageResult(
        status=status,
        confidence=confidence,
        reasoning=reasoning,
    )


def _is_city_sender(sender: str | None) -> bool:
    """Check if sender is likely a municipal contact."""
    if not sender:
        return False
    s = sender.lower()
    return any(domain in s for domain in [
        "vancouver.ca", "burnaby.ca", "surrey.ca",
        "cnv.org", "dnv.org", "newwestcity.ca",
        "portmoody.ca", "coquitlam.ca", "squamish.ca",
        "whiterockcity.ca",
    ])
