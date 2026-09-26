"""Jede Zahl, die README und Beschriftungen zu den neuen Abschnitten nennen (mehr Verfahren, Szenario-Vergleich, Schattenpreise), ist hier belegt (die vier Beispielszenarien, Normalfall = Seed 7)."""

import pytest

import flow_constants as C
import flow_scenario
from flow_evaluation import bottlenecks, scenario_row
from flow_lp_solver import solve_lp
from flow_naive import solve_rule
from flow_network_simplex import solve_network_simplex
from flow_variants import make_variant


def _preset(name):
    p = C.PRESETS[name]
    return flow_scenario.generate_instance(
        p["n_plants"], p["n_dcs"], p["n_stores"], p["seed"], p.get("dc_throughput_scale", 1.0), p.get("plant_capacity_scale", 1.0),
        n_periods=p.get("n_periods", 1), demand_peak_multiplier=p.get("demand_peak_multiplier", 1.0))


EXPECTED = {   # optimale Kosten, Abstand der Regeln in % (FCFS / größte zuerst / regional), Fehlmenge im Optimum
    "Normalfall": (43852.00, (3.95, 4.13, 2.59), 39),
    "DC-Engpass": (68042.67, (10.13, 8.34, 9.24), 100),
    "Knappe Werkskapazität": (31876.84, (28.07, 28.80, 26.15), 5),
    "Nachfragespitze": (197480.98, (10.37, 13.16, 13.15), 109),
}


@pytest.mark.parametrize("name", list(EXPECTED))
def test_rules_against_the_optimum(name):
    """Kosten des Optimums und Mehrkosten der drei Praxisregeln; alle drei exakten Löser stimmen überein."""
    inst = _preset(name)
    opt, gaps, short = EXPECTED[name]
    r = solve_network_simplex(inst)
    assert r.cost == pytest.approx(opt, abs=0.01) and solve_lp(inst)[1] == pytest.approx(opt, abs=0.01) and scenario_row(inst, r.cost, r.flow)["shortfall"] == short
    got = tuple((solve_rule(inst, k)[1] - opt) / opt * 100 for k in ("fcfs", "largest_first", "regional"))
    assert got == pytest.approx(gaps, abs=0.01)


def test_no_rule_wins_everywhere():
    """In den vier Beispielszenarien gewinnt dreimal eine andere Praxisregel: Regional (Normalfall, Knappe Werkskapazität), Größte Nachfrage zuerst (DC-Engpass), FCFS (Nachfragespitze); alle liegen 2,6 bis 28,8 % über dem Optimum."""
    winners = {}
    for name in EXPECTED:
        inst = _preset(name)
        costs = {k: solve_rule(inst, k)[1] for k in ("fcfs", "largest_first", "regional")}
        winners[name] = min(costs, key=costs.get)
        assert min(costs.values()) > EXPECTED[name][0]
    assert winners == {"Normalfall": "regional", "DC-Engpass": "largest_first", "Knappe Werkskapazität": "regional", "Nachfragespitze": "fcfs"}
    gaps = [g for _o, gs, _s in EXPECTED.values() for g in gs]
    assert min(gaps) == 2.59 and max(gaps) == 28.80


def test_scenarios_of_the_normal_case():
    """Normalfall (43 852 €, 39 Einheiten Fehlmenge): DC 1 um 50 % ausbauen spart 12 570 € (-28,7 %) und beseitigt die Fehlmenge; Werk 1 schließen +2 648 € (+6,0 %, Fehlmenge 46); Werkskapazität -20 % nur +114 € (+0,3 %);
    Nachfrage +20 % +25 049 € (+57,1 %, Fehlmenge 90); Notbeschaffung 100 % teurer +19 500 € (= 39 mal 500, Fehlmenge unverändert)."""
    inst = _preset("Normalfall")
    r = solve_network_simplex(inst)
    base_short = scenario_row(inst, r.cost, r.flow)["shortfall"]
    got = {}
    for change, target, pct in (("dc_expand", "DC 1", 50), ("plant_close", "Werk 1", 0), ("plant_capacity", None, -20), ("demand", None, 20), ("penalty", None, 100)):
        v = make_variant(inst, change, target, pct)
        rv = solve_network_simplex(v)
        got[change] = (rv.cost - r.cost, (rv.cost - r.cost) / r.cost * 100, scenario_row(v, rv.cost, rv.flow)["shortfall"])
    assert base_short == 39
    assert got["dc_expand"][0] == pytest.approx(-12569.52, abs=0.05) and got["dc_expand"][1] == pytest.approx(-28.7, abs=0.05) and got["dc_expand"][2] == 0
    assert got["plant_close"][0] == pytest.approx(2648.16, abs=0.05) and got["plant_close"][1] == pytest.approx(6.0, abs=0.05) and got["plant_close"][2] == 46
    assert got["plant_capacity"][0] == pytest.approx(113.79, abs=0.05) and got["plant_capacity"][1] == pytest.approx(0.3, abs=0.05) and got["plant_capacity"][2] == 39
    assert got["demand"][0] == pytest.approx(25048.57, abs=0.05) and got["demand"][1] == pytest.approx(57.1, abs=0.05) and got["demand"][2] == 90
    assert got["penalty"][0] == pytest.approx(19500.0, abs=0.01) and got["penalty"][2] == 39


