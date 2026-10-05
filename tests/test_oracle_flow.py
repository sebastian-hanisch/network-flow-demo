"""Unabhängige Orakel für Netzwerksimplex, Praxisregeln und Schattenpreise.

- Netzwerksimplex gegen networkx (`min_cost_flow` auf zufälligen Netzen, auch unzulässige) plus Optimalitätszertifikat
  (Zulässigkeit, reduzierte Kosten je Schrankenstatus) aus den zurückgegebenen Potenzialen.
- Gesamtmodell gegen ein LP, das direkt aus den Parametern (Werke, DCs, Filialen, Perioden) gebaut wird, nicht aus den Kanten
  der Demo (prüft auch Knotensplitting, SRC/SINK-Ausgleich und Zeit-Expansion).
- Praxisregeln gegen eine Neufassung auf Parameterebene (Restkapazität je Werk/DC/Lane).
- Schattenpreise liegen im Subdifferential der Kostenfunktion (Kapazität ± ε, per LP nachgerechnet).
"""

from __future__ import annotations

import random
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest
from scipy.optimize import linprog

import flow_constants as C
import flow_scenario
from flow_evaluation import CAPACITY_KINDS, bottlenecks
from flow_lp_solver import solve_lp
from flow_naive import solve_rule
from flow_network import Arc, distance
from flow_network_simplex import solve_network_simplex

nx = pytest.importorskip("networkx")


def _random_net(rng):
    n = rng.randint(2, 9)
    nodes = [f"n{i}" for i in range(n)]
    arcs = []
    for idx in range(rng.randint(1, 3 * n)):
        a, b = rng.sample(nodes, 2)
        arcs.append(Arc(idx, a, b, float(rng.randint(0, 12)), float(rng.choice([0, 1, 2, 3, 5, 8, 10])), "x"))
    supply = {v: 0.0 for v in nodes}
    for _ in range(rng.randint(0, 4)):
        a, b = rng.sample(nodes, 2)
        q = rng.randint(1, 6)
        supply[a] += q
        supply[b] -= q
    return SimpleNamespace(nodes=nodes, arcs=arcs, supply=supply)


def _networkx_cost(inst):
    g = nx.DiGraph()
    for v in inst.nodes:
        g.add_node(v, demand=-int(inst.supply[v]))
    for a in inst.arcs:  # Zwischenknoten je Kante, damit parallele Kanten erhalten bleiben
        mid = f"__a{a.idx}"
        g.add_node(mid, demand=0)
        g.add_edge(a.tail, mid, weight=int(a.cost), capacity=int(a.capacity))
        g.add_edge(mid, a.head, weight=0, capacity=int(a.capacity))
    try:
        return nx.cost_of_flow(g, nx.min_cost_flow(g))
    except nx.NetworkXUnfeasible:
        return None


def _certificate_violation(inst, r):
    out = {v: 0.0 for v in inst.nodes}
    for a in inst.arcs:
        f = r.flow[a.idx]
        if f < -1e-6 or f > a.capacity + 1e-6:
            return f"Schranke {a.idx}"
        out[a.tail] += f
        out[a.head] -= f
    for v in inst.nodes:
        if abs(out[v] - inst.supply[v]) > 1e-6:
            return f"Bilanz {v}"
    for a in inst.arcs:
        rc = a.cost - r.potentials[a.tail] + r.potentials[a.head]
        f = r.flow[a.idx]
        if a.capacity > 0 and f < 1e-9 and rc < -1e-6:
            return f"reduzierte Kosten unten {a.idx}"
        if a.capacity > 0 and f > a.capacity - 1e-9 and rc > 1e-6:
            return f"reduzierte Kosten oben {a.idx}"
        if 1e-9 < f < a.capacity - 1e-9 and abs(rc) > 1e-6:
            return f"reduzierte Kosten Baum {a.idx}"
    return None


def test_network_simplex_matches_networkx_on_random_nets():
    rng = random.Random(2026)
    feasible = infeasible = 0
    for _ in range(300):
        inst = _random_net(rng)
        ref = _networkx_cost(inst)
        r = solve_network_simplex(inst)
        if ref is None:
            infeasible += 1
            assert not r.feasible
            continue
        feasible += 1
        assert r.feasible
        assert r.cost == pytest.approx(ref, abs=1e-6)
        assert _certificate_violation(inst, r) is None
    assert feasible >= 50 and infeasible >= 50


def _parameter_lp(inst):
    P, D, S, T = inst.plants, inst.dcs, inst.stores, inst.n_periods
    cols, cost, ub = {}, [], []

    def var(key, c, u):
        cols[key] = len(cost)
        cost.append(c)
        ub.append(u)

    for t in range(T):
        for p in P:
            var(("prod", p, t), inst.plant_unit_cost[p], inst.plant_capacity[p])
            for d in D:
                var(("x", p, d, t), C.COST_PER_DISTANCE_UNIT * distance(inst.plant_pos[p], inst.dc_pos[d]), inst.lane_capacity_plant_dc[(p, d)])
        for d in D:
            var(("h", d, t), inst.dc_handling_cost[d], inst.dc_throughput[d])
            for s in S:
                var(("y", d, s, t), C.COST_PER_DISTANCE_UNIT * distance(inst.dc_pos[d], inst.store_pos[s]), inst.lane_capacity_dc_store[(d, s)])
            if t < T - 1:
                var(("inv", d, t), inst.dc_holding_cost[d], inst.dc_storage_capacity[d])
        for s in S:
            var(("short", s, t), inst.shortfall_penalty, inst.store_demand[(s, t)])
    rows, rhs = [], []

    def eq(terms, b):
        row = np.zeros(len(cost))
        for k, c in terms:
            row[cols[k]] += c
        rows.append(row)
        rhs.append(b)

    for t in range(T):
        for p in P:
            eq([(("prod", p, t), 1)] + [(("x", p, d, t), -1) for d in D], 0)
        for d in D:
            eq([(("x", p, d, t), 1) for p in P] + [(("h", d, t), -1)], 0)
            terms = [(("h", d, t), 1)] + [(("y", d, s, t), -1) for s in S]
            if t > 0:
                terms.append((("inv", d, t - 1), 1))
            if t < T - 1:
                terms.append((("inv", d, t), -1))
            eq(terms, 0)
        for s in S:
            eq([(("y", d, s, t), 1) for d in D] + [(("short", s, t), 1)], inst.store_demand[(s, t)])
    res = linprog(cost, A_eq=np.array(rows), b_eq=rhs, bounds=[(0, u) for u in ub], method="highs")
    assert res.status == 0
    return res.fun


