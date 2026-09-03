"""Ein-Klick-Beispielszenarien und Permalink-Logik - dasselbe SETTING_SPECS-Muster
wie in den anderen Demos dieses Workspace (z. B. nutrition_presets.py)."""

import math
import random
from dataclasses import dataclass
from typing import Callable, Optional

import streamlit as st

import flow_constants as C


@dataclass(frozen=True)
class SettingSpec:
    url_param: str
    caster: Callable
    default: object
    lo: Optional[float] = None
    hi: Optional[float] = None


SETTING_SPECS = {
    "n_plants_slider": SettingSpec("np", int, C.N_PLANTS_DEFAULT, *C.N_PLANTS_RANGE),
    "n_dcs_slider": SettingSpec("nd", int, C.N_DCS_DEFAULT, *C.N_DCS_RANGE),
    "n_stores_slider": SettingSpec("ns", int, C.N_STORES_DEFAULT, *C.N_STORES_RANGE),
    "dc_scale_slider": SettingSpec("dcs", float, 1.0, 0.2, 1.5),
    "plant_scale_slider": SettingSpec("ps", float, 1.0, 0.3, 1.5),
    "seed_input": SettingSpec("seed", int, C.RANDOM_SEED_DEFAULT, *C.RANDOM_SEED_RANGE),
}


def bounds(state_key):
    spec = SETTING_SPECS[state_key]
    return spec.lo, spec.hi


def apply_preset(name):
    p = C.PRESETS[name]
    st.session_state["n_plants_slider"] = p["n_plants"]
    st.session_state["n_dcs_slider"] = p["n_dcs"]
    st.session_state["n_stores_slider"] = p["n_stores"]
    st.session_state["dc_scale_slider"] = p["dc_throughput_scale"]
    st.session_state["plant_scale_slider"] = p.get("plant_capacity_scale", 1.0)
    st.session_state["seed_input"] = p["seed"]


def randomize_seed():
    st.session_state["seed_input"] = random.randint(0, 2_000_000_000)


def load_permalink_settings():
    if "permalink_loaded" in st.session_state:
        return
    qp = st.query_params
    for state_key, spec in SETTING_SPECS.items():
        if spec.url_param in qp:
            try:
                value = spec.caster(qp[spec.url_param])
                if isinstance(value, float) and not math.isfinite(value):
                    continue
                if spec.lo is not None:
                    value = max(spec.lo, value)
                if spec.hi is not None:
                    value = min(spec.hi, value)
                st.session_state[state_key] = value
            except (ValueError, TypeError):
                pass
    st.session_state["permalink_loaded"] = True


def init_session_state_defaults():
    for state_key, spec in SETTING_SPECS.items():
        if state_key not in st.session_state:
            st.session_state[state_key] = spec.default


def sync_query_params(n_plants, n_dcs, n_stores, dc_scale, plant_scale, seed):
    try:
        st.query_params["np"] = str(int(n_plants))
        st.query_params["nd"] = str(int(n_dcs))
        st.query_params["ns"] = str(int(n_stores))
        st.query_params["dcs"] = str(dc_scale)
        st.query_params["ps"] = str(plant_scale)
        st.query_params["seed"] = str(int(seed))
    except Exception:
        pass
