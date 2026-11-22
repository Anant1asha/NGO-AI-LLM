"""Render an ObjectGraph skill dependency graph to Mermaid or Graphviz DOT.

The ``.og`` format *is* an object graph, so make it visible. These pure
functions turn the structure from :meth:`SkillEngine.get_skill_graph` into:

- **Mermaid** — renders inline on GitHub/GitLab/Obsidian/most Markdown viewers
  with no tooling; paste it straight into a README.
- **Graphviz DOT** — pipe to ``dot -Tsvg`` for a publication-quality diagram.
- **HTML** — a self-contained, interactive force-directed graph (drag / zoom /
  hover) for exploring a large skill library in the browser.

All color nodes by role and highlight entry-point roots, dependency cycles, and
missing (referenced-but-unloaded) dependencies. Pure (no I/O) → unit-testable.
"""

from __future__ import annotations

import json
import re
from typing import Any

# Role → fill color (GitHub-dark friendly). Unknown roles fall back to grey.
_ROLE_COLORS: dict[str, str] = {
    "skill": "#238636",  # green
    "rule": "#8957e5",  # purple
    "integration": "#1f6feb",  # blue
    "env": "#9e6a03",  # amber
    "general": "#30363d",  # grey
}
_FALLBACK_COLOR = "#30363d"
_ROOT_COLOR = "#1f6feb"
_CYCLE_COLOR = "#f85149"
_MISSING_COLOR = "#f85149"


def _slug(name: str) -> str:
    """A Mermaid-safe node id (Mermaid ids must be alphanumeric/underscore)."""
    return re.sub(r"\W", "_", name)


def _node_color(node: dict[str, Any]) -> str:
    return _ROLE_COLORS.get(str(node.get("role") or "general"), _FALLBACK_COLOR)


def render_mermaid(graph: dict[str, Any]) -> str:
    """Render the skill graph as a Mermaid ``graph TD`` diagram."""
    nodes = graph.get("nodes", [])
    roots = set(graph.get("roots", []))
    cyclic = set(graph.get("cyclic", []))
    missing = sorted(set(graph.get("missing", [])))
    edges = graph.get("edges", [])

    lines = ["graph TD"]
    ids: dict[str, str] = {}

    for node in nodes:
        name = str(node["name"])
        ids[name] = _slug(name)
        if name in cyclic:
            cls = "cycle"
        elif name in roots:
            cls = "root"
        else:
            cls = f"role_{_slug(str(node.get('role') or 'general'))}"
        lines.append(f'    {ids[name]}["{name}"]:::{cls}')

    for name in missing:
        ids[name] = _slug(name)
        lines.append(f'    {ids[name]}["{name} (missing)"]:::missing')

    for src, dst in edges:
        lines.append(f"    {ids.get(src, _slug(src))} --> {ids.get(dst, _slug(dst))}")

    # Style classes (defined after nodes/edges, which Mermaid allows).
    lines.append(f"    classDef root fill:{_ROOT_COLOR},stroke:{_ROOT_COLOR},color:#ffffff;")
    lines.append(
        f"    classDef cycle fill:#3d1d1d,stroke:{_CYCLE_COLOR},stroke-width:3px,color:#f85149;"
    )
    lines.append(
        f"    classDef missing fill:#2d2d2d,stroke:{_MISSING_COLOR},"
        "color:#f85149,stroke-dasharray:5 3;"
    )
    for role in sorted({str(node.get("role") or "general") for node in nodes}):
        color = _ROLE_COLORS.get(role, _FALLBACK_COLOR)
        lines.append(f"    classDef role_{_slug(role)} fill:{color},stroke:#8b949e,color:#ffffff;")

    return "\n".join(lines)


def render_dot(graph: dict[str, Any]) -> str:
    """Render the skill graph as a Graphviz DOT digraph (pipe to ``dot -Tsvg``)."""
    nodes = graph.get("nodes", [])
    roots = set(graph.get("roots", []))
    cyclic = set(graph.get("cyclic", []))
    missing = sorted(set(graph.get("missing", [])))
    edges = graph.get("edges", [])

    lines = [
        "digraph skills {",
        "    rankdir=LR;",
        '    bgcolor="#0d1117";',
        '    node [shape=box, style="rounded,filled", fontname="sans-serif", '
        'fontcolor="#ffffff", color="#8b949e"];',
        '    edge [color="#8b949e"];',
    ]

    for node in nodes:
        name = str(node["name"])
        if name in cyclic:
            fill = _CYCLE_COLOR
        elif name in roots:
            fill = _ROOT_COLOR
        else:
            fill = _node_color(node)
        lines.append(f'    "{name}" [fillcolor="{fill}"];')

    for name in missing:
        lines.append(
            f'    "{name}" [label="{name}\\n(missing)", style="rounded,dashed", '
            f'fillcolor="#2d2d2d", color="{_MISSING_COLOR}", fontcolor="#f85149"];'
        )

    for src, dst in edges:
        lines.append(f'    "{src}" -> "{dst}";')

    lines.append("}")
    return "\n".join(lines)


