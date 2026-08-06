"""Reference-architecture sketch as a Mermaid diagram (spec §4.4c).

A projection of the graph's components and their data-flow / integration edges.
Labelled a Phase 1 sketch; the full pattern-library rendering is later work.
"""

from __future__ import annotations

from ..models.graph import ComponentType, EdgeKind
from ..models.solution_graph import SolutionGraph

# Mermaid node shape per component type, for a readable architecture sketch.
_SHAPE = {
    ComponentType.SERVICE: ("[", "]"),
    ComponentType.UI: ("[/", "/]"),
    ComponentType.DATASTORE: ("[(", ")]"),
    ComponentType.PIPELINE: ("[[", "]]"),
    ComponentType.ML_MODEL: ("([", "])"),
    ComponentType.GATEWAY: ("{{", "}}"),
    ComponentType.QUEUE: (">", "]"),
    ComponentType.INTEGRATION: ("[/", "/]"),
    ComponentType.EXTERNAL_SYSTEM: ("[(", ")]"),
}


def _safe(text: str) -> str:
    return text.replace('"', "'")


def architecture_mermaid(graph: SolutionGraph) -> str:
    """Render the component graph as a Mermaid flowchart string."""
    lines = ["flowchart LR"]
    for comp in graph.components:
        open_b, close_b = _SHAPE.get(comp.component_type, ("[", "]"))
        label = _safe(comp.name)
        if comp.technology:
            label += f"<br/><small>{_safe(comp.technology)}</small>"
        lines.append(f'  {comp.id}{open_b}"{label}"{close_b}')

    for edge in graph.architecture_edges():
        arrow = "-->" if edge.kind is EdgeKind.DATA_FLOW else "-.->"
        label = f'|"{_safe(edge.label)}"|' if edge.label else ""
        lines.append(f"  {edge.source_id} {arrow}{label} {edge.target_id}")

    return "\n".join(lines)
