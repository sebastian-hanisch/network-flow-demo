import flow_scenario
from flow_naive import solve_naive
from flow_network import build_instance
from flow_network_simplex import solve_network_simplex
from flow_reference_solver import solve_reference

EPS = 1e-6


def _tiny_instance(plant_capacity=100.0, demand=30.0):
    return build_instance(
        plant_pos={"P1": (0, 0)}, dc_pos={"D1": (0, 0)}, store_pos={"S1": (0, 0)},
        plant_capacity={"P1": plant_capacity}, plant_unit_cost={"P1": 5.0},
        dc_throughput={"D1": 100.0}, dc_handling_cost={"D1": 2.0},
        store_demand={"S1": demand},
        lane_capacity_plant_dc={("P1", "D1"): 100.0},
        lane_capacity_dc_store={("D1", "S1"): 100.0},
        cost_per_distance_unit=1.0, shortfall_penalty=500.0,
    )


def _flow_conservation_holds(instance, flow):
    # instance.supply[v] ist als (Abfluss - Zufluss)(v) definiert (siehe
    # flow_network_simplex.py) - die hier akkumulierte balance ist (Zufluss -
    # Abfluss), also das Negative davon.
    balance = {v: 0.0 for v in instance.nodes}
    for a in instance.arcs:
        f = flow.get(a.idx, 0.0)
        balance[a.tail] -= f
        balance[a.head] += f
    for v in instance.nodes:
        expected = -instance.supply.get(v, 0.0)
        if abs(balance[v] - expected) > 1e-4:
            return False
    return True


def _capacities_respected(instance, flow):
    return all(-1e-6 <= flow.get(a.idx, 0.0) <= a.capacity + 1e-6 for a in instance.arcs)


def test_hand_computed_single_route_no_shortfall():
    inst = _tiny_instance(plant_capacity=100.0, demand=30.0)
    result = solve_network_simplex(inst)
    assert result.feasible
    # 30 Einheiten * (5 Produktion + 0 Transport + 2 Umschlag + 0 Transport) = 210
    assert abs(result.cost - 210.0) < 1e-3


def test_hand_computed_forces_shortfall_when_plant_capacity_too_small():
    inst = _tiny_instance(plant_capacity=10.0, demand=30.0)
    result = solve_network_simplex(inst)
    assert result.feasible
    # 10 Einheiten regulär (7 EUR/Einheit) + 20 Einheiten Fehlmenge (500 EUR/Einheit)
    expected = 10 * 7.0 + 20 * 500.0
    assert abs(result.cost - expected) < 1e-3


def test_network_simplex_matches_ortools_on_random_instances():
    for n_plants, n_dcs, n_stores, seed in [
        (2, 2, 4, 1), (3, 3, 8, 7), (4, 3, 10, 42), (5, 4, 12, 99), (2, 3, 6, 2026), (6, 5, 14, 123),
    ]:
        inst = flow_scenario.generate_instance(n_plants, n_dcs, n_stores, seed)
        custom = solve_network_simplex(inst)
        ref_flow, ref_cost, ref_feasible, _ = solve_reference(inst)

        assert custom.feasible, f"Netzwerksimplex nicht feasible bei seed={seed}"
        assert ref_feasible, f"OR-Tools nicht feasible bei seed={seed}"
        assert abs(custom.cost - ref_cost) < 0.5, (
            f"Kostenabweichung bei seed={seed}: {custom.cost} vs {ref_cost}"
        )
        assert _flow_conservation_holds(inst, custom.flow)
        assert _capacities_respected(inst, custom.flow)


def test_network_simplex_matches_ortools_under_dc_bottleneck():
    inst = flow_scenario.generate_instance(3, 2, 10, seed=11, dc_throughput_scale=0.4)
    custom = solve_network_simplex(inst)
    ref_flow, ref_cost, ref_feasible, _ = solve_reference(inst)
    assert custom.feasible and ref_feasible
    assert abs(custom.cost - ref_cost) < 0.5
    # Ein harter DC-Engpass sollte hier tatsächlich Fehlmenge erzwingen.
    shortfall = sum(custom.flow.get(a.idx, 0.0) for a in inst.arcs if a.kind == "fehlmenge")
    assert shortfall > 0


def test_naive_heuristic_produces_valid_flow_and_is_never_cheaper_than_optimum():
    for n_plants, n_dcs, n_stores, seed in [(3, 3, 8, 7), (3, 2, 10, 11), (4, 3, 10, 42)]:
        inst = flow_scenario.generate_instance(n_plants, n_dcs, n_stores, seed)
        naive_flow, naive_cost = solve_naive(inst)
        optimal = solve_network_simplex(inst)

        assert _flow_conservation_holds(inst, naive_flow)
        assert _capacities_respected(inst, naive_flow)
        assert naive_cost >= optimal.cost - 1e-6


def test_iteration_count_is_bounded_for_demo_sized_networks():
    inst = flow_scenario.generate_instance(6, 5, 14, seed=123)
    result = solve_network_simplex(inst)
    assert result.feasible
    assert result.iterations < 2000
