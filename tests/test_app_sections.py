"""Neue App-Abschnitte per AppTest: Mehr Verfahren, Szenario-Vergleich, Engpässe - Standard, jedes Preset, jede Änderung, Randwerte."""

import os

import pytest
from streamlit.testing.v1 import AppTest

import flow_constants as C
from flow_variants import CHANGES, NEEDS_TARGET

APP_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")


def _run(setup=None):
    at = AppTest.from_file(APP_PATH, default_timeout=180)
    at.run()
    assert not at.exception, [str(e) for e in at.exception]
    if setup is not None:
        setup(at)
        at.run()
        assert not at.exception, [str(e) for e in at.exception]
    return at


def _apply(at, name):
    p = C.PRESETS[name]
    at.session_state["n_plants_slider"] = p["n_plants"]
    at.session_state["n_dcs_slider"] = p["n_dcs"]
    at.session_state["n_stores_slider"] = p["n_stores"]
    at.session_state["dc_scale_slider"] = p["dc_throughput_scale"]
    at.session_state["plant_scale_slider"] = p.get("plant_capacity_scale", 1.0)
    at.session_state["seed_input"] = p["seed"]
    at.session_state["n_periods_slider"] = p.get("n_periods", 1)
    at.session_state["peak_multiplier_slider"] = p.get("demand_peak_multiplier", 1.0)


def _texts(at):
    return [e.value for e in list(at.success) + list(at.warning) + list(at.info) + list(at.error)]


def test_default_shows_all_three_exact_solvers_agreeing_and_the_bottleneck_table():
    at = _run()
    assert any("Alle drei exakten Löser" in t for t in _texts(at))
    assert any("Engpass" in list(d.value.columns) and "Schattenpreis (€ je Einheit)" in list(d.value.columns) for d in at.dataframe)
    assert any("Praxisregel" in set(d.value["Art"]) for d in at.dataframe if "Art" in d.value.columns)
    assert any("Kein Vergleich" in str(s.value) or s.value == "none" for s in at.selectbox)


@pytest.mark.parametrize("name", list(C.PRESETS))
def test_every_preset_renders_the_new_sections(name):
    at = _run(lambda a: _apply(a, name))
    assert not at.error and any("Alle drei exakten Löser" in t for t in _texts(at))


@pytest.mark.parametrize("change", list(CHANGES))
def test_every_change_renders_a_comparison(change):
    def setup(at):
        at.session_state["scenario_change"] = change
    at = _run(setup)
    assert any(m.label == "Gesamtkosten Ausgangslage" for m in at.metric) and any(m.label == "Fehlmenge" for m in at.metric)
    assert NEEDS_TARGET.get(change) is None or any(s.key in ("scenario_dc", "scenario_plant") for s in at.selectbox)


def test_dc_expansion_lowers_the_cost_and_the_investment_shows_the_payback():
    def setup(at):
        at.session_state["scenario_change"] = "dc_expand"
        at.session_state["scenario_invest"] = 50000.0
    at = _run(setup)
    v2 = next(m for m in at.metric if m.label.startswith("Gesamtkosten: DC 1 um 50 %"))
    assert v2.delta.startswith("-") or "−" in v2.delta or v2.delta.startswith("- ")
    assert any("amortisiert sich nach" in t for t in _texts(at))


def test_a_variant_that_saves_nothing_has_no_payback():
    def setup(at):
        at.session_state["scenario_change"] = "demand"
        at.session_state["scenario_invest"] = 1000.0
    at = _run(setup)
    assert any("keine Amortisation" in t for t in _texts(at))


def test_scaling_experiment_runs_on_demand():
    at = _run()
    next(b for b in at.button if b.key == "scaling_start").click().run()
    assert not at.exception
    frames = [d.value for d in at.dataframe if "Simplex-Iterationen" in d.value.columns]
    assert frames and list(frames[0]["Simplex-Iterationen"]) == [33, 118, 295] and list(frames[0]["Knoten"]) == [19, 49, 100] and list(frames[0]["Kanten"]) == [55, 312, 1124]
    assert all(row["OR-Tools (ms)"] < row["Netzwerksimplex (eigen) (ms)"] for _i, row in frames[0].iterrows() if row["Knoten"] == 100)
