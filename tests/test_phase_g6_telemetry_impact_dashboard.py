"""
tests/test_phase_g6_telemetry_impact_dashboard.py
Unit tests for Phase G6: Autonomous Classroom Telemetry Aggregator,
NGO Impact Dashboard & Production Release Promotion
"""

import os
import sys
import unittest
import json

# Ensure src/ is on python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from aasha.orchestrator.phase_g6_telemetry_impact_dashboard import (
    ClassroomTelemetryAggregator,
    NGOImpactDashboardPackager,
    ProductionReleasePromoter,
    TelemetryEvent,
    LearningImpactMetrics
)

class TestPhaseG6TelemetryAndImpactDashboard(unittest.TestCase):
    def setUp(self):
        self.db_path = "aasha_operational.db"
        self.aggregator = ClassroomTelemetryAggregator(self.db_path)
        self.packager = NGOImpactDashboardPackager()
        self.promoter = ProductionReleasePromoter()

    def test_01_telemetry_recording_and_zero_pii_pseudonymization(self):
        """Verify anonymous student salt hashing and zero PII leakage."""
        raw_salt = "village_student_rahul_9876543210"
        event = self.aggregator.record_anonymous_event(
            raw_student_salt=raw_salt,
            chapter_id="NCERT-G06-MATH-CH07",
            node_id="NCERT-G06-MATH-CH07_TLN_01",
            event_type="QUEST_ATTEMPT",
            score_delta=0.85,
            hint_tier=2
        )

        self.assertTrue(event.anonymous_student_id.startswith("STU_"))
        self.assertNotIn("rahul", event.anonymous_student_id)
        self.assertNotIn("9876543210", event.anonymous_student_id)
        self.assertEqual(len(event.anonymous_student_id), 16)

    def test_02_aggregate_impact_computation(self):
        """Verify computation of aggregate learning impact metrics."""
        metrics = self.aggregator.compute_aggregate_impact()
        self.assertGreaterEqual(metrics.total_students_engaged, 1)
        self.assertGreaterEqual(metrics.avg_mastery_gain_pct, 0.0)
        self.assertEqual(metrics.total_paid_tokens_spent, 0, "Must maintain zero paid token bleed")
        self.assertEqual(metrics.total_external_cdn_bytes, 0, "Must be 100% offline self-contained")

    def test_03_ngo_impact_dashboard_html_generation(self):
        """Verify generation of offline SVG dashboard without remote CDNs."""
        metrics = self.aggregator.compute_aggregate_impact()
        out_file = self.packager.export_dashboard(metrics)

        self.assertTrue(os.path.exists(out_file))
        with open(out_file, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("AASHA AIOS — ग्रामीण शिक्षा एवं प्रभाव डैशबोर्ड", content)
        self.assertIn("svg viewBox=", content, "Must use pure inlined SVG charts")
        self.assertNotIn("http://", content)
        self.assertNotIn("https://cdn", content)
        self.assertLess(os.path.getsize(out_file), 1024 * 1024, "Dashboard must be < 1 MiB")

    def test_04_gate6_release_promotion_verification(self):
        """Verify ADR-001 Gate 6 Autonomous Release Promotion Protocol."""
        # Case A: Ready for promotion (100% tests, 0 secrets, ceiling respected)
        res = self.promoter.verify_gate6_release_readiness(
            test_suites_passed=15,
            total_test_suites=15,
            zero_secrets_certified=True
        )
        self.assertTrue(res["is_promotable"])
        self.assertTrue(res["tests_ok"])
        self.assertTrue(res["secrets_ok"])
        self.assertTrue(res["ceiling_ok"])

        # Case B: Blocked when a test fails
        res_fail = self.promoter.verify_gate6_release_readiness(
            test_suites_passed=14,
            total_test_suites=15,
            zero_secrets_certified=True
        )
        self.assertFalse(res_fail["is_promotable"])

if __name__ == "__main__":
    unittest.main()
