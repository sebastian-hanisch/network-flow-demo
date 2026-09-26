"""Zusätzliche Verfahren: Praxisregeln (Größte Nachfrage zuerst, Regional) und der HiGHS-LP als dritter exakter Löser."""

import pytest

import flow_constants as C
import flow_scenario
from flow_evaluation import method_rows, shortfall_total
from flow_lp_solver import solve_lp
from flow_naive import RULE_LABELS, RULES, solve_naive, solve_rule
from flow_network import build_instance
from flow_network_simplex import solve_network_simplex
from flow_reference_solver import solve_reference


def _preset_instance(name):
    p = C.PRESETS[name]
    return flow_scenario.generate_instance(
        p["n_plants"], p["n_dcs"], p["n_stores"], p["seed"], p.get("dc_throughput_scale", 1.0), p.get("plant_capacity_scale", 1.0),
        n_periods=p.get("n_periods", 1), demand_peak_multiplier=p.get("demand_peak_multiplier", 1.0),
    )


def _valid(instance, flow):
    balance = {v: 0.0 for v in instance.nodes}
    for a in instance.arcs:
        f = flow.get(a.idx, 0.0)
        assert -1e-6 <= f <= a.capacity + 1e-6
        balance[a.tail] -= f
        balance[a.head] += f
    return all(abs(balance[v] + instance.supply.get(v, 0.0)) < 1e-4 for v in instance.nodes)


def test_default_rule_is_the_unchanged_fcfs_baseline():
    inst = _preset_instance("Normalfall")
    assert solve_naive(inst) == solve_rule(inst, "fcfs") == solve_naive(inst, order="given", rule="cheapest")
    assert set(RULES) == set(RULE_LABELS) == {"fcfs", "largest_first", "regional"}


@pytest.mark.parametrize("name", list(C.PRESETS))
@pytest.mark.parametrize("rule", list(RULES))
def test_every_rule_is_feasible_and_never_beats_the_optimum(name, rule):
    inst = _preset_instance(name)
    flow, cost = solve_rule(inst, rule)
    assert _valid(inst, flow) and cost == pytest.approx(sum(a.cost * flow[a.idx] for a in inst.arcs))
    assert cost >= solve_network_simplex(inst).cost - 1e-6


def test_the_rules_are_deterministic():
    inst = _preset_instance("DC-Engpass")
    for rule in RULES:
        assert solve_rule(inst, rule) == solve_rule(inst, rule)


def _two_dcs(near_cost, far_cost):
    """Ein Werk, zwei DCs (D1 nah an der Filiale, D2 weit weg), Kapazitäten reichen überall: die billigste Route über D1 oder D2 hängt an den Umschlagkosten."""
    return build_instance(
        plant_pos={"P1": (0, 0)}, dc_pos={"D1": (0, 90), "D2": (0, 10)}, store_pos={"S1": (0, 100)},
        plant_capacity={"P1": 100.0}, plant_unit_cost={"P1": 5.0},
        dc_throughput={"D1": 100.0, "D2": 100.0}, dc_handling_cost={"D1": near_cost, "D2": far_cost},
        store_demand={"S1": 30.0},
        lane_capacity_plant_dc={("P1", "D1"): 100.0, ("P1", "D2"): 100.0},
        lane_capacity_dc_store={("D1", "S1"): 100.0, ("D2", "S1"): 100.0},
        cost_per_distance_unit=1.0, shortfall_penalty=500.0,
    )


def test_regional_takes_the_nearest_dc_even_when_it_is_not_cheapest():
    """D1 liegt 10 von der Filiale entfernt, D2 90: die Regel wählt D1 - auch wenn dessen Umschlag so teuer ist, dass die Route über D2 billiger wäre. Die billigste Route je Filiale nimmt dann D2."""
    inst = _two_dcs(near_cost=200.0, far_cost=1.0)
    flow_reg, cost_reg = solve_rule(inst, "regional")
    flow_fcfs, cost_fcfs = solve_rule(inst, "fcfs")
    umschlag = {a.tail: a.idx for a in inst.arcs if a.kind == "umschlag"}
    assert flow_reg[umschlag["D1_in"]] == 30.0 and flow_reg[umschlag["D2_in"]] == 0.0
    assert flow_fcfs[umschlag["D2_in"]] == 30.0 and cost_fcfs < cost_reg
    assert cost_fcfs == pytest.approx(solve_network_simplex(inst).cost)


