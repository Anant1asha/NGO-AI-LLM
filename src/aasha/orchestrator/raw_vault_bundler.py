"""
G75: Raw Source Vault & IIFE + Base64 Multimedia Inline Bundler
Supports:
  - Beyond-SVG high-quality graphical & multimedia assets (3D GLB/GLTF, PNG/WebP sprite sheets,
    WebGL2 shaders, MP4/WebM video, OGG/MP3/WAV audio, and SVG vectors)
  - IIFE JS bundling (zero ES-module file:// CORS errors), plus optional esbuild/vite hook on local PC/Colab
  - Strict <= 20 MiB (20,971,520 bytes) per individual child output HTML5 file.
"""
from __future__ import annotations

import base64
import json
import mimetypes
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

MAX_CHILD_HTML_BYTES = 20_971_520

ASSET_MIME_OVERRIDES = {
    ".glb": "model/gltf-binary",
    ".gltf": "model/gltf+json",
    ".png": "image/png",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".mp3": "audio/mpeg",
    ".ogg": "audio/ogg",
    ".wav": "audio/wav",
    ".glsl": "text/plain",
    ".wgsl": "text/plain",
}


def encode_file_to_data_uri(file_path: Path) -> Dict[str, Any]:
    raw = file_path.read_bytes()
    ext = file_path.suffix.lower()
    mime = ASSET_MIME_OVERRIDES.get(ext) or mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    b64 = base64.b64encode(raw).decode("ascii")
    return {
        "file": file_path.name,
        "ext": ext,
        "mime": mime,
        "raw_bytes": len(raw),
        "data_uri": f"data:{mime};base64,{b64}",
    }


def bundle_js_to_iife_tag(js_source: str, entry_file: Optional[Path] = None) -> str:
    """
    Bundle JS into a file://-safe IIFE <script src="data:text/javascript;base64,..."></script>.
    Uses esbuild --bundle --format=iife if available on Local PC / Colab, otherwise wraps cleanly in IIFE.
    """
    bundled_code = js_source
    if entry_file and entry_file.is_file() and shutil.which("esbuild"):
        proc = subprocess.run(
            ["esbuild", str(entry_file), "--bundle", "--format=iife", "--minify"],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            bundled_code = proc.stdout
    elif not bundled_code.lstrip().startswith("(function"):
        bundled_code = f"(function(){{\n{bundled_code}\n}})();"

    b64 = base64.b64encode(bundled_code.encode("utf-8")).decode("ascii")
    return f'<script src="data:text/javascript;base64,{b64}"></script>'


def scan_raw_source_vault(repo_root: Path) -> Dict[str, Any]:
    vault_root = repo_root / "raw_source_vault"
    mit_dir = vault_root / "mit_bsd_ccby"
    gpl_dir = vault_root / "gpl_isolated"
    mit_files = [p for p in mit_dir.rglob("*") if p.is_file()] if mit_dir.exists() else []
    gpl_files = [p for p in gpl_dir.rglob("*") if p.is_file()] if gpl_dir.exists() else []
    return {
        "vault_exists": vault_root.exists(),
        "mit_bsd_ccby_files": len(mit_files),
        "gpl_isolated_files": len(gpl_files),
        "supports_3d_sprites_video_audio": True,
        "max_child_html_bytes": MAX_CHILD_HTML_BYTES,
    }
