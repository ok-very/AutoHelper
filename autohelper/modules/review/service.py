"""
Review service implementation.

Handles AI-powered review and repair of artifacts using Gemini API.
Key is read from config; optional ephemeral key from request is never persisted.
"""

import json
import re
from pathlib import Path
from typing import Any

from autohelper.config import get_settings
from autohelper.shared.ids import generate_id
from autohelper.shared.logging import get_logger

from .schemas import (
    ApplyPatchesRequest,
    ApplyPatchesResult,
    PatchLocation,
    PatchSuggestion,
    ReviewRequest,
    ReviewResult,
)

logger = get_logger(__name__)


# =============================================================================
# SERVICE
# =============================================================================

class ReviewService:
    """Service for AI-powered artifact review and repair."""

    def __init__(self):
        self.settings = get_settings()
        self._pending_patches: dict[str, list[PatchSuggestion]] = {}

    def _get_api_key(self, ephemeral_key: str | None) -> str | None:
        """
        Get Gemini API key with preference:
        1. Ephemeral key from request (NOT logged, NOT persisted)
        2. Server-side key from config
        """
        if ephemeral_key:
            # Never log the key
            return ephemeral_key
        
        # Try config
        return getattr(self.settings, "gemini_api_key", None)

    async def review(self, request: ReviewRequest) -> ReviewResult:
        """
        Review an artifact with Gemini AI.
        
        The Gemini API key is:
        - Used from request.gemini_api_key if provided (ephemeral, not persisted)
        - Otherwise read from server config
        - Never written to logs
        """
        artifact_path = Path(request.artifact_path).resolve()
        
        if not artifact_path.exists():
            return ReviewResult(
                success=False,
                error=f"Artifact not found: {artifact_path}",
            )

        api_key = self._get_api_key(request.gemini_api_key)
        if not api_key:
            return ReviewResult(
                success=False,
                error="Gemini API key not configured. Set in server config or provide ephemeral key.",
            )

        # Read artifact content
        try:
            content = artifact_path.read_text(encoding="utf-8")
        except Exception as e:
            return ReviewResult(
                success=False,
                error=f"Failed to read artifact: {e}",
            )

        # Call Gemini API
        try:
            patches, summary = await self._call_gemini(
                content=content,
                review_type=request.review_type,
                api_key=api_key,
                file_type=artifact_path.suffix,
            )

            # Store patches for later application
            artifact_key = str(artifact_path)
            self._pending_patches[artifact_key] = patches

            return ReviewResult(
                success=True,
                patches=patches,
                summary=summary,
            )

        except Exception as e:
            # Sanitize error message - never include API key
            error_msg = str(e)
            if api_key and api_key in error_msg:
                error_msg = error_msg.replace(api_key, "[REDACTED]")
            
            logger.exception("Gemini review failed")
            return ReviewResult(
                success=False,
                error=f"Review failed: {error_msg}",
            )

    async def _call_gemini(
        self,
        content: str,
        review_type: str,
        api_key: str,
        file_type: str,
    ) -> tuple[list[PatchSuggestion], str]:
        """
        Call Gemini API to review content.
        
        Returns: (patches, summary)
        """
        import httpx

        # Build prompt based on review type
        if file_type in [".html", ".htm"]:
            format_hint = "HTML"
        elif file_type == ".md":
            format_hint = "Markdown"
        else:
            format_hint = "text"

        prompts = {
            "grammar": f"Review this {format_hint} document for grammar and spelling errors only.",
            "structure": f"Review this {format_hint} document for structural issues (headings, organization, formatting).",
            "full": f"Review this {format_hint} document comprehensively: grammar, spelling, structure, clarity, and formatting.",
        }

        system_prompt = f"""You are a document reviewer. {prompts.get(review_type, prompts['full'])}

Return your analysis as JSON with this structure:
{{
    "summary": "One paragraph summary of issues found",
    "patches": [
        {{
            "category": "grammar|structure|content|formatting",
            "severity": "info|warning|error",
            "original_text": "exact text to replace (or null if not applicable)",
            "suggested_text": "replacement text (or null if just a comment)",
            "explanation": "why this change is suggested"
        }}
    ]
}}

Only return valid JSON, no other text."""

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
        
        payload = {
            "contents": [{
                "parts": [
                    {"text": system_prompt},
                    {"text": f"Document to review:\n\n{content}"},
                ]
            }],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 4096,
            }
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            
            result = response.json()

        # Parse response
        try:
            text = result["candidates"][0]["content"]["parts"][0]["text"]
            # Extract JSON from response (may be wrapped in markdown code block)
            json_match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
            if json_match:
                text = json_match.group(1)
            
            data = json.loads(text)
            summary = data.get("summary", "")
            raw_patches = data.get("patches", [])

            patches = []
            for p in raw_patches:
                patches.append(PatchSuggestion(
                    id=generate_id("patch"),
                    category=p.get("category", "content"),
                    severity=p.get("severity", "info"),
                    original_text=p.get("original_text"),
                    suggested_text=p.get("suggested_text"),
                    explanation=p.get("explanation", ""),
                ))

            return patches, summary

        except (KeyError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to parse Gemini response: {e}")
            return [], "Failed to parse AI response"

    async def apply_patches(self, request: ApplyPatchesRequest) -> ApplyPatchesResult:
        """Apply approved patches to an artifact."""
        artifact_path = Path(request.artifact_path).resolve()
        artifact_key = str(artifact_path)

        if artifact_key not in self._pending_patches:
            return ApplyPatchesResult(
                success=False,
                error="No pending patches for this artifact. Run review first.",
            )

        pending = self._pending_patches[artifact_key]
        patches_to_apply = [p for p in pending if p.id in request.patch_ids]

        if not patches_to_apply:
            return ApplyPatchesResult(
                success=False,
                error="No matching patches found.",
            )

        try:
            content = artifact_path.read_text(encoding="utf-8")
            
            applied = 0
            for patch in patches_to_apply:
                if patch.original_text and patch.suggested_text:
                    if patch.original_text in content:
                        content = content.replace(patch.original_text, patch.suggested_text, 1)
                        applied += 1

            # Write back
            artifact_path.write_text(content, encoding="utf-8")

            # Clear applied patches
            self._pending_patches[artifact_key] = [
                p for p in pending if p.id not in request.patch_ids
            ]

            return ApplyPatchesResult(
                success=True,
                applied_count=applied,
                output_path=str(artifact_path),
            )

        except Exception as e:
            return ApplyPatchesResult(
                success=False,
                error=f"Failed to apply patches: {e}",
            )