def test_largest_first_serves_the_biggest_store_first():
    """Zwei Filialen an einem knappen Werk (Kapazität 40): die Filiale mit der größeren Nachfrage (30) wird zuerst bedient, die kleinere (20) bekommt den Rest (10) und braucht die Notbeschaffung."""
    inst = build_instance(
        plant_pos={"P1": (0, 0)}, dc_pos={"D1": (0, 0)}, store_pos={"S1": (0, 0), "S2": (0, 0)},
        plant_capacity={"P1": 40.0}, plant_unit_cost={"P1": 5.0},
        dc_throughput={"D1": 100.0}, dc_handling_cost={"D1": 1.0},
        store_demand={"S1": 20.0, "S2": 30.0},
        lane_capacity_plant_dc={("P1", "D1"): 100.0}, lane_capacity_dc_store={("D1", "S1"): 100.0, ("D1", "S2"): 100.0},
        cost_per_distance_unit=1.0, shortfall_penalty=500.0,
    )
    given, _ = solve_rule(inst, "fcfs")
    largest, _ = solve_rule(inst, "largest_first")
    short = {a.tail: a.idx for a in inst.arcs if a.kind == "fehlmenge"}
    short_arc = {a.head: a.idx for a in inst.arcs if a.kind == "fehlmenge"}
    assert given[short_arc["S2"]] == 10.0 and given[short_arc["S1"]] == 0.0             # S1 zuerst: S2 bleibt 10 schuldig
    assert largest[short_arc["S1"]] == 10.0 and largest[short_arc["S2"]] == 0.0         # S2 zuerst: S1 bleibt 10 schuldig
    assert shortfall_total(inst, given) == shortfall_total(inst, largest) == 10.0


@pytest.mark.parametrize("name", list(C.PRESETS))
def test_highs_lp_matches_the_network_simplex_and_or_tools(name):
    inst = _preset_instance(name)
    flow, cost, feasible = solve_lp(inst)
    assert feasible and _valid(inst, flow)
    assert cost == pytest.approx(solve_network_simplex(inst).cost, abs=1e-3) and cost == pytest.approx(solve_reference(inst)[1], abs=0.05)     # OR-Tools rechnet mit auf 1e-4 gerundeten Kosten


def test_highs_lp_on_random_instances_and_a_hand_instance():
    for seed in range(20):
        inst = flow_scenario.generate_instance(3, 3, 8, seed)
        assert solve_lp(inst)[1] == pytest.approx(solve_network_simplex(inst).cost, abs=1e-3)
    tiny = build_instance(
        plant_pos={"P1": (0, 0)}, dc_pos={"D1": (0, 0)}, store_pos={"S1": (0, 0)}, plant_capacity={"P1": 100.0}, plant_unit_cost={"P1": 5.0},
        dc_throughput={"D1": 100.0}, dc_handling_cost={"D1": 2.0}, store_demand={"S1": 30.0}, lane_capacity_plant_dc={("P1", "D1"): 100.0},
        lane_capacity_dc_store={("D1", "S1"): 100.0}, cost_per_distance_unit=1.0, shortfall_penalty=500.0)
    assert solve_lp(tiny)[1] == pytest.approx(210.0)


def test_method_rows_sort_by_cost_and_measure_the_gap_to_the_best_exact_solver():
    inst = _preset_instance("Normalfall")
    results = {"Unoptimiert (FCFS je Filiale)": dict(zip(("flow", "cost"), solve_naive(inst)), runtime=0.001)}
    ns = solve_network_simplex(inst)
    results["Netzwerksimplex (eigene Implementierung)"] = dict(flow=ns.flow, cost=ns.cost, runtime=0.01)
    extra = {RULE_LABELS["regional"]: dict(zip(("flow", "cost"), solve_rule(inst, "regional")), runtime=0.001, kind="Praxisregel")}
    rows = method_rows(inst, results, extra)
    assert [r["Gesamtkosten (€)"] for r in rows] == sorted(r["Gesamtkosten (€)"] for r in rows)
    exact = [r for r in rows if r["Art"] == "exakt"]
    assert len(exact) == 1 and exact[0]["Abstand zum Optimum (%)"] == 0.0 and all(r["Abstand zum Optimum (%)"] > 0 for r in rows if r["Art"] == "Praxisregel")
