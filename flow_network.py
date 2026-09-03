"""Baut das Distributionsnetzwerk als reines Min-Cost-Flow-Problem auf: Werke ->
Verteilzentren -> Filialen, plus zwei Hilfsknoten SRC/SINK, die das Netz immer
ausgeglichen (balanciert) und lösbar machen - unabhängig davon, wie eng die
Regler für Werks- oder DC-Kapazität gestellt sind.

Modellierungs-Kniffe, die hier zum Einsatz kommen:

1. Knotenkapazität als Kantenkapazität: Ein Verteilzentrum DC_j hat eine
   Durchsatzgrenze (wie viele Einheiten insgesamt durch das Lager dürfen), aber
   ein Min-Cost-Flow-Modell kennt nur Kantenkapazitäten. Kunstgriff: jedes DC wird
   in zwei Knoten gesplittet (DC_j_in, DC_j_out), verbunden durch eine einzige
   interne Kante mit Kapazität = Durchsatzgrenze. Aller Zufluss zum DC läuft über
   DC_j_in, aller Abfluss über DC_j_out - die interne Kante limitiert damit exakt
   den Gesamtdurchsatz.

2. SRC/SINK als Ausgleichsknoten: Werkskapazität und Filialnachfrage stimmen in
   Summe fast nie exakt überein, ein Min-Cost-Flow-Knoten-Ausgleich (Summe aller
   Angebote = Summe aller Nachfragen) ist aber Voraussetzung für den
   Netzwerksimplex. SRC speist daher sowohl die Werke (SRC -> Werk, Kosten =
   Produktionskosten, Kapazität = Werkskapazität) als auch - als teure
   Notbeschaffung - jede Filiale direkt (SRC -> Filiale, Kosten =
   Fehlmengen-Strafkosten, Kapazität = exakt die Nachfrage dieser Filiale). Jede
   Filiale wiederum hat eine Kante Filiale -> SINK mit Kapazität = exakt ihre
   Nachfrage. Da die Summe aller Filial-Kapazitäten gleich SRCs Gesamtangebot
   ist, MUSS im Optimum jede Filiale exakt ihre Nachfrage erhalten - ob über
   Werk/DC-Routen oder (teuer) direkt von SRC, entscheidet die Optimierung.
   Damit ist das Netz immer lösbar, auch bei einem harten DC-Engpass, und die
   Fehlmengen-Kante macht sichtbar, wie viel Nachfrage nicht wirtschaftlich
   bedient werden kann.
"""

import math
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Arc:
    idx: int
    tail: str
    head: str
    cost: float
    capacity: float
    kind: str  # "produktion" | "umschlag" | "transport_werk_dc" | "transport_dc_filiale" | "nachfrage" | "fehlmenge"


@dataclass
class ProblemInstance:
    nodes: list
    supply: dict  # b(v); != 0 nur für SRC/SINK
    arcs: list
    plants: list
    dcs: list
    stores: list
    plant_pos: dict
    dc_pos: dict
    store_pos: dict
    plant_capacity: dict
    plant_unit_cost: dict
    dc_throughput: dict
    dc_handling_cost: dict
    store_demand: dict
    lane_capacity_plant_dc: dict  # (plant, dc) -> Kapazität
    lane_capacity_dc_store: dict  # (dc, store) -> Kapazität
    shortfall_penalty: float
    total_demand: float = field(init=False)

    def __post_init__(self):
        self.total_demand = float(sum(self.store_demand.values()))


def dc_in(dc_id):
    return f"{dc_id}_in"


def dc_out(dc_id):
    return f"{dc_id}_out"


def distance(pos_a, pos_b):
    return math.hypot(pos_a[0] - pos_b[0], pos_a[1] - pos_b[1])


def build_instance(
    plant_pos, dc_pos, store_pos,
    plant_capacity, plant_unit_cost,
    dc_throughput, dc_handling_cost,
    store_demand,
    lane_capacity_plant_dc, lane_capacity_dc_store,
    cost_per_distance_unit, shortfall_penalty,
):
    """Baut die ProblemInstance aus bereits festgelegten Parametern (siehe
    flow_scenario.py für die Zufallsgenerierung dieser Parameter)."""
    plants = list(plant_pos.keys())
    dcs = list(dc_pos.keys())
    stores = list(store_pos.keys())

    nodes = ["SRC", "SINK"] + plants + [n for dc in dcs for n in (dc_in(dc), dc_out(dc))] + stores
    total_demand = float(sum(store_demand.values()))
    supply = {n: 0.0 for n in nodes}
    supply["SRC"] = total_demand
    supply["SINK"] = -total_demand

    arcs = []
    idx = 0

    def add_arc(tail, head, cost, capacity, kind):
        nonlocal idx
        arcs.append(Arc(idx, tail, head, float(cost), float(capacity), kind))
        idx += 1

    for p in plants:
        add_arc("SRC", p, plant_unit_cost[p], plant_capacity[p], "produktion")

    for dc in dcs:
        add_arc(dc_in(dc), dc_out(dc), dc_handling_cost[dc], dc_throughput[dc], "umschlag")

    for p in plants:
        for dc in dcs:
            cap = lane_capacity_plant_dc[(p, dc)]
            cost = cost_per_distance_unit * distance(plant_pos[p], dc_pos[dc])
            add_arc(p, dc_in(dc), cost, cap, "transport_werk_dc")

    for dc in dcs:
        for s in stores:
            cap = lane_capacity_dc_store[(dc, s)]
            cost = cost_per_distance_unit * distance(dc_pos[dc], store_pos[s])
            add_arc(dc_out(dc), s, cost, cap, "transport_dc_filiale")

    for s in stores:
        demand = store_demand[s]
        add_arc(s, "SINK", 0.0, demand, "nachfrage")
        add_arc("SRC", s, shortfall_penalty, demand, "fehlmenge")

    return ProblemInstance(
        nodes=nodes, supply=supply, arcs=arcs,
        plants=plants, dcs=dcs, stores=stores,
        plant_pos=plant_pos, dc_pos=dc_pos, store_pos=store_pos,
        plant_capacity=plant_capacity, plant_unit_cost=plant_unit_cost,
        dc_throughput=dc_throughput, dc_handling_cost=dc_handling_cost,
        store_demand=store_demand,
        lane_capacity_plant_dc=lane_capacity_plant_dc,
        lane_capacity_dc_store=lane_capacity_dc_store,
        shortfall_penalty=shortfall_penalty,
    )
