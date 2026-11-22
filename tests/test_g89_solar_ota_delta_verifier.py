import hashlib
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from aasha.orchestrator.g89_solar_ota_delta_verifier import (  # noqa: E402
    verify_solar_ota_delta_bundle,
)


class TestG89SolarOtaDeltaVerifier(unittest.TestCase):
    def test_verifies_valid_solar_ota_delta_bundle(self):
        html_body = "<!DOCTYPE html><html><body><h1>Solar Pump Module</h1></body></html>"
        sha = hashlib.sha256(html_body.encode("utf-8")).hexdigest()
        res = verify_solar_ota_delta_bundle(
            "CENTER-UP-GN-01",
            [{"chunk_id": "C1", "size_bytes": len(html_body), "content": html_body, "sha256": sha}],
        )
        self.assertTrue(res["ok"])
        self.assertTrue(res["within_20mib_cap"])
        self.assertTrue(res["zero_external_urls"])
        self.assertGreater(len(res["ota_verification_sha256"]), 32)

    def test_rejects_tampered_sha256_and_oversized_chunk(self):
        bad_sha = verify_solar_ota_delta_bundle(
            "CENTER-UP-GN-01",
            [{"chunk_id": "C1", "size_bytes": 50, "content": "<html></html>", "sha256": "0" * 64}],
        )
        self.assertFalse(bad_sha["ok"])
        self.assertEqual(bad_sha["error"], "OTA_CHUNK_SHA256_MISMATCH")

        too_big = verify_solar_ota_delta_bundle(
            "CENTER-UP-GN-01",
            [{"chunk_id": "C2", "size_bytes": 20971521}],
        )
        self.assertFalse(too_big["ok"])
        self.assertEqual(too_big["error"], "CHILD_HTML_EXCEEDS_20MIB_CAP")


if __name__ == "__main__":
    unittest.main()
