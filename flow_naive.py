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

Mehrperioden-Fall: Perioden werden chronologisch nacheinander abgearbeitet (Periode 0
zuerst), und die Lagerhaltungskante wird hier NIE genutzt - route_arcs kennt nur
Kanten innerhalb ein und derselben Periode. Das ist genau die "myopische" Baseline:
eine unkoordinierte Disposition plant nicht vorausschauend Bestand für eine künftige
Nachfragespitze auf, sondern reagiert immer nur auf die aktuelle Periode.
"""

from flow_network import dc_in, dc_out, node_name

EPS = 1e-9


def solve_naive(instance):
    arc_by_pair = {(a.tail, a.head): a for a in instance.arcs}
    remaining = {a.idx: a.capacity for a in instance.arcs}
    flow = {a.idx: 0.0 for a in instance.arcs}
    n = instance.n_periods

    def route_arcs(p, dc, s, t):
        p_t, dc_in_t, dc_out_t, s_t = node_name(p, t, n), dc_in(dc, t, n), dc_out(dc, t, n), node_name(s, t, n)
        return [
            arc_by_pair[("SRC", p_t)],
            arc_by_pair[(p_t, dc_in_t)],
            arc_by_pair[(dc_in_t, dc_out_t)],
            arc_by_pair[(dc_out_t, s_t)],
        ]

    for t in range(n):
        for s in instance.stores:
            s_t = node_name(s, t, n)
            need = instance.store_demand.get((s, t), 0.0)
            demand_arc = arc_by_pair[(s_t, "SINK")]
            shortfall_arc = arc_by_pair[("SRC", s_t)]

            while need > EPS:
                best = None
                best_cost = None
                for p in instance.plants:
                    for dc in instance.dcs:
                        arcs = route_arcs(p, dc, s, t)
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
