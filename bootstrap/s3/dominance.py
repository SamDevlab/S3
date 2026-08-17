"""Dominator Tree and Dominance Frontier calculation for S3 Control Flow Graph."""

from __future__ import annotations

from dataclasses import dataclass, field

from .cfg import ControlFlowGraph


@dataclass(slots=True)
class DominatorTree:
    """Dominator Tree and Dominance Frontier for a Control Flow Graph."""

    cfg: ControlFlowGraph
    entry_name: str
    dominators: dict[str, set[str]]
    idom: dict[str, str | None]
    dominance_frontier: dict[str, set[str]]
    children: dict[str, set[str]] = field(default_factory=dict)

    @classmethod
    def build(cls, cfg: ControlFlowGraph) -> DominatorTree:
        reachable = cfg.reachable_nodes()
        entry = cfg.entry_name

        if entry not in reachable:
            return cls(
                cfg=cfg,
                entry_name=entry,
                dominators={},
                idom={},
                dominance_frontier={},
                children={},
            )

        # Reverse postorder makes the fixed-point pass converge quickly even
        # for generated functions with thousands of small control-flow blocks.
        postorder: list[str] = []
        visited: set[str] = set()

        def visit(name: str) -> None:
            if name in visited:
                return
            visited.add(name)
            for successor in sorted(cfg.nodes[name].successors):
                if successor in reachable:
                    visit(successor)
            postorder.append(name)

        visit(entry)
        reverse_postorder = list(reversed(postorder))

        # 1. Compute Dominators (Iterative Algorithm)
        dom: dict[str, set[str]] = {}
        dom[entry] = {entry}
        for node in reachable - {entry}:
            dom[node] = set(reachable)

        changed = True
        while changed:
            changed = False
            for node in reverse_postorder:
                if node == entry:
                    continue
                preds = [p for p in cfg.nodes[node].predecessors if p in reachable]
                if preds:
                    new_dom = {node} | set.intersection(*(dom[p] for p in preds))
                else:
                    new_dom = {node}
                if new_dom != dom[node]:
                    dom[node] = new_dom
                    changed = True

        # 2. Compute Immediate Dominator (idom) & Children Tree
        idom: dict[str, str | None] = {entry: None}
        children: dict[str, set[str]] = {n: set() for n in reachable}

        for node in sorted(reachable - {entry}):
            strict_doms = dom[node] - {node}
            immed = max(strict_doms, key=lambda name: len(dom[name]), default=None)
            idom[node] = immed
            if immed is not None:
                children[immed].add(node)

        # 3. Compute Dominance Frontier (DF)
        df: dict[str, set[str]] = {n: set() for n in reachable}

        for y in sorted(reachable):
            preds = [p for p in cfg.nodes[y].predecessors if p in reachable]
            if len(preds) >= 2:
                for p in preds:
                    runner: str | None = p
                    while runner is not None and runner != idom[y]:
                        df[runner].add(y)
                        runner = idom[runner]

        return cls(
            cfg=cfg,
            entry_name=entry,
            dominators=dom,
            idom=idom,
            dominance_frontier=df,
            children=children,
        )

    def dominates(self, a: str, b: str) -> bool:
        """Returns True if block `a` dominates block `b`."""
        return a in self.dominators.get(b, set())

    def strictly_dominates(self, a: str, b: str) -> bool:
        """Returns True if block `a` strictly dominates block `b`."""
        return a != b and self.dominates(a, b)
