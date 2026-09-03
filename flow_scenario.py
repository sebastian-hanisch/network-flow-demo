"""Erzeugt zufällige, aber reproduzierbare Distributionsnetz-Szenarien (Positionen,
Kapazitäten, Kosten, Nachfrage) - Seed-gesteuert wie bei den anderen Demos in diesem
Workspace, damit ein Szenario per Permalink exakt reproduzierbar bleibt."""

import numpy as np

import flow_constants as C
from flow_network import build_instance


def seasonality_curve(n_periods, peak_multiplier):
    """Glockenförmiger Nachfrage-Verlauf über die Perioden, mit Spitze in der
    mittleren Periode. peak_multiplier=1.0 (oder n_periods<=1) ergibt eine flache
    Kurve (keine Saisonalität) - das reduziert den Mehrperioden-Fall auf T
    strukturell unabhängige Ein-Perioden-Probleme, weil sich Lagerhaltung ohne
    Nachfrageschwankung nie lohnt (Lagerhaltungskosten sind nie negativ)."""
    if n_periods <= 1 or peak_multiplier <= 1.0:
        return [1.0] * n_periods
    peak = (n_periods - 1) / 2.0
    half_width = max(peak, (n_periods - 1) - peak, 1e-9)
    curve = []
    for t in range(n_periods):
        dist = abs(t - peak) / half_width
        bump = max(0.0, 1.0 - dist ** 2)
        curve.append(1.0 + (peak_multiplier - 1.0) * bump)
    return curve


def generate_instance(
    n_plants, n_dcs, n_stores, seed,
    dc_throughput_scale=1.0, plant_capacity_scale=1.0,
    n_periods=1, demand_peak_multiplier=1.0,
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
    dc_holding_cost = {dc: float(rng.uniform(*C.DC_HOLDING_COST_RANGE)) for dc in dcs}
    dc_storage_capacity = {
        dc: dc_throughput[dc] * C.DC_STORAGE_CAPACITY_THROUGHPUT_MULTIPLIER for dc in dcs
    }

    base_demand = {s: float(rng.integers(*C.STORE_DEMAND_RANGE)) for s in stores}
    curve = seasonality_curve(n_periods, demand_peak_multiplier)
    store_demand = {(s, t): round(base_demand[s] * curve[t]) for s in stores for t in range(n_periods)}

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
        n_periods=n_periods,
        dc_storage_capacity=dc_storage_capacity, dc_holding_cost=dc_holding_cost,
    )
