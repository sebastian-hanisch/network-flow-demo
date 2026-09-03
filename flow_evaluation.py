"""Gemeinsame Kennzahlen-Berechnung für alle drei Verfahren (Unoptimiert,
Netzwerksimplex, Referenz) - operiert einheitlich auf einem flow-Dict (Arc.idx ->
Flusswert), egal von welchem Solver es stammt."""

from collections import defaultdict

from flow_network import dc_in, dc_out, node_name

KIND_LABELS = {
    "produktion": "Produktion",
    "umschlag": "Umschlag (DC)",
    "transport_werk_dc": "Transport Werk→DC",
    "transport_dc_filiale": "Transport DC→Filiale",
    "nachfrage": "Nachfrage (intern, 0 €)",
    "fehlmenge": "Fehlmenge (Notbeschaffung)",
    "lagerhaltung": "Lagerhaltung (Bestand)",
}


def total_cost(instance, flow):
    return sum(a.cost * flow.get(a.idx, 0.0) for a in instance.arcs)


def cost_breakdown(instance, flow):
    cost_by_kind = defaultdict(float)
    units_by_kind = defaultdict(float)
    for a in instance.arcs:
        f = flow.get(a.idx, 0.0)
        cost_by_kind[a.kind] += a.cost * f
        units_by_kind[a.kind] += f
    return cost_by_kind, units_by_kind


def shortfall_total(instance, flow):
    return sum(flow.get(a.idx, 0.0) for a in instance.arcs if a.kind == "fehlmenge")


def inventory_total(instance, flow):
    return sum(flow.get(a.idx, 0.0) for a in instance.arcs if a.kind == "lagerhaltung")


def dc_utilization(instance, flow):
    """Durchsatzauslastung je DC, über alle Perioden aufsummiert (genutzt/Kapazität
    je Periode addiert) - ein einzelner Auslastungswert je DC, unabhängig von
    n_periods."""
    umschlag_by_tail = {a.tail: a for a in instance.arcs if a.kind == "umschlag"}
    rows = []
    for dc in instance.dcs:
        used = 0.0
        cap = 0.0
        for t in range(instance.n_periods):
            arc = umschlag_by_tail[dc_in(dc, t, instance.n_periods)]
            used += flow.get(arc.idx, 0.0)
            cap += instance.dc_throughput[dc]
        rows.append({
            "DC": dc, "Durchsatz genutzt": used, "Durchsatzkapazität": cap,
            "Auslastung": (used / cap * 100.0) if cap > 0 else 0.0,
        })
    return rows


def plant_utilization(instance, flow):
    """Produktionsauslastung je Werk, über alle Perioden aufsummiert."""
    produktion_by_head = {a.head: a for a in instance.arcs if a.kind == "produktion"}
    rows = []
    for p in instance.plants:
        used = 0.0
        cap = 0.0
        for t in range(instance.n_periods):
            arc = produktion_by_head[node_name(p, t, instance.n_periods)]
            used += flow.get(arc.idx, 0.0)
            cap += instance.plant_capacity[p]
        rows.append({
            "Werk": p, "Produziert": used, "Kapazität": cap,
            "Auslastung": (used / cap * 100.0) if cap > 0 else 0.0,
        })
    return rows


def inventory_by_period(instance, flow):
    """Lagerbestand je DC, der von Periode t nach t+1 mitgenommen wird - eine Zeile
    je (DC, Periodenübergang). Leer, wenn n_periods == 1 (keine Lagerhaltungskanten)."""
    rows = []
    for a in instance.arcs:
        if a.kind != "lagerhaltung":
            continue
        dc = next(d for d in instance.dcs if a.tail == dc_out(d, a.period, instance.n_periods))
        rows.append({
            "DC": dc, "Periode": a.period + 1, "Lagerbestand": flow.get(a.idx, 0.0),
            "Lagerkapazität": a.capacity,
        })
    return rows


def comparison_rows(instance, results):
    """results: dict label -> dict(flow=..., cost=..., runtime=..., extra=...)"""
    rows = []
    for label, r in results.items():
        shortfall = shortfall_total(instance, r["flow"])
        row = {
            "Verfahren": label,
            "Gesamtkosten (€)": round(r["cost"], 2),
            "Fehlmenge (Einheiten)": round(shortfall, 1),
            "Laufzeit (ms)": round(r["runtime"] * 1000, 2),
        }
        if instance.n_periods > 1:
            row["Ø Lagerbestand"] = round(inventory_total(instance, r["flow"]) / max(1, instance.n_periods - 1), 1)
        rows.append(row)
    return rows


def savings_pct(baseline_cost, improved_cost):
    if baseline_cost <= 0:
        return 0.0
    return (baseline_cost - improved_cost) / baseline_cost * 100.0
