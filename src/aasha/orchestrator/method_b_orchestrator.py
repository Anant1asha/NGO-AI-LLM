from __future__ import annotations
import re
from typing import Dict, Tuple

MATH_RE = re.compile(r"\$[^$]+\$")

def insulate_math_tokens(text: str) -> Tuple[str, Dict[str, str]]:
    token_map: Dict[str, str] = {}
    def _repl(m: re.Match) -> str:
        key = f"__AASHA_MATH_{len(token_map)}__"
        token_map[key] = m.group(0)
        return key
    return MATH_RE.sub(_repl, text), token_map

def restore_math_tokens(text: str, token_map: Dict[str, str]) -> str:
    out = text
    for k, v in token_map.items():
        out = out.replace(k, v)
    return out
