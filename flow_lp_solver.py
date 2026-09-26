"""Zweite unabhängige exakte Gegenprobe: dasselbe Min-Cost-Flow-Problem als lineares Programm, gelöst von HiGHS (`scipy.optimize.linprog`).

Anders als OR-Tools' `SimpleMinCostFlow` (Cost-Scaling-Push-Relabel, ein Netzwerkverfahren) kennt HiGHS keine Netzwerkstruktur: die Knoten-Kanten-Inzidenzmatrix wird als allgemeines LP behandelt (Simplex bzw. Innere Punkte).
Bei ganzzahligen Kapazitäten und Bilanzen liefert HiGHS trotzdem eine ganzzahlige Ecke - die Inzidenzmatrix ist total unimodular. Bilanzkonvention wie im Netzwerksimplex: (Abfluss - Zufluss)(v) = supply(v)."""

from scipy.optimize import linprog
from scipy.sparse import lil_matrix

ZERO = 1e-9


def solve_lp(instance):
    """Rückgabe (flow dict Arc.idx -> Fluss, Kosten, zulässig)."""
    index = {v: i for i, v in enumerate(instance.nodes)}
    arcs = instance.arcs
    a_eq = lil_matrix((len(instance.nodes), len(arcs)))
    for j, a in enumerate(arcs):
        a_eq[index[a.tail], j] += 1.0
        a_eq[index[a.head], j] -= 1.0
    b_eq = [instance.supply.get(v, 0.0) for v in instance.nodes]
    res = linprog([a.cost for a in arcs], A_eq=a_eq.tocsr(), b_eq=b_eq, bounds=[(0.0, a.capacity) for a in arcs], method="highs")
    if res.status != 0:
        return {a.idx: 0.0 for a in arcs}, float("nan"), False
    flow = {a.idx: (0.0 if abs(x) < ZERO else float(x)) for a, x in zip(arcs, res.x)}
    return flow, float(res.fun), True
