"""
Email enrichment service using Gemini for AI-powered triage analysis.
"""

import json
import logging
import os
import re
from dataclasses import dataclass

import requests

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"


@dataclass
class EmailAnalysis:
    """Structured output from AI analysis."""
    triage_status: str
    confidence: float
    reasoning: str
    priority: str
    priority_factors: list[str]
    keywords: list[str]
    suggested_action: str | None


class EmailEnrichmentService:
    """Service for AI-powered email analysis."""

    def __init__(self):
        self.api_key = GEMINI_API_KEY
        if not self.api_key:
            logger.warning("GEMINI_API_KEY not set, enrichment will be disabled")

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def analyze_email(
        self,
        subject: str | None,
        sender: str | None,
        body_preview: str | None,
    ) -> EmailAnalysis | None:
        """
        Analyze email content using Gemini AI.

        Returns structured analysis or None if enrichment is disabled/failed.
        """
        if not self.enabled:
            return None

        prompt = self._build_analysis_prompt(subject, sender, body_preview)

        try:
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.2,
                    "maxOutputTokens": 500,
                },
            }

            headers = {
                "Content-Type": "application/json",
                "X-goog-api-key": self.api_key,
            }

            response = requests.post(
                GEMINI_API_URL, json=payload, headers=headers, timeout=15
            )

            if response.status_code != 200:
                logger.error(f"Gemini API error {response.status_code}: {response.text}")
                return None

            result = response.json()
            response_text = result["candidates"][0]["content"]["parts"][0]["text"]

            return self._parse_response(response_text)

        except requests.RequestException as e:
            logger.error(f"Network error during enrichment: {e}")
            return None
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            logger.error(f"Failed to parse Gemini response: {e}")
            return None

    def _build_analysis_prompt(
        self,
        subject: str | None,
        sender: str | None,
        body: str | None,
    ) -> str:
        """Build the analysis prompt for email triage."""
        return f"""Analyze this email and provide structured triage information.

Subject: {subject or '(No Subject)'}
From: {sender or 'Unknown'}
Body Preview: {body or '(Empty)'}

Respond with ONLY valid JSON (no markdown, no explanation) in this exact format:
{{
  "triage_status": "pending" | "action_required" | "informational" | "archived",
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation",
  "priority": "low" | "medium" | "high" | "urgent",
  "priority_factors": ["factor1", "factor2"],
  "keywords": ["keyword1", "keyword2"],
  "suggested_action": "action or null"
}}

Guidelines:
- action_required: needs response/decision within 24-48 hours
- informational: FYI only, no action needed
- archived: spam, auto-reply, or outdated
- pending: cannot determine, needs human review
- priority factors: deadline mentions, sender importance, financial impact
- keywords: project names, key terms, people mentioned"""

    def _parse_response(self, response_text: str) -> EmailAnalysis | None:
        """Parse AI response into structured format."""
        # Clean the response - remove markdown code blocks if present
        cleaned = response_text.strip()
        if cleaned.startswith("```"):
            # Remove markdown code block
            cleaned = re.sub(r"^```(?:json)?\n?", "", cleaned)
            cleaned = re.sub(r"\n?```$", "", cleaned)
            cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)

            return EmailAnalysis(
                triage_status=data.get("triage_status", "pending"),
                confidence=float(data.get("confidence", 0.5)),
                reasoning=data.get("reasoning", ""),
                priority=data.get("priority", "medium"),
                priority_factors=data.get("priority_factors", []),
                keywords=data.get("keywords", []),
                suggested_action=data.get("suggested_action"),
            )
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            logger.error(f"Failed to parse analysis JSON: {e}\nRaw: {response_text}")
            return None


# Singleton instance
enrichment_service = EmailEnrichmentService()