def _random_instance(rng):
    t = rng.choice([1, 1, 2, 3, 4])
    return flow_scenario.generate_instance(
        rng.randint(2, 5), rng.randint(2, 4), rng.randint(4, 12), rng.randint(0, 10**6),
        rng.choice([0.2, 0.4, 0.65, 1.0]), rng.choice([0.4, 0.6, 0.82, 1.0]),
        n_periods=t, demand_peak_multiplier=rng.choice([1.0, 1.5, 3.0]) if t > 1 else 1.0,
    )


def test_whole_model_matches_parameter_level_lp():
    rng = random.Random(99)
    for _ in range(25):
        inst = _random_instance(rng)
        r = solve_network_simplex(inst)
        assert r.feasible
        assert r.cost == pytest.approx(_parameter_lp(inst), abs=1e-4)
        assert _certificate_violation(inst, r) is None


def _greedy_cost(inst, order, rule):
    cps = C.COST_PER_DISTANCE_UNIT
    total = 0.0
    for t in range(inst.n_periods):
        plant, dc = dict(inst.plant_capacity), dict(inst.dc_throughput)
        lpd, lds = dict(inst.lane_capacity_plant_dc), dict(inst.lane_capacity_dc_store)
        stores = list(inst.stores)
        if order == "demand_desc":
            stores.sort(key=lambda s: (-inst.store_demand[(s, t)], s))
        for s in stores:
            need = inst.store_demand[(s, t)]

            def route_cost(p, d):
                return (inst.plant_unit_cost[p] + cps * distance(inst.plant_pos[p], inst.dc_pos[d]) + inst.dc_handling_cost[d]
                        + cps * distance(inst.dc_pos[d], inst.store_pos[s]))

            def free(p, d):
                return min(plant[p], lpd[(p, d)], dc[d], lds[(d, s)])

            while need > 1e-9:
                best = None
                dcs = inst.dcs if rule == "cheapest" else None
                groups = [dcs] if rule == "cheapest" else [[d] for d in sorted(inst.dcs, key=lambda d: (distance(inst.dc_pos[d], inst.store_pos[s]), d))]
                for group in groups:
                    bc = None
                    for p in inst.plants:
                        for d in group:
                            if free(p, d) > 1e-9 and (bc is None or route_cost(p, d) < bc - 1e-9):
                                bc, best = route_cost(p, d), (p, d)
                    if best is not None:
                        break
                if best is None:
                    break
                p, d = best
                amt = min(free(p, d), need)
                plant[p] -= amt
                dc[d] -= amt
                lpd[(p, d)] -= amt
                lds[(d, s)] -= amt
                need -= amt
                total += amt * route_cost(p, d)
            total += max(need, 0.0) * inst.shortfall_penalty
    return total


@pytest.mark.parametrize("name, order, rule", [("fcfs", "given", "cheapest"), ("largest_first", "demand_desc", "cheapest"), ("regional", "given", "regional")])
def test_practice_rules_match_parameter_level_reimplementation(name, order, rule):
    rng = random.Random(77)
    for _ in range(25):
        inst = _random_instance(rng)
        flow, cost = solve_rule(inst, name)
        assert cost == pytest.approx(_greedy_cost(inst, order, rule), abs=1e-6)
        assert cost >= solve_network_simplex(inst).cost - 1e-6
        assert not [a for a in inst.arcs if a.kind == "lagerhaltung" and flow[a.idx] > 0]


def test_shadow_prices_lie_in_the_subdifferential_of_the_cost_function():
    rng = random.Random(5)
    eps = 1e-3

    def cost_with(inst, idx, delta):
        arcs = [replace(a, capacity=a.capacity + delta) if a.idx == idx else a for a in inst.arcs]
        return solve_lp(replace(inst, arcs=arcs))[1]

    checked = 0
    for _ in range(8):
        inst = _random_instance(rng)
        r = solve_network_simplex(inst)
        listed = bottlenecks(inst, r, top=50, verify=0)
        for row in listed[:5]:
            right = (r.cost - cost_with(inst, row["arc"], eps)) / eps
            left = (cost_with(inst, row["arc"], -eps) - r.cost) / eps
            assert right - 1e-3 <= row["value"] <= left + 1e-3
            checked += 1
        listed_ids = {x["arc"] for x in listed}
        for a in inst.arcs:  # kein Engpass übersehen
            if a.kind in CAPACITY_KINDS and a.idx not in listed_ids and a.capacity > 0:
                assert (r.cost - cost_with(inst, a.idx, eps)) / eps < 1e-3
    assert checked >= 5