def test_shadow_prices_of_the_normal_case():
    """Die drei größten Schattenpreise sind Durchsatz-Engpässe: DC 2 393,93 €, DC 3 380,00 €, DC 1 329,15 € je Einheit; danach Werk 3 → DC 1 mit 35,81 €. Alle fünf größten stimmen mit dem Nachrechnen (Kapazität + 1) überein.
    Der DC-1-Ausbau um 51 Einheiten (101 auf 152) spart 12 570 €, das sind 246 € je Einheit - weniger als der Schattenpreis 329 €: der Wert gilt nur für die ersten Einheiten."""
    inst = _preset("Normalfall")
    r = solve_network_simplex(inst)
    rows = bottlenecks(inst, r, top=5, verify=5)
    assert [(x["label"], round(x["value"], 2)) for x in rows] == [("DC 2 (Durchsatz)", 393.93), ("DC 3 (Durchsatz)", 380.0), ("DC 1 (Durchsatz)", 329.15), ("Werk 3 → DC 1", 35.81), ("Werk 2 → DC 2", 19.3)]
    assert all(x["exact"] for x in rows)
    assert inst.dc_throughput["DC 1"] == 101.0 and make_variant(inst, "dc_expand", "DC 1", 50).dc_throughput["DC 1"] == 152.0
    assert 12569.52 / 51 == pytest.approx(246.4, abs=0.1) and 246.4 < 329.15


def test_shadow_prices_of_the_other_scenarios():
    """DC-Engpass: DC 3 389,22 € und DC 2 388,40 €, DC 1 351,28 € (beim Nachrechnen nur 345,43 €: die Basis wechselt). Knappe Werkskapazität: die Werke 343,24 / 340,29 / 316,82 €. Nachfragespitze: DC 1 in Periode 3 mit 367,38 €.
    Über die 20 Engpässe der vier Szenarien (je fünf geprüft) stimmen 19 genau."""
    checked = exact = 0
    out = {}
    for name in EXPECTED:
        inst = _preset(name)
        rows = bottlenecks(inst, solve_network_simplex(inst), top=5, verify=5)
        out[name] = [(x["label"], round(x["value"], 2), round(x["recomputed"], 2)) for x in rows]
        checked += len(rows)
        exact += sum(1 for x in rows if x["exact"])
    assert out["DC-Engpass"][:3] == [("DC 3 (Durchsatz)", 389.22, 389.22), ("DC 2 (Durchsatz)", 388.4, 388.4), ("DC 1 (Durchsatz)", 351.28, 345.43)]
    assert [x[:2] for x in out["Knappe Werkskapazität"][:3]] == [("Werk 1 (Produktion)", 343.24), ("Werk 3 (Produktion)", 340.29), ("Werk 2 (Produktion)", 316.82)]
    assert out["Nachfragespitze"][0][:2] == ("DC 1 (Durchsatz) (Periode 3)", 367.38)
    assert (checked, exact) == (20, 19)


def test_shadow_price_is_bounded_by_the_penalty():
    """Ein Schattenpreis kann nie über den Strafkosten der Notbeschaffung liegen (mehr Kapazität ersetzt höchstens eine Einheit Fehlmenge): alle Werte in den vier Szenarien liegen unter 500 €."""
    for name in EXPECTED:
        inst = _preset(name)
        assert all(x["value"] <= C.SHORTFALL_PENALTY_PER_UNIT + 1e-6 for x in bottlenecks(inst, solve_network_simplex(inst), top=50, verify=0))
