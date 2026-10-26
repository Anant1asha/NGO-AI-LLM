#!/usr/bin/env python3
"""
lint_superbrain_parity.py
Zero-dependency Python counterpart to scripts/lint_superbrain_parity.mjs.
Validates rule parity, enforces Antigravity scalar frontmatter invariants (0 !!seq),
audits SUPERBRAIN.md invariants, and scans for secret leakage.
Uses Python standard library ONLY (no PyYAML or third-party dependencies required).
"""

import os
import re
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent
print("=== Superbrain Instruction Architecture & Rule Parity Audit (Python Fallback) ===\n")

error_count = 0
check_count = 0

def report_pass(message: str) -> None:
    global check_count
    check_count += 1
    print(f"  [PASS] {message}")

def report_fail(message: str) -> None:
    global check_count, error_count
    check_count += 1
    error_count += 1
    print(f"  [FAIL] {message}", file=sys.stderr)

# ---------------------------------------------------------------------------
# 1. Rule Parity Check (.agents/rules <-> .superbrain/rules)
# ---------------------------------------------------------------------------
print("--- 1. Rule Parity Check (.agents/rules <-> .superbrain/rules) ---")

agents_rules_dir = repo_root / ".agents" / "rules"
superbrain_rules_dir = repo_root / ".superbrain" / "rules"

if not agents_rules_dir.is_dir():
    report_fail(f".agents/rules directory missing at: {agents_rules_dir}")
elif not superbrain_rules_dir.is_dir():
    report_fail(f".superbrain/rules directory missing at: {superbrain_rules_dir}")
else:
    agents_files = [f.name for f in agents_rules_dir.iterdir() if f.name.endswith(".md")]
    superbrain_files = [f.name for f in superbrain_rules_dir.iterdir() if f.name.endswith(".md")]

    for a_file in agents_files:
        expected_sb = a_file.replace("_", "-")
        if expected_sb in superbrain_files:
            report_pass(f".agents/rules/{a_file} <-> .superbrain/rules/{expected_sb}")
        else:
            report_fail(f"Missing .superbrain/rules/{expected_sb} for .agents/rules/{a_file}")

    for s_file in superbrain_files:
        expected_ag = s_file.replace("-", "_")
        if expected_ag in agents_files or s_file in agents_files:
            report_pass(f".superbrain/rules/{s_file} maps to tracked agent rule")
        else:
            report_fail(f"Unmapped .superbrain/rules/{s_file} has no counterpart in .agents/rules/")

# ---------------------------------------------------------------------------
# 2. YAML Frontmatter Schema Validation in .superbrain/rules/*.md
# ---------------------------------------------------------------------------
print("\n--- 2. YAML Frontmatter Schema Validation (.superbrain/rules/*.md) ---")

if superbrain_rules_dir.is_dir():
    for f_path in sorted(superbrain_rules_dir.glob("*.md")):
        fname = f_path.name
        content = f_path.read_text(encoding="utf-8")

        if not content.startswith("---"):
            report_fail(f"{fname}: Missing opening YAML frontmatter delimiter (---)")
            continue

        match = re.match(r"^---\r?\n([\s\S]*?)\r?\n---", content)
        if not match:
            report_fail(f"{fname}: Malformed or unclosed YAML frontmatter")
            continue

        fm = match.group(1)
        if re.search(r"^description:\s*.+", fm, re.MULTILINE):
            report_pass(f"{fname}: Valid 'description' defined")
        else:
            report_fail(f"{fname}: Frontmatter missing non-empty 'description' field")

        has_always = bool(re.search(r"^alwaysApply:\s*(true|false)", fm, re.MULTILINE))
        has_globs = bool(re.search(r"^globs:\s*.+", fm, re.MULTILINE))
        if has_always or has_globs:
            report_pass(f"{fname}: Execution trigger configured ({'alwaysApply' if has_always else 'globs'})")
        else:
            report_fail(f"{fname}: Frontmatter must define either 'alwaysApply: true|false' or 'globs'")

# ---------------------------------------------------------------------------
# 2b. YAML Frontmatter Schema Validation in .agents/rules/*.md (Antigravity)
# ---------------------------------------------------------------------------
print("\n--- 2b. YAML Frontmatter Schema Validation (.agents/rules/*.md) ---")

