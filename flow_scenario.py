"""Erzeugt zufällige, aber reproduzierbare Distributionsnetz-Szenarien (Positionen,
Kapazitäten, Kosten, Nachfrage) - Seed-gesteuert wie bei den anderen Demos in diesem
Workspace, damit ein Szenario per Permalink exakt reproduzierbar bleibt."""

import numpy as np

import flow_constants as C
from flow_network import build_instance


def generate_instance(
    n_plants, n_dcs, n_stores, seed,
    dc_throughput_scale=1.0, plant_capacity_scale=1.0,
):
    rng = np.random.default_rng(seed)

    plants = [f"Werk {i + 1}" for i in range(n_plants)]
    dcs = [f"DC {i + 1}" for i in range(n_dcs)]
    stores = [f"Filiale {i + 1}" for i in range(n_stores)]

    def random_positions(names, y_lo, y_hi):
        return {
            name: (
                float(rng.uniform(0, C.MAP_SIZE)),
                float(rng.uniform(y_lo, y_hi)),
            )
            for name in names
        }

    # Werke oben, DCs in der Mitte, Filialen unten - macht das Netzwerkdiagramm
    # sofort lesbar (Fluss von oben nach unten), ohne dass ein Layout-Algorithmus
    # nötig wäre.
    plant_pos = random_positions(plants, 0.8 * C.MAP_SIZE, C.MAP_SIZE)
    dc_pos = random_positions(dcs, 0.35 * C.MAP_SIZE, 0.65 * C.MAP_SIZE)
    store_pos = random_positions(stores, 0.0, 0.2 * C.MAP_SIZE)

    plant_capacity = {
        p: float(round(rng.integers(*C.PLANT_CAPACITY_RANGE) * plant_capacity_scale)) for p in plants
    }
    plant_unit_cost = {p: float(rng.uniform(*C.PLANT_UNIT_COST_RANGE)) for p in plants}

    dc_throughput = {
        dc: float(round(rng.integers(*C.DC_THROUGHPUT_RANGE) * dc_throughput_scale)) for dc in dcs
    }
    dc_handling_cost = {dc: float(rng.uniform(*C.DC_HANDLING_COST_RANGE)) for dc in dcs}

    store_demand = {s: float(rng.integers(*C.STORE_DEMAND_RANGE)) for s in stores}

    lane_capacity_plant_dc = {
        (p, dc): float(rng.integers(*C.LANE_CAPACITY_RANGE)) for p in plants for dc in dcs
    }
    lane_capacity_dc_store = {
        (dc, s): float(rng.integers(*C.LANE_CAPACITY_RANGE)) for dc in dcs for s in stores
    }

    return build_instance(
        plant_pos, dc_pos, store_pos,
        plant_capacity, plant_unit_cost,
        dc_throughput, dc_handling_cost,
        store_demand,
        lane_capacity_plant_dc, lane_capacity_dc_store,
        C.COST_PER_DISTANCE_UNIT, C.SHORTFALL_PENALTY_PER_UNIT,
    )
