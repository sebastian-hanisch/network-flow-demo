import flow_scenario
from flow_network import build_instance, dc_in, dc_out, node_name


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


def test_single_period_node_names_have_no_time_suffix():
    # n_periods=1 ist der Default und muss exakt die alte Ein-Perioden-Benennung
    # reproduzieren (kein "@t0"-Suffix) - Regressionsschutz für die
    # Mehrperioden-Erweiterung.
    inst = _tiny_instance()
    assert "P1" in inst.nodes
    assert dc_in("D1") == "D1_in"
    assert node_name("P1", 0, 1) == "P1"
    assert not any("@t" in n for n in inst.nodes)
    assert not any(a.kind == "lagerhaltung" for a in inst.arcs)


def test_multi_period_creates_time_suffixed_nodes_and_carryover_arcs():
    inst = build_instance(
        plant_pos={"P1": (0, 0)}, dc_pos={"D1": (0, 0)}, store_pos={"S1": (0, 0)},
        plant_capacity={"P1": 100.0}, plant_unit_cost={"P1": 5.0},
        dc_throughput={"D1": 100.0}, dc_handling_cost={"D1": 2.0},
        store_demand={("S1", 0): 20.0, ("S1", 1): 20.0, ("S1", 2): 20.0},
        lane_capacity_plant_dc={("P1", "D1"): 100.0},
        lane_capacity_dc_store={("D1", "S1"): 100.0},
        cost_per_distance_unit=1.0, shortfall_penalty=500.0,
        n_periods=3, dc_storage_capacity={"D1": 50.0}, dc_holding_cost={"D1": 1.0},
    )
    assert node_name("P1", 1, 3) == "P1@t1"
    assert dc_in("D1", 2, 3) == "D1_in@t2"
    assert "P1@t0" in inst.nodes and "P1@t2" in inst.nodes
    assert abs(sum(inst.supply.values())) < 1e-9
    assert inst.total_demand == 60.0

    carryover = [a for a in inst.arcs if a.kind == "lagerhaltung"]
    assert len(carryover) == 2  # t0->t1, t1->t2, ein DC
    assert {a.tail for a in carryover} == {"D1_out@t0", "D1_out@t1"}
    assert all(a.capacity == 50.0 and a.cost == 1.0 for a in carryover)


def test_multi_period_random_scenario_is_balanced():
    inst = flow_scenario.generate_instance(3, 3, 8, seed=7, n_periods=4, demand_peak_multiplier=1.8)
    assert abs(sum(inst.supply.values())) < 1e-6
    assert inst.n_periods == 4
    assert len([a for a in inst.arcs if a.kind == "lagerhaltung"]) == 3 * len(inst.dcs)