if agents_rules_dir.is_dir():
    for f_path in sorted(agents_rules_dir.glob("*.md")):
        fname = f_path.name
        content = f_path.read_text(encoding="utf-8")

        if not content.startswith("---"):
            report_fail(f".agents/rules/{fname}: Missing opening YAML frontmatter delimiter (---)")
            continue

        match = re.match(r"^---\r?\n([\s\S]*?)\r?\n---", content)
        if not match:
            report_fail(f".agents/rules/{fname}: Malformed or unclosed YAML frontmatter")
            continue

        fm = match.group(1)

        # Prohibit sequence arrays that crash Go language server (language_server.exe unmarshals to Globs string)
        if re.search(r"globs:\s*\[", fm, re.MULTILINE):
            report_fail(f".agents/rules/{fname}: Invalid array 'globs: [...]' detected. Must be scalar string 'globs: \"**/*\"'.")
        elif not re.search(r"^globs:\s*.+", fm, re.MULTILINE):
            report_fail(f".agents/rules/{fname}: Missing required scalar 'globs' definition")
        else:
            report_pass(f".agents/rules/{fname}: Scalar 'globs' schema verified")

        if re.search(r"^trigger:\s*(always_on|model_decision)", fm, re.MULTILINE):
            report_pass(f".agents/rules/{fname}: Valid trigger configured")
        else:
            report_fail(f".agents/rules/{fname}: Frontmatter should specify 'trigger: always_on' or 'trigger: model_decision'")

# ---------------------------------------------------------------------------
# 3. SUPERBRAIN.md Core Invariant Audit
# ---------------------------------------------------------------------------
print("\n--- 3. SUPERBRAIN.md Core Invariant Audit ---")

superbrain_path = repo_root / "SUPERBRAIN.md"
if not superbrain_path.is_file():
    report_fail(f"SUPERBRAIN.md missing at root: {superbrain_path}")
else:
    sb_content = superbrain_path.read_text(encoding="utf-8")

    if ("does not build, pre-train, or fine-tune large language models" in sb_content or
            "Autonomous AI Agent Ecosystem" in sb_content):
        report_pass("Ecosystem Identity Invariant preserved")
    else:
        report_fail("SUPERBRAIN.md lacks explicit Ecosystem Identity Invariant statement")

    if "Tier 1" in sb_content and "OpenRouter" in sb_content and "Tier 3" in sb_content and "reserve" in sb_content:
        report_pass("Zero-Token Bleed & 3-Tier cascade invariant preserved")
    else:
        report_fail("SUPERBRAIN.md lacks complete 3-Tier Anti-Bleed routing rules")

    if "Serena MCP" in sb_content and ".serena/memories/" in sb_content:
        report_pass("Serena MCP Default Local Memory Mandate preserved")
    else:
        report_fail("SUPERBRAIN.md lacks Serena MCP memory specifications")

    if "Safe file operations" in sb_content or "forbidden from executing destructive shell commands" in sb_content:
        report_pass("Safe File Operations policy preserved")
    else:
        report_fail("SUPERBRAIN.md lacks Safe File Operations guardrails")

# ---------------------------------------------------------------------------
# 4. Zero-Secret Static Exposure Scan
# ---------------------------------------------------------------------------
print("\n--- 4. Zero-Secret Static Exposure Scan ---")

secret_patterns = [
    re.compile(r"(?:" + "sk-or-v1-" + r"[a-zA-Z0-9]{20,})", re.IGNORECASE),
    re.compile(r"(?:" + "github_pat_" + r"[a-zA-Z0-9_]{20,})", re.IGNORECASE),
    re.compile(r"(?:" + "ghp_" + r"[a-zA-Z0-9]{20,})", re.IGNORECASE),
    re.compile(r"(?:" + "AIzaSy" + r"[a-zA-Z0-9_-]{20,})", re.IGNORECASE),
    re.compile(r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----", re.IGNORECASE)
]

files_to_scan = [
    superbrain_path,
    repo_root / ".markdownlint-cli2.jsonc"
]

if superbrain_rules_dir.is_dir():
    files_to_scan.extend(sorted(superbrain_rules_dir.glob("*.md")))

if agents_rules_dir.is_dir():
    files_to_scan.extend(sorted(agents_rules_dir.glob("*.md")))

for f_path in files_to_scan:
    if not f_path.is_file():
        continue
    rel_name = f_path.relative_to(repo_root).as_posix()
    content = f_path.read_text(encoding="utf-8")

    file_has_secret = False
    for pat in secret_patterns:
        if pat.search(content):
            report_fail(f"Potential secret or token pattern detected in: {rel_name}")
            file_has_secret = True
            break

    if not file_has_secret:
        report_pass(f"Clean secret scan: {rel_name}")

# ---------------------------------------------------------------------------
# Summary & Exit Code
# ---------------------------------------------------------------------------
print("\n=== Audit Summary ===")
print(f"Total checks: {check_count}")
print(f"Passed: {check_count - error_count}")
print(f"Failed: {error_count}")

if error_count > 0:
    print("\n❌ Superbrain parity and schema audit FAILED.", file=sys.stderr)
    sys.exit(1)
else:
    print("\n✅ Superbrain instruction architecture & parity audit PASSED.")
    sys.exit(0)