def _vis_nodes(graph: dict[str, Any]) -> list[dict[str, Any]]:
    """Build vis-network node objects (color/border by root/cycle/role/missing)."""
    roots = set(graph.get("roots", []))
    cyclic = set(graph.get("cyclic", []))
    out: list[dict[str, Any]] = []
    for node in graph.get("nodes", []):
        name = str(node["name"])
        if name in cyclic:
            border = _CYCLE_COLOR
        elif name in roots:
            border = _ROOT_COLOR
        else:
            border = "#8b949e"
        out.append(
            {
                "id": name,
                "label": name,
                "title": f"{name} ({node.get('role') or 'general'})",
                "color": {"background": _node_color(node), "border": border},
                "borderWidth": 3 if (name in roots or name in cyclic) else 1,
                "font": {"color": "#ffffff"},
            }
        )
    for name in sorted(set(graph.get("missing", []))):
        out.append(
            {
                "id": name,
                "label": f"{name}\n(missing)",
                "color": {"background": "#2d2d2d", "border": _MISSING_COLOR},
                "borderWidth": 2,
                "shapeProperties": {"borderDashes": [5, 3]},
                "font": {"color": "#f85149"},
            }
        )
    return out


# Static page shell; node/edge data and counts are injected via str.replace so we
# avoid f-string brace-escaping over the CSS/JS blocks. vis-network is loaded from
# a CDN (needs internet to render; the file itself is self-contained otherwise).
_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Hachi ObjectGraph</title>
<script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
<style>
  html,body{margin:0;height:100%;background:#0d1117;color:#c9d1d9;font-family:system-ui,sans-serif}
  #graph{width:100vw;height:100vh}
  .panel{position:fixed;top:12px;left:12px;background:#161b22;border:1px solid #30363d;
    border-radius:8px;padding:12px 16px;font-size:13px;z-index:10;max-width:260px}
  .panel h1{font-size:14px;margin:0 0 8px}
  .panel .muted{color:#8b949e}
  .sw{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:6px;
    vertical-align:middle;border:1px solid #8b949e}
  .cy{border-color:#f85149;background:#3d1d1d}
  .ms{border-color:#f85149;background:#2d2d2d}
  .row{margin:3px 0}
</style>
</head>
<body>
<div class="panel">
  <h1>Hachi ObjectGraph</h1>
  <div class="muted">__COUNT__ skills · __EDGECOUNT__ edges</div>
  <div class="row"><span class="sw" style="background:#238636"></span>skill</div>
  <div class="row"><span class="sw" style="background:#1f6feb"></span>root / integration</div>
  <div class="row"><span class="sw" style="background:#8957e5"></span>rule</div>
  <div class="row"><span class="sw cy"></span>cycle</div>
  <div class="row"><span class="sw ms"></span>missing</div>
  <div class="muted" style="margin-top:8px">drag · scroll to zoom · hover for role</div>
</div>
<div id="graph"></div>
<script>
  const nodes = new vis.DataSet(__NODES__);
  const edges = new vis.DataSet(__EDGES__);
  const options = {
    nodes: { shape: "box", margin: 8 },
    edges: { arrows: "to", color: { color: "#8b949e" }, smooth: { type: "cubicBezier" } },
    physics: { barnesHut: { springLength: 150, gravitationalConstant: -12000 } },
    interaction: { hover: true, tooltipDelay: 120 }
  };
  new vis.Network(document.getElementById("graph"), { nodes, edges }, options);
</script>
</body>
</html>
"""


def render_html(graph: dict[str, Any]) -> str:
    """Render the skill graph as a self-contained interactive HTML page.

    Uses vis-network (loaded from a CDN, so rendering needs internet) for a
    force-directed graph you can drag, zoom, and hover. Node/edge data is
    embedded inline, so the file is otherwise standalone.
    """
    vis_edges = [{"from": src, "to": dst, "arrows": "to"} for src, dst in graph.get("edges", [])]
    return (
        _HTML_TEMPLATE.replace("__NODES__", json.dumps(_vis_nodes(graph)))
        .replace("__EDGES__", json.dumps(vis_edges))
        .replace("__COUNT__", str(graph.get("skill_count", 0)))
        .replace("__EDGECOUNT__", str(graph.get("edge_count", 0)))
    )


def render_graph(graph: dict[str, Any], fmt: str) -> str:
    """Dispatch to the requested renderer. Raises ValueError on unknown ``fmt``."""
    fmt = fmt.lower()
    if fmt == "mermaid":
        return render_mermaid(graph)
    if fmt == "dot":
        return render_dot(graph)
    if fmt == "html":
        return render_html(graph)
    raise ValueError(f"Unknown format: {fmt!r} (expected 'mermaid', 'dot', or 'html')")
