"""
G71: Legacy Output HTML5 Modules WM Compounding Upgrade & Zero-External-URL Remediation
Upgrades all <1,000 WM legacy HTML5 modules in Aasha-AI/aasha-pipeline-with-master-json/output/
with the compounding WM/CONN dictionary and scrubs any external http(s):// URLs so every
compiled output HTML5 module satisfies 0 external URLs and <= 20 MiB per-child-HTML cap.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict

MAX_CHILD_HTML_BYTES = 20_971_520


def remediate_legacy_output_html_modules(repo_root: Path) -> Dict[str, Any]:
    out_dir = repo_root / "Aasha-AI" / "aasha-pipeline-with-master-json" / "output"
    defaults_path = repo_root / "Aasha-AI" / "aasha-pipeline-with-master-json" / "config" / "defaults_expanded_v2.json"
    v2 = json.loads(defaults_path.read_text(encoding="utf-8"))
    wm_json = json.dumps(v2["WM"], ensure_ascii=False, separators=(",", ":"))
    conn_json = json.dumps(v2["CONN"], ensure_ascii=False, separators=(",", ":"))

    html_files = sorted(out_dir.rglob("*.html"))
    wm_upgraded_count = 0
    ext_url_scrubbed_count = 0
    oversized_files = []

    for html_path in html_files:
        txt = html_path.read_text(encoding="utf-8", errors="ignore")
        changed = False

        wm_m = re.search(r"var WM=(\{[^\n]*\});", txt)
        if wm_m:
            try:
                cur_wm = json.loads(wm_m.group(1))
            except Exception:
                cur_wm = {}
            if len(cur_wm) < len(v2["WM"]):
                txt = txt[:wm_m.start()] + f"var WM={wm_json};" + txt[wm_m.end():]
                wm_upgraded_count += 1
                changed = True

        conn_m = re.search(r"var CONN=(\{[^\n]*\});", txt)
        if conn_m:
            try:
                cur_conn = json.loads(conn_m.group(1))
            except Exception:
                cur_conn = {}
            if len(cur_conn) < len(v2["CONN"]):
                txt = txt[:conn_m.start()] + f"var CONN={conn_json};" + txt[conn_m.end():]
                changed = True

        if re.search(r"https?://", txt):
            txt = re.sub(r"https?://[^\s\"'<>`]+", "aasha://offline-local", txt)
            ext_url_scrubbed_count += 1
            changed = True

        if changed:
            html_path.write_text(txt, encoding="utf-8")

        if html_path.stat().st_size > MAX_CHILD_HTML_BYTES:
            oversized_files.append(str(html_path.relative_to(out_dir)))

    # Final verification pass
    remaining_ext = 0
    remaining_low_wm = 0
    for html_path in html_files:
        txt = html_path.read_text(encoding="utf-8", errors="ignore")
        if re.search(r"https?://", txt):
            remaining_ext += 1
        wm_m = re.search(r"var WM=(\{[^\n]*\});", txt)
        if wm_m:
            try:
                if len(json.loads(wm_m.group(1))) < 1000:
                    remaining_low_wm += 1
            except Exception:
                remaining_low_wm += 1

    return {
        "ok": remaining_ext == 0 and remaining_low_wm == 0 and len(oversized_files) == 0,
        "total_html_files_scanned": len(html_files),
        "wm_upgraded_count": wm_upgraded_count,
        "ext_url_scrubbed_count": ext_url_scrubbed_count,
        "remaining_ext_url_files": remaining_ext,
        "remaining_low_wm_files": remaining_low_wm,
        "oversized_files": oversized_files,
        "compounding_wm_entries": len(v2["WM"]),
    }
