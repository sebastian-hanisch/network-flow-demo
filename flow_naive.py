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

from flow_network import dc_in, dc_out, distance, node_name

EPS = 1e-9


RULES = {
    "fcfs": ("given", "cheapest"),
    "largest_first": ("demand_desc", "cheapest"),
    "regional": ("given", "regional"),
}
RULE_LABELS = {
    "fcfs": "Unoptimiert (FCFS je Filiale)",
    "largest_first": "Größte Nachfrage zuerst",
    "regional": "Regional (nächstes DC, dann billigstes Werk)",
}


def solve_naive(instance, order="given", rule="cheapest"):
    """`order`: 'given' (Filialen in der Reihenfolge der Instanz) oder 'demand_desc' (je Periode die Filiale mit der größten Nachfrage zuerst). `rule`: 'cheapest' (die billigste noch freie komplette Route über alle Werke und DCs)
    oder 'regional' (das der Filiale nächste DC mit noch freier Route, dort das billigste Werk - die übliche zweistufige Praxisregel). Standard = die FCFS-Baseline der Demo."""
    assert order in ("given", "demand_desc") and rule in ("cheapest", "regional")
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

    def cheapest_route(s, t, dcs):
        best, best_cost = None, None
        for p in instance.plants:
            for dc in dcs:
                arcs = route_arcs(p, dc, s, t)
                if min(remaining[a.idx] for a in arcs) <= EPS:
                    continue
                cost = sum(a.cost for a in arcs)
                if best_cost is None or cost < best_cost - 1e-9:
                    best_cost, best = cost, arcs
        return best

    for t in range(n):
        stores = list(instance.stores)
        if order == "demand_desc":
            stores.sort(key=lambda s: (-instance.store_demand.get((s, t), 0.0), s))
        for s in stores:
            s_t = node_name(s, t, n)
            need = instance.store_demand.get((s, t), 0.0)
            demand_arc = arc_by_pair[(s_t, "SINK")]
            shortfall_arc = arc_by_pair[("SRC", s_t)]
            dcs_by_distance = sorted(instance.dcs, key=lambda d: (distance(instance.dc_pos[d], instance.store_pos[s]), d))

            while need > EPS:
                if rule == "cheapest":
                    best = cheapest_route(s, t, instance.dcs)
                else:
                    best = None
                    for dc in dcs_by_distance:
                        best = cheapest_route(s, t, [dc])
                        if best is not None:
                            break
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


def solve_rule(instance, name):
    """Praxisregel nach Namen ('fcfs', 'largest_first', 'regional')."""
    order, rule = RULES[name]
    return solve_naive(instance, order=order, rule="cheapest" if rule == "cheapest" else "regional")
