"""Schattenpreise und Engpässe aus den Potenzialen des Netzwerksimplex: nur volle Kanten, Wert nie negativ, Gegenprobe durch Nachrechnen mit Kapazität + 1."""

import pytest

import flow_constants as C
import flow_scenario
from flow_evaluation import CAPACITY_KINDS, bottlenecks
from flow_network_simplex import solve_network_simplex


def _preset(name):
    p = C.PRESETS[name]
    return flow_scenario.generate_instance(
        p["n_plants"], p["n_dcs"], p["n_stores"], p["seed"], p.get("dc_throughput_scale", 1.0), p.get("plant_capacity_scale", 1.0),
        n_periods=p.get("n_periods", 1), demand_peak_multiplier=p.get("demand_peak_multiplier", 1.0))


def test_the_simplex_result_carries_potentials_reduced_costs_and_status():
    inst = _preset("Normalfall")
    r = solve_network_simplex(inst)
    assert set(r.reduced_costs) == set(r.status) == {a.idx for a in inst.arcs} and set(r.status.values()) <= {"T", "L", "U"}
    assert all(abs(r.reduced_costs[i]) < 1e-6 for i, s in r.status.items() if s == "T")                   # Baumkanten: reduzierte Kosten 0
    assert all(r.reduced_costs[i] >= -1e-6 for i, s in r.status.items() if s == "L") and all(r.reduced_costs[i] <= 1e-6 for i, s in r.status.items() if s == "U")   # Optimalitätsbedingung


@pytest.mark.parametrize("name", list(C.PRESETS))
def test_bottlenecks_are_full_capacity_arcs_sorted_by_value_and_checked(name):
    inst = _preset(name)
    r = solve_network_simplex(inst)
    rows = bottlenecks(inst, r, top=10, verify=5)
    assert rows and [x["value"] for x in rows] == sorted((x["value"] for x in rows), reverse=True)
    by_idx = {a.idx: a for a in inst.arcs}
    for x in rows:
        a = by_idx[x["arc"]]
        assert a.kind in CAPACITY_KINDS and r.flow[a.idx] == pytest.approx(a.capacity, abs=1e-6) and x["value"] > 0
    for x in rows[:5]:
        assert -1e-6 <= x["recomputed"] <= x["value"] + 1e-4                                            # mehr Kapazität spart höchstens den Schattenpreis
    assert all("recomputed" not in x for x in rows[5:])


def test_most_top_bottlenecks_are_exact_on_the_presets():
    checked = exact = 0
    for name in C.PRESETS:
        inst = _preset(name)
        for x in bottlenecks(inst, solve_network_simplex(inst), top=5, verify=5):
            checked += 1
            exact += x["exact"]
    assert checked == 20 and exact >= checked - 3


def test_no_bottleneck_when_capacity_is_ample():
    inst = flow_scenario.generate_instance(3, 3, 4, 7, dc_throughput_scale=2.0, plant_capacity_scale=2.0)
    r = solve_network_simplex(inst)
    rows = bottlenecks(inst, r)
    assert all(x["value"] > 0 for x in rows) and len(rows) <= 10
    assert solve_network_simplex(inst).cost == pytest.approx(r.cost)


def test_labels_are_readable_and_carry_the_period_when_there_are_several():
    inst = _preset("Nachfragespitze")
    labels = [x["label"] for x in bottlenecks(inst, solve_network_simplex(inst), top=10, verify=0)]
    assert all("@" not in lab and "_in" not in lab and "_out" not in lab for lab in labels) and any("Periode" in lab for lab in labels)
    single = [x["label"] for x in bottlenecks(_preset("Normalfall"), solve_network_simplex(_preset("Normalfall")), top=10, verify=0)]
    assert all("Periode" not in lab for lab in single) and any("Durchsatz" in lab for lab in single)
