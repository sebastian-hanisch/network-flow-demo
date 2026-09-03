"""Referenzlösung über Google OR-Tools (SimpleMinCostFlow) als Cross-Check für den
selbst geschriebenen Netzwerksimplex: bestätigt Korrektheit (identische Gesamtkosten)
und liefert einen Laufzeitvergleich. OR-Tools' SimpleMinCostFlow verlangt ganzzahlige
Kapazitäten/Kosten - Kosten werden dafür mit COST_SCALE hochskaliert und beim Ergebnis
wieder heruntergerechnet, Kapazitäten sind im Modell bereits ganzzahlig."""

from ortools.graph.python import min_cost_flow

COST_SCALE = 10_000


def solve_reference(instance):
    smcf = min_cost_flow.SimpleMinCostFlow()

    node_id = {v: i for i, v in enumerate(instance.nodes)}
    arc_ortools_idx = {}
    for a in instance.arcs:
        cap = int(round(a.capacity))
        cost = int(round(a.cost * COST_SCALE))
        oidx = smcf.add_arc_with_capacity_and_unit_cost(node_id[a.tail], node_id[a.head], cap, cost)
        arc_ortools_idx[a.idx] = oidx

    for v in instance.nodes:
        smcf.set_node_supply(node_id[v], int(round(instance.supply.get(v, 0.0))))

    status = smcf.solve()
    feasible = status == smcf.OPTIMAL

    flow = {}
    if feasible:
        for a in instance.arcs:
            flow[a.idx] = float(smcf.flow(arc_ortools_idx[a.idx]))
        cost = float(smcf.optimal_cost()) / COST_SCALE
    else:
        flow = {a.idx: 0.0 for a in instance.arcs}
        cost = float("nan")

    return flow, cost, feasible, status
