"""
Multi-pass scan orchestrator.

Runs domain-specific passes sequentially, validates and enriches against
ground truth, performs cross-domain reconciliation, then returns records
ready for the existing resolve_artists() pipeline.
"""
from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .ground_truth import GroundTruthIndex

logger = logging.getLogger(__name__)


class ScanOrchestrator:
    """Runs multi-pass scanning with ground truth integration."""

    def __init__(
        self,
        passes: list[Any],
        ground_truth_csv: str | None = None,
    ) -> None:
        self._passes = passes
        self._gt_csv = ground_truth_csv
        self._ground_truth: GroundTruthIndex | None = None

    def run(
        self,
        storage_root: Path,
        progress_cb: Callable[[str], None],
        cancel: threading.Event | None = None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Execute all passes, validate, enrich, reconcile.

        Returns (records, admin_files).
        """

        # Load ground truth
        if self._gt_csv:
            progress_cb("Loading ground truth CSV...")
            self._ground_truth = GroundTruthIndex.from_csv(self._gt_csv)
            progress_cb(
                f"Ground truth: {self._ground_truth.total_count} contacts, "
                f"{self._ground_truth.artist_count} artists"
            )

        all_records: list[dict[str, Any]] = []
        all_admin_files: list[dict[str, Any]] = []

        for domain_pass in self._passes:
            if cancel and cancel.is_set():
                break

            progress_cb(f"=== Pass: {domain_pass.label} ===")
            records = domain_pass.execute(storage_root, progress_cb, cancel)
            progress_cb(f"  {domain_pass.label}: {len(records)} records")

            # Collect admin files from the pass
            if hasattr(domain_pass, "admin_files"):
                all_admin_files.extend(domain_pass.admin_files)

            # Ground truth validation + enrichment per record
            if self._ground_truth:
                self._validate_and_enrich(records, domain_pass.domain_key, progress_cb)

            all_records.extend(records)

        if cancel and cancel.is_set():
            return all_records, all_admin_files

        # Cross-domain reconciliation
        progress_cb("Cross-domain reconciliation...")
        all_records = self._cross_domain_reconcile(all_records, progress_cb)

        if all_admin_files:
            progress_cb(f"Admin files collected: {len(all_admin_files)}")

        progress_cb(f"Orchestrator complete: {len(all_records)} total records")
        return all_records, all_admin_files

    def _validate_and_enrich(
        self,
        records: list[dict[str, Any]],
        domain_key: str,
        progress_cb: Callable[[str], None],
    ) -> None:
        """Validate and enrich records against ground truth."""
        if not self._ground_truth:
            return

        matched = 0
        for rec in records:
            gt_match = self._ground_truth.find_contact(
                rec.get("last_name"),
                rec.get("first_name"),
                rec.get("display_name"),
            )
            if gt_match:
                matched += 1
                rec["ground_truth_match"] = gt_match
                rec["validation_flags"] = self._ground_truth.validate_domain(
                    rec, domain_key
                )

                # Enrich contact info
                enrichment = rec.setdefault("contact_enrichment", {})
                if gt_match.get("email"):
                    enrichment["email"] = gt_match["email"]
                if gt_match.get("phone"):
                    enrichment["phone"] = gt_match["phone"]
                if gt_match.get("company"):
                    enrichment["company"] = gt_match["company"]

        progress_cb(f"  Ground truth: matched {matched}/{len(records)} records")

    def _cross_domain_reconcile(
        self,
        records: list[dict[str, Any]],
        progress_cb: Callable[[str], None],
    ) -> list[dict[str, Any]]:
        """
        Detect same artist across domains. Flag duplicates but do NOT remove
        — the existing resolver merges by canonical_id.
        """
        by_id: dict[str, list[dict[str, Any]]] = {}
        for rec in records:
            cid = rec["canonical_id"]
            by_id.setdefault(cid, []).append(rec)

        cross_domain_count = 0
        for cid, recs in by_id.items():
            domains = {r.get("domain_source", "unknown") for r in recs}
            if len(domains) > 1:
                cross_domain_count += 1
                for rec in recs:
                    rec.setdefault("validation_flags", []).append(
                        f"cross_domain:{','.join(sorted(domains))}"
                    )

        progress_cb(f"  Cross-domain artists: {cross_domain_count}")
        return records

    @property
    def ground_truth(self) -> GroundTruthIndex | None:
        return self._ground_truth
