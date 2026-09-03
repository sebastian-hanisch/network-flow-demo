"""Gemeinsame Kennzahlen-Berechnung für alle drei Verfahren (Unoptimiert,
Netzwerksimplex, Referenz) - operiert einheitlich auf einem flow-Dict (Arc.idx ->
Flusswert), egal von welchem Solver es stammt."""

from collections import defaultdict

KIND_LABELS = {
    "produktion": "Produktion",
    "umschlag": "Umschlag (DC)",
    "transport_werk_dc": "Transport Werk→DC",
    "transport_dc_filiale": "Transport DC→Filiale",
    "nachfrage": "Nachfrage (intern, 0 €)",
    "fehlmenge": "Fehlmenge (Notbeschaffung)",
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


def dc_utilization(instance, flow):
    rows = []
    by_dc_arc = {a.tail: a for a in instance.arcs if a.kind == "umschlag"}
    for dc in instance.dcs:
        arc = next(a for a in instance.arcs if a.kind == "umschlag" and a.tail == f"{dc}_in")
        used = flow.get(arc.idx, 0.0)
        cap = instance.dc_throughput[dc]
        rows.append({
            "DC": dc, "Durchsatz genutzt": used, "Durchsatzkapazität": cap,
            "Auslastung": (used / cap * 100.0) if cap > 0 else 0.0,
        })
    return rows


def plant_utilization(instance, flow):
    rows = []
    for p in instance.plants:
        arc = next(a for a in instance.arcs if a.kind == "produktion" and a.head == p)
        used = flow.get(arc.idx, 0.0)
        cap = instance.plant_capacity[p]
        rows.append({
            "Werk": p, "Produziert": used, "Kapazität": cap,
            "Auslastung": (used / cap * 100.0) if cap > 0 else 0.0,
        })
    return rows


def comparison_rows(instance, results):
    """results: dict label -> dict(flow=..., cost=..., runtime=..., extra=...)"""
    rows = []
    for label, r in results.items():
        shortfall = shortfall_total(instance, r["flow"])
        rows.append({
            "Verfahren": label,
            "Gesamtkosten (€)": round(r["cost"], 2),
            "Fehlmenge (Einheiten)": round(shortfall, 1),
            "Laufzeit (ms)": round(r["runtime"] * 1000, 2),
        })
    return rows


def savings_pct(baseline_cost, improved_cost):
    if baseline_cost <= 0:
        return 0.0
    return (baseline_cost - improved_cost) / baseline_cost * 100.0
