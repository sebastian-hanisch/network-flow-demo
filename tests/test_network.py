import flow_scenario
from flow_network import build_instance, dc_in, dc_out


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


def test_supply_balances_to_zero():
    inst = _tiny_instance()
    assert abs(sum(inst.supply.values())) < 1e-9


def test_dc_split_creates_internal_capacity_arc():
    inst = _tiny_instance()
    internal = [a for a in inst.arcs if a.kind == "umschlag"]
    assert len(internal) == 1
    assert internal[0].tail == dc_in("D1")
    assert internal[0].head == dc_out("D1")
    assert internal[0].capacity == 100.0


def test_store_demand_arc_capacity_equals_demand():
    inst = _tiny_instance(demand=42.0)
    arc = next(a for a in inst.arcs if a.kind == "nachfrage")
    assert arc.capacity == 42.0
    assert inst.total_demand == 42.0


def test_shortfall_arc_capacity_equals_demand_and_uses_penalty():
    inst = _tiny_instance(demand=42.0)
    arc = next(a for a in inst.arcs if a.kind == "fehlmenge")
    assert arc.capacity == 42.0
    assert arc.cost == 500.0


def test_random_scenario_is_balanced_for_various_sizes():
    for n_plants, n_dcs, n_stores, seed in [(2, 2, 4, 1), (5, 4, 12, 99), (3, 2, 6, 2026)]:
        inst = flow_scenario.generate_instance(n_plants, n_dcs, n_stores, seed)
        assert abs(sum(inst.supply.values())) < 1e-6
        assert len(inst.plants) == n_plants
        assert len(inst.dcs) == n_dcs
        assert len(inst.stores) == n_stores
