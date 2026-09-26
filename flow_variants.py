"""Szenario-Varianten (What-if): aus einer `ProblemInstance` entsteht mit geänderten Parametern eine zweite über `build_instance` - dieselben Positionen, Kosten und Lanes, nur das Gewählte ändert sich.

Änderungen: ein Verteilzentrum ausbauen (Durchsatz und Lager mal 1 + p %), ein Werk schließen (Kapazität 0), die Werkskapazität aller Werke ändern, die Nachfrage aller Filialen ändern, die Notbeschaffung verteuern (Strafkosten mal 1 + p %)."""

import flow_constants as C
from flow_network import build_instance

CHANGES = {
    "dc_expand": "Verteilzentrum ausbauen",
    "plant_close": "Werk schließen",
    "plant_capacity": "Werkskapazität aller Werke ändern",
    "demand": "Nachfrage aller Filialen ändern",
    "penalty": "Notbeschaffung verteuern",
}
# (kleinster Wert, größter Wert, Standard) in Prozent; None: kein Prozentwert
CHANGE_PCT = {"dc_expand": (10, 150, 50), "plant_close": None, "plant_capacity": (-40, 40, -20), "demand": (-30, 50, 20), "penalty": (20, 200, 100)}
NEEDS_TARGET = {"dc_expand": "dc", "plant_close": "plant"}


def describe(change, target=None, pct=None):
    if change == "dc_expand":
        return f"{target} um {pct} % ausbauen"
    if change == "plant_close":
        return f"{target} schließen"
    if change == "plant_capacity":
        return f"Werkskapazität {pct:+d} %"
    if change == "demand":
        return f"Nachfrage {pct:+d} %"
    return f"Notbeschaffung {pct} % teurer"


def make_variant(instance, change, target=None, pct=0):
    """Neue `ProblemInstance` mit der Änderung; die ursprüngliche bleibt unverändert."""
    assert change in CHANGES
    factor = 1.0 + pct / 100.0
    plant_capacity = dict(instance.plant_capacity)
    dc_throughput = dict(instance.dc_throughput)
    dc_storage = dict(instance.dc_storage_capacity)
    store_demand = dict(instance.store_demand)
    penalty = instance.shortfall_penalty
    if change == "dc_expand":
        dc_throughput[target] = float(round(dc_throughput[target] * factor))
        if target in dc_storage:
            dc_storage[target] = float(round(dc_storage[target] * factor))
    elif change == "plant_close":
        plant_capacity[target] = 0.0
    elif change == "plant_capacity":
        plant_capacity = {p: float(round(c * factor)) for p, c in plant_capacity.items()}
    elif change == "demand":
        store_demand = {k: float(round(v * factor)) for k, v in store_demand.items()}
    else:
        penalty = penalty * factor
    return build_instance(
        instance.plant_pos, instance.dc_pos, instance.store_pos,
        plant_capacity, instance.plant_unit_cost,
        dc_throughput, instance.dc_handling_cost,
        store_demand,
        instance.lane_capacity_plant_dc, instance.lane_capacity_dc_store,
        C.COST_PER_DISTANCE_UNIT, penalty,
        n_periods=instance.n_periods,
        dc_storage_capacity=dc_storage or None, dc_holding_cost=instance.dc_holding_cost or None,
    )
