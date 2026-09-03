"""Unoptimierte Baseline: jede Filiale wird nacheinander (First-Come-First-Served,
keine Priorisierung) über die jeweils güns­tigste zu diesem Zeitpunkt noch verfügbare
komplette Werk-DC-Filiale-Route beliefert - ohne Rücksicht darauf, was das für später
bediente Filialen an Kapazität übrig lässt. Gleiche Grundidee wie die
"Unoptimiert (FCFS)"-Baseline in den anderen Demos dieses Workspace (z. B.
warehouse-transfer-demo): rein lokale, unkoordinierte Entscheidungen je Filiale statt
einer netzweiten Abstimmung.

Anders als ein "dezentral je Zone"-Verfahren mit zwei unabhängigen Stufen (erst Werk->DC,
dann DC->Filiale) wird hier bewusst je Filiale eine vollständige Route auf einmal
reserviert - das hält den Fluss automatisch zulässig (Kapazitäten werden beim
Reservieren direkt verbraucht), ohne eine nachgelagerte Korrektur zu brauchen.
"""

from flow_network import dc_in, dc_out

EPS = 1e-9


def solve_naive(instance):
    arc_by_pair = {(a.tail, a.head): a for a in instance.arcs}
    remaining = {a.idx: a.capacity for a in instance.arcs}
    flow = {a.idx: 0.0 for a in instance.arcs}

    def route_arcs(p, dc, s):
        return [
            arc_by_pair[("SRC", p)],
            arc_by_pair[(p, dc_in(dc))],
            arc_by_pair[(dc_in(dc), dc_out(dc))],
            arc_by_pair[(dc_out(dc), s)],
        ]

    for s in instance.stores:
        need = instance.store_demand[s]
        demand_arc = arc_by_pair[(s, "SINK")]
        shortfall_arc = arc_by_pair[("SRC", s)]

        while need > EPS:
            best = None
            best_cost = None
            for p in instance.plants:
                for dc in instance.dcs:
                    arcs = route_arcs(p, dc, s)
                    available = min(remaining[a.idx] for a in arcs)
                    if available <= EPS:
                        continue
                    cost = sum(a.cost for a in arcs)
                    if best_cost is None or cost < best_cost - 1e-9:
                        best_cost = cost
                        best = arcs
            if best is None:
                break
            amount = min(min(remaining[a.idx] for a in best), need)
            for a in best:
                remaining[a.idx] -= amount
                flow[a.idx] += amount
            remaining[demand_arc.idx] -= amount
            flow[demand_arc.idx] += amount
            need -= amount

        if need > EPS:
            amount = min(need, remaining[shortfall_arc.idx])
            remaining[shortfall_arc.idx] -= amount
            flow[shortfall_arc.idx] += amount
            remaining[demand_arc.idx] -= amount
            flow[demand_arc.idx] += amount
            need -= amount

    cost = sum(a.cost * flow[a.idx] for a in instance.arcs)
    return flow, cost
