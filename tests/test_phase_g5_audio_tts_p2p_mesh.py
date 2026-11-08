"""
tests/test_phase_g5_audio_tts_p2p_mesh.py
Unit tests for Phase G5: Autonomous Multi-Modal Indic Audio/TTS Weaving,
Low-Bandwidth Offline P2P Mesh & Field Deployment Pack
"""

import os
import sys
import unittest
import json

# Ensure src/ is on python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from aasha.orchestrator.phase_g5_audio_tts_p2p_mesh import (
    IndicAudioWeaveSynthesizer,
    OfflineP2PMeshProtocol,
    FieldDeploymentPackager,
    TenChapterG5Evolution,
    PeerCRDTDelta
)

class TestPhaseG5AudioTTSAndP2PMesh(unittest.TestCase):
    def setUp(self):
        self.synth = IndicAudioWeaveSynthesizer()
        self.mesh_a = OfflineP2PMeshProtocol("STATION_A")
        self.mesh_b = OfflineP2PMeshProtocol("STATION_B")

    def test_01_indic_audio_synthesizer_web_audio_js(self):
        """Verify procedural Web Audio API synthesis generation and 0 external audio files."""
        js_code = self.synth.generate_web_audio_synthesizer_js()
        self.assertIn("customElements.define('aasha-audio-narrator'", js_code)
        self.assertIn("createBiquadFilter", js_code, "Must use resonant formant filters")
        self.assertIn("createOscillator", js_code, "Must use glottal pulse oscillator")
        # Ensure script is lightweight (<10 KB)
        self.assertLess(len(js_code.encode('utf-8')), 10240, "Audio engine must be < 10 KB")
        # Ensure canonical phonemes are present
        self.assertIn("fraction", self.synth.CANONICAL_PHONEMES)
        self.assertIn("numerator", self.synth.CANONICAL_PHONEMES)

    def test_02_offline_p2p_mesh_crdt_delta_sync(self):
        """Verify commutative CRDT delta merge and Lamport clock conflict resolution."""
        # Station A creates delta at clock 2
        delta_a = self.mesh_a.create_delta("STUDENT_01", "NCERT-G06-MATH-CH07_TLN_01", 0.75, lamport_clock=2)
        # Station B creates updated delta at clock 3
        delta_b = self.mesh_b.create_delta("STUDENT_01", "NCERT-G06-MATH-CH07_TLN_01", 0.88, lamport_clock=3)

        # Merge B into A -> B should win because clock 3 > 2
        merged = self.mesh_a.merge_remote_delta(delta_b)
        self.assertTrue(merged)
        self.assertEqual(self.mesh_a.state_store["STUDENT_01:NCERT-G06-MATH-CH07_TLN_01"].mastery_prob, 0.88)

        # Merge stale A into B -> should be rejected because clock 2 < 3
        rejected = self.mesh_b.merge_remote_delta(delta_a)
        self.assertFalse(rejected)
        self.assertEqual(self.mesh_b.state_store["STUDENT_01:NCERT-G06-MATH-CH07_TLN_01"].mastery_prob, 0.88)

    def test_03_field_deployment_packaging_and_service_worker(self):
        """Verify service worker offline cache manifest and dashboard generation."""
        packager = FieldDeploymentPackager()
        file_list = ["chapter1.html", "chapter2.html"]
        sw_js = packager.generate_service_worker_js(file_list)
        self.assertIn("CACHE_NAME = 'aasha-field-cache-v1'", sw_js)
        self.assertIn("chapter1.html", sw_js)
        self.assertIn("caches.match(event.request)", sw_js)

        dash_html = packager.generate_teacher_field_dashboard()
        self.assertIn("AASHA — शिक्षक फील्ड नियंत्रण पटल", dash_html)
        self.assertIn("100% ऑफ़लाइन P2P मेश सक्रिय", dash_html)

    def test_04_ten_chapter_g5_evolution_and_ceiling(self):
        """Verify multimodal audio and P2P mesh integration into 10 modules under 20 MiB ceiling."""
        evolution = TenChapterG5Evolution()
        manifest = evolution.execute_g5_evolution()

        self.assertEqual(manifest["modules_enhanced"], 10)
        self.assertTrue(manifest["all_under_20mib"])
        self.assertTrue(manifest["offline_zero_cdn_compliant"])
        self.assertTrue(manifest["p2p_mesh_enabled"])
        self.assertTrue(manifest["service_worker_cached"])
        print(f"G5 Field Pack: {manifest['total_size_bytes']} bytes across 10 modules (< 20 MiB ceiling)")

if __name__ == "__main__":
    unittest.main()
