"""GAP-V7-03: Live Headless Chromium (Chrome/156.0.8078.73) DOM, Layout & Click Verification via CDP.

Boots /usr/lib/chromium/chromium directly (bypassing Debian's /usr/bin/chromium wrapper that injects
--load-extension=), connects via Chrome DevTools Protocol (RFC-6455 WebSocket), loads certified v5 HTML5
modules via Page.setDocumentContent + Runtime.evaluate, verifies 0 V8 runtime exceptions, checks real Blink
DOM bounding boxes, executes click interactions (selectOpt -> checkAns -> TEAS XP/Coins), and verifies
bilingual WM/CONN dictionaries inside real Headless Chrome 156.
"""
from __future__ import annotations

import base64
import json
import os
import re
import socket
import struct
import subprocess
import time
import unittest
import urllib.request
from pathlib import Path
from typing import Any, Dict
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
CHROMIUM_BIN = Path("/usr/lib/chromium/chromium")


class SimpleCDPClient:
    """Zero-dependency RFC-6455 WebSocket client for local Chrome DevTools Protocol."""

    def __init__(self, ws_url: str) -> None:
        parsed = urlparse(ws_url)
        self.sock = socket.create_connection((parsed.hostname or "127.0.0.1", parsed.port or 9222), timeout=10.0)
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        req = (
            f"GET {parsed.path} HTTP/1.1\r\n"
            f"Host: {parsed.netloc}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock.sendall(req.encode("ascii"))
        resp = b""
        while b"\r\n\r\n" not in resp:
            resp += self.sock.recv(1024)
        if b"101 " not in resp:
            raise RuntimeError(f"WebSocket handshake failed: {resp!r}")
        self._msg_id = 0

    def send_cmd(self, method: str, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
        self._msg_id += 1
        msg_id = self._msg_id
        payload = json.dumps({"id": msg_id, "method": method, "params": params or {}}).encode("utf-8")
        self._send_frame(payload)
        while True:
            msg = json.loads(self._recv_frame().decode("utf-8"))
            if msg.get("id") == msg_id:
                if "error" in msg:
                    raise RuntimeError(f"CDP error on {method}: {msg['error']}")
                return msg.get("result", {})

    def _send_frame(self, data: bytes) -> None:
        mask_key = os.urandom(4)
        header = bytearray([0x81])
        length = len(data)
        if length < 126:
            header.append(0x80 | length)
        elif length < 65536:
            header.append(0x80 | 126)
            header.extend(struct.pack("!H", length))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack("!Q", length))
        header.extend(mask_key)
        masked = bytes(b ^ mask_key[i % 4] for i, b in enumerate(data))
        self.sock.sendall(bytes(header) + masked)

    def _recv_exact(self, n: int) -> bytes:
        buf = bytearray()
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("WebSocket closed")
            buf.extend(chunk)
        return bytes(buf)

    def _recv_frame(self) -> bytes:
        b1, b2 = self._recv_exact(2)
        length = b2 & 0x7F
        if length == 126:
            (length,) = struct.unpack("!H", self._recv_exact(2))
        elif length == 127:
            (length,) = struct.unpack("!Q", self._recv_exact(8))
        mask = self._recv_exact(4) if (b2 & 0x80) else None
        data = self._recv_exact(length)
        if mask:
            data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
        return data

    def close(self) -> None:
        try:
            self.sock.close()
        except Exception:
            pass


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class TestGapV703ChromiumCDPHeadless(unittest.TestCase):
    def test_real_chromium_dom_layout_and_click_flow(self) -> None:
        if not CHROMIUM_BIN.exists():
            self.skipTest(f"{CHROMIUM_BIN} not present")

        port = _find_free_port()
        proc = subprocess.Popen(
            [
                str(CHROMIUM_BIN),
                "--headless",
                "--no-sandbox",
                "--disable-gpu",
                "--disable-dev-shm-usage",
                f"--remote-debugging-port={port}",
                "about:blank",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            targets = None
            for _ in range(30):
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=1.0) as resp:
                        targets = json.loads(resp.read().decode("utf-8"))
                        if targets:
                            break
                except Exception:
                    time.sleep(0.15)
            self.assertIsNotNone(targets, "Chromium CDP failed to start")
            page_target = next(t for t in targets if t.get("type") == "page" and t.get("url") == "about:blank")
            cdp = SimpleCDPClient(page_target["webSocketDebuggerUrl"])
            try:
                cdp.send_cmd("Page.enable")
                cdp.send_cmd("Runtime.enable")
                ft = cdp.send_cmd("Page.getFrameTree")
                frame_id = ft["frameTree"]["frame"]["id"]

                modules_to_verify = sorted(
                    list((REPO_ROOT / "Aasha-AI/aasha-pipeline-with-master-json/output/g3_10chapter_pack").glob("*.html"))
                    + list((REPO_ROOT / "Aasha-AI/aasha-pipeline-with-master-json/output/g36_ncvet_psscive_pack").glob("*.html"))
                    + [
                        REPO_ROOT / "AASHA_Visual_Mass_Harvest_Phase3/Enriched_G31_Cricket_Arena_LLE_Hub_v5.html",
                        REPO_ROOT / "AASHA_Visual_Mass_Harvest_Phase3/TenPack_SQLite_Studio_Facilitator_Bridge_Hub_v5.html",
                        REPO_ROOT / "AASHA_Visual_Mass_Harvest_Phase3/MVP_Release_Candidate_G37_Certification_Hub_v5.html",
                        REPO_ROOT / "AASHA_Visual_Mass_Harvest_Phase3/Field_Pilot_100Learner_TEAS_Audit_Hub_v5.html",
                        REPO_ROOT / "AASHA_Visual_Mass_Harvest_Phase3/E2E_Regression_G39_Golden_Master_Hub_v5.html",
                        REPO_ROOT / "AASHA_Visual_Mass_Harvest_Phase3/V7_System_Wide_Audit_And_Argon_Swarm_Observability_Hub_v5.html",
                        REPO_ROOT / "AASHA_Visual_Mass_Harvest_Phase3/Multi_Centre_Delta_Rubric_And_10Pack_1129WM_Hub_v5.html",
                        REPO_ROOT / "AASHA_Visual_Mass_Harvest_Phase3/SQLite_Gzip_Catalogue_And_PWA_Cache_Auditor_Hub_v5.html",
                        REPO_ROOT / "AASHA_Visual_Mass_Harvest_Phase3/Teacher_Remediation_Worksheet_And_Cohort_Export_Hub_v5.html",
                    ]
                )
                self.assertEqual(len(modules_to_verify), 22)

                for mod_path in modules_to_verify:
                    self.assertTrue(mod_path.exists(), f"Missing {mod_path}")
                    html = mod_path.read_text(encoding="utf-8")
                    cdp.send_cmd("Page.setDocumentContent", {"frameId": frame_id, "html": html})

                    # Execute all inline <script> blocks inside real V8 and assert 0 uncaught exceptions
                    for script_body in re.findall(r"<script[^>]*>([\s\S]*?)</script>", html):
                        s_res = cdp.send_cmd("Runtime.evaluate", {"expression": script_body})
                        self.assertNotIn(
                            "exceptionDetails",
                            s_res,
                            f"Real Chrome 156 V8 uncaught exception in {mod_path.name}: {s_res.get('exceptionDetails')}",
                        )

                    eval_res = cdp.send_cmd(
                        "Runtime.evaluate",
                        {
                            "expression": (
                                "(function() {"
                                "  var rootEl = document.getElementById('app') || document.body;"
                                "  var appRect = rootEl.getBoundingClientRect();"
                                "  var correctBtn = document.querySelector('.tap-option[data-correct=\"true\"]');"
                                "  if (correctBtn && typeof selectOpt === 'function' && typeof checkAns === 'function') {"
                                "    selectOpt(correctBtn); checkAns();"
                                "  }"
                                "  return JSON.stringify({"
                                "    userAgent: navigator.userAgent,"
                                "    title: document.title,"
                                "    appWidth: appRect.width,"
                                "    appHeight: appRect.height,"
                                "    wmCount: Object.keys(window.WM || {}).length,"
                                "    connCount: Object.keys(window.CONN || {}).length,"
                                "    nodesCount: (window.NODES || []).length,"
                                "    xp: (window.TEAS_STATE && window.TEAS_STATE.xp) || 0,"
                                "    coins: (window.TEAS_STATE && window.TEAS_STATE.coins) || 0"
                                "  });"
                                "})()"
                            ),
                            "returnByValue": True,
                        },
                    )
                    val = json.loads(eval_res["result"]["value"])
                    self.assertIn("HeadlessChrome/156", val["userAgent"])
                    self.assertGreater(val["appWidth"], 100, f"Zero layout width in {mod_path.name}")
                    self.assertGreater(val["appHeight"], 50, f"Zero layout height in {mod_path.name}")
                    self.assertGreaterEqual(val["wmCount"], 1129, f"Low WM in {mod_path.name}")
                    self.assertGreaterEqual(val["connCount"], 85, f"Low CONN in {mod_path.name}")
                    self.assertGreaterEqual(val["nodesCount"], 3, f"Missing NODES in {mod_path.name}")
                    if "Hub_v5.html" in mod_path.name and "Enriched_G31" not in mod_path.name:
                        self.assertGreaterEqual(val["wmCount"], 1129, f"Expected 1,129 WM in {mod_path.name}")
                        self.assertEqual(val["xp"], 20, f"Click interaction did not award 20 XP in {mod_path.name}")
                        self.assertEqual(val["coins"], 10, f"Click interaction did not award 10 Coins in {mod_path.name}")
            finally:
                cdp.close()
        finally:
            proc.kill()
            proc.wait()
            subprocess.run(["pkill", "-9", "chromium"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == "__main__":
    unittest.main()
