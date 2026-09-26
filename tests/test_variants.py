"""Szenario-Varianten: jede Änderung ändert genau das Gewählte, die Ausgangslage bleibt unberührt, die Kosten reagieren in die erwartete Richtung."""

import pytest

import flow_constants as C
import flow_scenario
from flow_evaluation import scenario_row
from flow_network_simplex import solve_network_simplex
from flow_variants import CHANGE_PCT, CHANGES, NEEDS_TARGET, describe, make_variant


def _base():
    p = C.PRESETS["Normalfall"]
    return flow_scenario.generate_instance(p["n_plants"], p["n_dcs"], p["n_stores"], p["seed"])


def _arcs_by(instance, kind):
    return {(a.tail, a.head): a for a in instance.arcs if a.kind == kind}


def test_no_change_reproduces_the_instance_and_the_original_is_untouched():
    inst = _base()
    caps = {a.idx: a.capacity for a in inst.arcs}
    same = make_variant(inst, "penalty", pct=0)
    assert [(a.tail, a.head, a.cost, a.capacity, a.kind) for a in same.arcs] == [(a.tail, a.head, a.cost, a.capacity, a.kind) for a in inst.arcs]
    make_variant(inst, "dc_expand", inst.dcs[0], 100)
    make_variant(inst, "plant_close", inst.plants[0])
    assert {a.idx: a.capacity for a in inst.arcs} == caps


def test_dc_expansion_changes_only_that_dc_and_never_costs_more():
    inst = _base()
    v = make_variant(inst, "dc_expand", "DC 1", 50)
    old, new = _arcs_by(inst, "umschlag"), _arcs_by(v, "umschlag")
    for key in old:
        assert new[key].capacity == (round(old[key].capacity * 1.5) if key[0] == "DC 1_in" else old[key].capacity)
    assert solve_network_simplex(v).cost <= solve_network_simplex(inst).cost + 1e-6


def test_closing_a_plant_zeroes_its_capacity_and_does_not_help():
    inst = _base()
    v = make_variant(inst, "plant_close", "Werk 1")
    assert _arcs_by(v, "produktion")[("SRC", "Werk 1")].capacity == 0.0 and _arcs_by(v, "produktion")[("SRC", "Werk 2")].capacity == _arcs_by(inst, "produktion")[("SRC", "Werk 2")].capacity
    assert solve_network_simplex(v).cost >= solve_network_simplex(inst).cost - 1e-6


def test_demand_and_plant_capacity_scale_everything():
    inst = _base()
    up = make_variant(inst, "demand", pct=20)
    assert all(up.store_demand[k] == round(inst.store_demand[k] * 1.2) for k in inst.store_demand)
    assert solve_network_simplex(up).cost >= solve_network_simplex(inst).cost
    low = make_variant(inst, "plant_capacity", pct=-20)
    assert all(low.plant_capacity[p] == round(inst.plant_capacity[p] * 0.8) for p in inst.plants)
    assert solve_network_simplex(low).cost >= solve_network_simplex(inst).cost - 1e-6


def test_a_dearer_penalty_raises_the_cost_by_exactly_the_shortfall_times_the_increase():
    """Die Fehlmenge bleibt gleich (dieselben Engpässe), jede Einheit kostet 500 mehr: bei 100 % genau Fehlmenge mal 500."""
    inst = _base()
    a = solve_network_simplex(inst)
    v = make_variant(inst, "penalty", pct=100)
    b = solve_network_simplex(v)
    short = scenario_row(inst, a.cost, a.flow)["shortfall"]
    assert short > 0 and b.cost - a.cost == pytest.approx(short * C.SHORTFALL_PENALTY_PER_UNIT, abs=1e-3)


def test_multi_period_instances_are_supported():
    p = C.PRESETS["Nachfragespitze"]
    inst = flow_scenario.generate_instance(p["n_plants"], p["n_dcs"], p["n_stores"], p["seed"], n_periods=p["n_periods"], demand_peak_multiplier=p["demand_peak_multiplier"])
    v = make_variant(inst, "dc_expand", "DC 1", 50)
    assert v.n_periods == 4 and solve_network_simplex(v).cost < solve_network_simplex(inst).cost
    assert all(v.dc_storage_capacity[d] == (round(inst.dc_storage_capacity[d] * 1.5) if d == "DC 1" else inst.dc_storage_capacity[d]) for d in inst.dcs)


def test_change_tables_are_consistent():
    assert set(CHANGES) == set(CHANGE_PCT) and set(NEEDS_TARGET) <= set(CHANGES)
    for change, spec in CHANGE_PCT.items():
        if spec is not None:
            lo, hi, default = spec
            assert lo < hi and lo <= default <= hi
    assert describe("dc_expand", "DC 1", 50) == "DC 1 um 50 % ausbauen" and describe("plant_close", "Werk 2") == "Werk 2 schließen"
    assert describe("plant_capacity", None, -20) == "Werkskapazität -20 %" and describe("demand", None, 20) == "Nachfrage +20 %" and describe("penalty", None, 100) == "Notbeschaffung 100 % teurer"
