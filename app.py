"""
Distributionsnetzwerk-Optimierung (Min-Cost-Flow / Netzwerksimplex) - interaktive Demo
Sebastian Hanisch - Operations Research und Machine Learning

Kernstück dieser Demo ist eine eigene Implementierung des Netzwerksimplex-Algorithmus
(flow_network_simplex.py) für das Min-Cost-Flow-Problem - klassisches Verfahren der
Netzwerkoptimierung (siehe z. B. Ahuja/Magnanti/Orlin, "Network Flows"), hier neu in
Python umgesetzt. Die Demo zeigt an einem mehrstufigen Distributionsnetz (Werke ->
Verteilzentren -> Filialen), wie der Algorithmus arbeitet, vergleicht ihn mit einer
unoptimierten First-Come-First-Served-Baseline und verifiziert seine Korrektheit sowie
Laufzeit gegen Google OR-Tools als Referenzlöser.

Mehrperioden-Erweiterung (Regler "Anzahl Perioden" > 1): das Netzwerk wird zeit-expandiert,
Verteilzentren können über eine Lagerhaltungskante Bestand in die nächste Periode
mitnehmen - der Netzwerksimplex selbst bleibt dabei unverändert, er löst nur ein
größeres, strukturell identisches Min-Cost-Flow-Problem. Bei n_periods=1 (Default)
reduziert sich alles exakt auf die vorherige Ein-Perioden-Variante.

Selbe Struktur wie bei den anderen Demos in diesem Workspace: Ergebnis zuerst,
vollständiger Methodenvergleich sekundär im Expander, dazu "Wie funktioniert diese
Demo?" und "Mathematische Formulierung" als eigene Expander.

Code-Struktur: Netzwerkaufbau, Solver, Kennzahlen, PDF-Export und Visualisierung liegen
in den Modulen flow_*.py neben dieser Datei.
"""

import time

import pandas as pd
import streamlit as st

import flow_constants as C
import flow_scenario
from flow_evaluation import comparison_rows, inventory_total, savings_pct, shortfall_total, total_cost
from flow_naive import solve_naive
from flow_network_simplex import solve_network_simplex
from flow_pdf_export import generate_distribution_plan_pdf
from flow_presets import (
    apply_preset,
    bounds,
    init_session_state_defaults,
    load_permalink_settings,
    randomize_seed,
    sync_query_params,
)
from flow_reference_solver import solve_reference
from flow_visualization import cost_breakdown_figure, inventory_figure, runtime_figure, sankey_figure, utilization_figure

NAIVE_LABEL = "Unoptimiert (FCFS je Filiale)"
SIMPLEX_LABEL = "Netzwerksimplex (eigene Implementierung)"
REFERENCE_LABEL = "Referenz (Google OR-Tools)"


@st.cache_data(show_spinner=False)
def _compute(n_plants, n_dcs, n_stores, dc_scale, plant_scale, seed, n_periods, peak_multiplier):
    instance = flow_scenario.generate_instance(
        n_plants, n_dcs, n_stores, seed, dc_scale, plant_scale,
        n_periods=n_periods, demand_peak_multiplier=peak_multiplier,
    )

    t0 = time.perf_counter()
    naive_flow, naive_cost = solve_naive(instance)
    t1 = time.perf_counter()

    ns_result = solve_network_simplex(instance)
    t2 = time.perf_counter()

    ref_flow, ref_cost, ref_feasible, ref_status = solve_reference(instance)
    t3 = time.perf_counter()

    results = {
        NAIVE_LABEL: dict(flow=naive_flow, cost=naive_cost, runtime=t1 - t0),
        SIMPLEX_LABEL: dict(
            flow=ns_result.flow, cost=ns_result.cost, runtime=t2 - t1,
            iterations=ns_result.iterations, feasible=ns_result.feasible,
        ),
        REFERENCE_LABEL: dict(flow=ref_flow, cost=ref_cost, runtime=t3 - t2, feasible=ref_feasible),
    }
    return instance, results


st.set_page_config(page_title="Distributionsnetzwerk-Optimierung – Sebastian Hanisch", layout="wide")

st.title("🔀 Distributionsnetzwerk-Optimierung")
st.markdown(
    """
Interaktive Demo zum **Min-Cost-Flow-Problem**: Ein Unternehmen beliefert Filialen über
Werke und Verteilzentren - gesucht ist der kostenminimale Warenfluss durchs gesamte
Netzwerk, unter Produktions-, Umschlag- und Transportkapazitäten, wahlweise über mehrere
Perioden mit Lagerhaltung. Kernstück ist eine eigene Implementierung des
**Netzwerksimplex-Algorithmus**, verifiziert gegen Google OR-Tools und verglichen mit
einer unkoordinierten Baseline. Hintergrund im Expander "Wie funktioniert diese Demo?"
unten sowie formal hergeleitet im Expander "📐 Mathematische Formulierung".
"""
)

st.caption("🎯 Schnellstart – ein Beispielszenario laden:")
preset_col1, preset_col2, preset_col3, preset_col4 = st.columns(4)
with preset_col1:
    st.button(
        "🏭 Normalfall", use_container_width=True,
        on_click=apply_preset, args=("Normalfall",),
        help="Ausreichend Kapazität überall - das Netzwerk hat echte Routing-Wahlfreiheit.",
    )
with preset_col2:
    st.button(
        "🚧 DC-Engpass", use_container_width=True,
        on_click=apply_preset, args=("DC-Engpass",),
        help="Verteilzentren stark gedrosselt - erzwingt teilweise Notbeschaffung (Fehlmenge).",
    )
with preset_col3:
    st.button(
        "🏗️ Knappe Werkskapazität", use_container_width=True,
        on_click=apply_preset, args=("Knappe Werkskapazität",),
        help="Wenig Produktionskapazität bei wenigen Werken - der Fehlmengen-Mechanismus greift hier anders als beim DC-Engpass.",
    )
with preset_col4:
    st.button(
        "📈 Nachfragespitze", use_container_width=True,
        on_click=apply_preset, args=("Nachfragespitze",),
        help="Mehrperioden-Szenario mit einer Nachfrage-Spitze in der Mitte des Planungshorizonts - zeigt, ob/wie Lagerhaltung sich lohnt.",
    )

st.caption(
    "🔗 Die Adresszeile oben spiegelt Ihre aktuelle Konfiguration wider – einfach kopieren, "
    "um ein Szenario zu teilen."
)

load_permalink_settings()
init_session_state_defaults()

with st.sidebar:
    st.header("⚙️ Einstellungen")
    n_plants = st.slider("Anzahl Werke", *bounds("n_plants_slider"), step=1, key="n_plants_slider")
    n_dcs = st.slider("Anzahl Verteilzentren", *bounds("n_dcs_slider"), step=1, key="n_dcs_slider")
    n_stores = st.slider("Anzahl Filialen", *bounds("n_stores_slider"), step=1, key="n_stores_slider")
    dc_scale = st.slider(
        "Verteilzentrum-Kapazität (Skalierung)", *bounds("dc_scale_slider"), step=0.05, key="dc_scale_slider",
        help="Skaliert die Durchsatzkapazität aller Verteilzentren - niedrige Werte erzeugen einen Engpass.",
    )
    plant_scale = st.slider(
        "Werks-Kapazität (Skalierung)", *bounds("plant_scale_slider"), step=0.05, key="plant_scale_slider",
        help="Skaliert die Produktionskapazität aller Werke.",
    )
    seed_lo, seed_hi = bounds("seed_input")
    seed = st.number_input("Zufalls-Seed", min_value=seed_lo, max_value=seed_hi, step=1, key="seed_input")
    st.button(
        "🎲 Neues Zufallsnetzwerk generieren", use_container_width=True, on_click=randomize_seed,
        help="Würfelt einen neuen Zufalls-Seed für Positionen, Kosten und Kapazitäten.",
    )

    st.markdown("**Mehrperioden-Erweiterung**")
    n_periods = st.slider(
        "Anzahl Perioden", *bounds("n_periods_slider"), step=1, key="n_periods_slider",
        help="Ab 2 Perioden können Verteilzentren Bestand mit Lagerhaltungskosten in die nächste "
             "Periode mitnehmen (begrenzt durch die Lagerkapazität).",
    )
    peak_multiplier = st.slider(
        "Nachfrage-Spitze (Faktor)", *bounds("peak_multiplier_slider"), step=0.1, key="peak_multiplier_slider",
        help="Erhöht die Nachfrage in der mittleren Periode gegenüber den Randperioden - Faktor 1.0 "
             "= keine Saisonalität. Wirkt nur bei mehr als einer Periode.",
        disabled=n_periods == 1,
    )
    if n_periods == 1:
        st.caption("ℹ️ Mit nur einer Periode reduziert sich das Modell auf den Ein-Perioden-Fall (keine Lagerhaltung).")
    elif peak_multiplier <= 1.0:
        st.caption(
            "ℹ️ Bei flacher Nachfrage (Faktor 1.0) lohnt sich Lagerhaltung nie - "
            "Lagerhaltungskosten sind nie negativ. Regler oben erhöhen, um eine "
            "Nachfrage-Spitze zu erzeugen und Bestandsaufbau zu sehen."
        )

sync_query_params(n_plants, n_dcs, n_stores, dc_scale, plant_scale, int(seed), int(n_periods), peak_multiplier)

instance, results = _compute(
    n_plants, n_dcs, n_stores, dc_scale, plant_scale, int(seed), int(n_periods), peak_multiplier,
)
simplex = results[SIMPLEX_LABEL]
naive = results[NAIVE_LABEL]
reference = results[REFERENCE_LABEL]

if not simplex["feasible"]:
    st.error(
        "Der eigene Netzwerksimplex hat innerhalb des Iterationslimits keine zulässige "
        "Optimallösung gefunden - das sollte bei dieser Netzgröße nicht vorkommen. "
        "Bitte ein neues Zufallsnetzwerk generieren."
    )
if not reference.get("feasible", True):
    st.warning("Die OR-Tools-Referenzlösung meldet Infeasibility - unerwartet, bitte Szenario neu würfeln.")

st.markdown("## 🎯 Ihr optimierter Distributionsplan")

shortfall = shortfall_total(instance, simplex["flow"])
savings = savings_pct(naive["cost"], simplex["cost"])
cost_match = abs(simplex["cost"] - reference["cost"]) < max(1.0, 0.001 * reference["cost"])

metric_cols = st.columns(5 if instance.n_periods > 1 else 4)
metric_cols[0].metric("Gesamtkosten (Netzwerksimplex)", f"{simplex['cost']:,.0f} €", delta=f"{-savings:.1f}% vs. unoptimiert", delta_color="inverse")
metric_cols[1].metric("Fehlmenge (Notbeschaffung)", f"{shortfall:.0f} Einheiten", delta=f"von {instance.total_demand:.0f} Gesamtnachfrage" if shortfall > 0 else "keine")
metric_cols[2].metric("Simplex-Iterationen", f"{simplex['iterations']}")
metric_cols[3].metric("Laufzeit (eigener Solver)", f"{simplex['runtime']*1000:.2f} ms", delta=f"OR-Tools: {reference['runtime']*1000:.2f} ms", delta_color="off")
if instance.n_periods > 1:
    inv_used = inventory_total(instance, simplex["flow"])
    metric_cols[4].metric(
        "Lagerhaltung (Summe)", f"{inv_used:.0f} Einheiten", delta="über alle Periodenübergänge",
        help="0, solange die Nachfrage über die Perioden flach ist (Regler \"Nachfrage-Spitze\" = 1.0) - "
             "Lagerhaltung kostet immer etwas, lohnt sich also nur, wenn dadurch später Fehlmenge oder "
             "eine teurere Route vermieden wird.",
    )

if cost_match:
    st.success(
        f"✅ Korrektheits-Check bestanden: Der eigene Netzwerksimplex liefert dieselben "
        f"Gesamtkosten wie die OR-Tools-Referenzlösung ({reference['cost']:,.2f} € vs. "
        f"{simplex['cost']:,.2f} €)."
    )
else:
    st.warning(
        f"⚠️ Kostenabweichung zur Referenzlösung: {simplex['cost']:,.2f} € (eigen) vs. "
        f"{reference['cost']:,.2f} € (OR-Tools) - sollte praktisch nicht vorkommen, bitte melden."
    )

if instance.n_periods > 1:
    shown_period = st.select_slider(
        "Periode anzeigen (Warenfluss-Diagramm unten)",
        options=list(range(instance.n_periods)),
        format_func=lambda t: f"Periode {t + 1}",
        key="shown_period",
    )
else:
    shown_period = 0

st.plotly_chart(
    sankey_figure(instance, simplex["flow"], f"Warenfluss – {SIMPLEX_LABEL} (Periode {shown_period + 1})", period=shown_period),
    use_container_width=True,
)

if instance.n_periods > 1:
    st.plotly_chart(
        inventory_figure(instance, simplex["flow"], f"Lagerbestand über die Zeit – {SIMPLEX_LABEL}"),
        use_container_width=True,
    )
    st.caption(
        "Bestand, den ein Verteilzentrum von einer Periode in die nächste mitnimmt - sichtbar wird, "
        "WANN im Zeitverlauf für eine spätere Nachfragespitze vorausschauend Bestand aufgebaut wird."
    )

pdf_bytes = generate_distribution_plan_pdf(instance, SIMPLEX_LABEL, simplex["flow"], simplex["cost"], simplex["runtime"] * 1000)
st.download_button(
    "📄 Distributionsplan als PDF herunterladen", data=pdf_bytes,
    file_name="distributionsplan.pdf", mime="application/pdf",
)

st.markdown("---")
st.subheader("📊 Wie viel bringt die netzweite Koordination?")
st.markdown(
    f"""
**{NAIVE_LABEL}** beliefert jede Filiale nacheinander über die jeweils güns­tigste in
diesem Moment noch verfügbare komplette Route - ohne Rücksicht darauf, was das für
später bediente Filialen an Kapazität übrig lässt. **{SIMPLEX_LABEL}** löst dasselbe
Problem exakt, netzweit koordiniert. **{REFERENCE_LABEL}** bestätigt die Kosten
unabhängig über einen zweiten, industriell erprobten Solver - beide finden garantiert
dieselbe Gesamtkostensumme, weil ein Min-Cost-Flow-Problem konvex ist (kein Heuristik-
Gap, nur die eine globale Optimallösung).
"""
)

col_a, col_b = st.columns(2)
with col_a:
    st.plotly_chart(cost_breakdown_figure(instance, results), use_container_width=True)
with col_b:
    st.plotly_chart(runtime_figure(results), use_container_width=True)

with st.expander("🔧 Vollständiger Vergleich aller drei Verfahren", expanded=False):
    st.dataframe(pd.DataFrame(comparison_rows(instance, results)), use_container_width=True, hide_index=True)

    tabs = st.tabs([NAIVE_LABEL, SIMPLEX_LABEL, REFERENCE_LABEL])
    for tab, label in zip(tabs, [NAIVE_LABEL, SIMPLEX_LABEL, REFERENCE_LABEL]):
        with tab:
            st.plotly_chart(
                sankey_figure(instance, results[label]["flow"], f"Warenfluss – {label} (Periode {shown_period + 1})", period=shown_period),
                use_container_width=True, key=f"sankey_{label}",
            )
            if instance.n_periods > 1:
                st.plotly_chart(
                    inventory_figure(instance, results[label]["flow"], f"Lagerbestand über die Zeit – {label}"),
                    use_container_width=True, key=f"inventory_{label}",
                )
            st.plotly_chart(
                utilization_figure(instance, results[label]["flow"], f"Kapazitätsauslastung – {label}"),
                use_container_width=True, key=f"util_{label}",
            )

st.markdown("---")

with st.expander("Wie funktioniert diese Demo?"):
    st.markdown(
        r"""
**Die Problemstellung:** Ein Unternehmen betreibt mehrere **Werke** (Produktionskosten,
begrenzte Produktionskapazität), mehrere **Verteilzentren** (Umschlagkosten, begrenzter
Gesamtdurchsatz) und beliefert mehrere **Filialen** mit fester Nachfrage. Transportkosten
sind proportional zur Entfernung. Gesucht: der mengenmäßige Warenfluss auf jeder Kante
des Netzwerks, der die Gesamtkosten minimiert - das klassische **Min-Cost-Flow-Problem**
bzw. seine Spezialform, das **(kapazitierte) Transportproblem mit Zwischenlagern**
(Transshipment Problem).

**Zwei Modellierungs-Kniffe, die das Problem erst zu einem "sauberen" Netzwerkfluss
machen** (Details mit Formeln im Expander "📐 Mathematische Formulierung"):

1. **Knotenkapazität als Kantenkapazität:** Ein Min-Cost-Flow-Modell kennt nur
   Kapazitäten auf Kanten, aber ein Verteilzentrum hat eine Kapazität auf sich selbst
   (Gesamtdurchsatz). Kniff: jedes Verteilzentrum wird in zwei Knoten gesplittet
   (Eingang/Ausgang), verbunden durch eine einzige interne Kante mit genau dieser
   Kapazität - aller Zufluss läuft über den Eingang, aller Abfluss über den Ausgang.
2. **SRC/SINK als Ausgleichsknoten:** Werkskapazität und Filialnachfrage stimmen in
   Summe praktisch nie exakt überein, ein Netzwerksimplex braucht aber ein exakt
   ausgeglichenes Netz. Ein Hilfsknoten SRC speist sowohl die Werke (zu
   Produktionskosten) als auch - als teure Notbeschaffung mit hohen Strafkosten -
   jede Filiale direkt; ein Hilfsknoten SINK sammelt die gesamte Nachfrage ein. Damit
   ist das Netz immer lösbar, selbst bei einem harten Kapazitätsengpass, und die
   Fehlmengen-Kante macht sichtbar, wie viel Nachfrage nicht wirtschaftlich bedient
   werden kann - probieren Sie dazu das Preset "DC-Engpass" oben.

**Netzwerksimplex statt generischem LP-Solver:** Jede Basislösung eines
Min-Cost-Flow-Problems entspricht einem **Spannbaum** über alle Knoten (ein klassisches
Ergebnis der Netzwerkoptimierung, siehe Ahuja/Magnanti/Orlin, *Network Flows*, Kap. 11).
Ein Pivot-Schritt tauscht dabei genau eine Kante des Spannbaums gegen eine
Nicht-Baum-Kante - dadurch müssen weder Tableau-Zeilen noch -Spalten eines generischen
Simplex explizit geführt werden, nur Baumstruktur und Knotenpotentiale. Das macht den
Netzwerksimplex auf großen, dünn besetzten Netzwerken um Größenordnungen schneller als
generischer Simplex auf derselben Kanten-Knoten-Inzidenzmatrix - und liefert bei
ganzzahligen Eingabedaten automatisch eine ganzzahlige Lösung (Folge der **totalen
Unimodularität** der Inzidenzmatrix eines Netzwerkflusses), ganz ohne die Ganzzahligkeit
explizit zu erzwingen.

**Startlösung (Phase 1):** Der Algorithmus startet mit einer künstlichen Wurzel, an die
jeder echte Knoten über einen künstlichen Bogen mit sehr hohen Kosten (**Big-M-Methode**)
angebunden ist - ein immer gültiger, wenn auch teurer Spannbaum. Die Pivot-Schritte
drücken den Fluss auf diesen künstlichen Bögen danach systematisch auf 0, sofern das
Netzwerk (wie hier per Konstruktion immer) auch ohne sie lösbar ist.

**"Unoptimiert (FCFS je Filiale)":** beliefert Filialen nacheinander (keine
Priorisierung) über die jeweils güns­tigste noch verfügbare komplette
Werk-DC-Filiale-Route - dieselbe Grundidee wie die FCFS-Baseline in den anderen Demos
dieses Workspace. Frühe Filialen "verbrauchen" dabei möglicherweise güns­tige Kapazität,
die für später bediente Filialen wirtschaftlicher gewesen wäre - eine rein lokale,
unkoordinierte Entscheidung je Filiale statt einer netzweiten Abstimmung.

**Referenzlösung:** Google OR-Tools' `SimpleMinCostFlow` (ebenfalls eine
Netzwerksimplex-Implementierung, industriell gehärtet und in C++ geschrieben) löst
dasselbe Problem unabhängig - bei jedem Szenario-Wechsel wird geprüft, dass beide
Lösungen exakt dieselben Gesamtkosten liefern (grüne Erfolgsmeldung oben). Der
Laufzeitvergleich ist bewusst Teil der Demo: eine industrielle C++-Implementierung mit
Jahrzehnten an Feintuning ist schneller als eine didaktische Python-Neuimplementierung -
Korrektheit lässt sich damit unabhängig von Performance zeigen.

**Mehrperioden-Erweiterung (Regler "Anzahl Perioden"):** Ab zwei Perioden wird das
Netzwerk **zeit-expandiert**: Werke, DC-Ein-/Ausgänge und Filialen werden je Periode
dupliziert, Produktions- und Durchsatzkapazität gelten dann als **Pro-Periode-Grenzen**
statt als Summe über den ganzen Horizont. Die einzige echte neue Kante ist eine
**Lagerhaltungskante** von einem DC-Ausgang der Periode $t$ zum selben DC-Ausgang der
Periode $t{+}1$: Bestand, der ankommt, aber nicht sofort an eine Filiale weitergeht,
kann zu Lagerhaltungskosten mitgenommen werden, begrenzt durch die Lagerkapazität - ganz
ohne neue Knotentypen, nur eine zusätzliche Kante je DC und Periodenübergang. SRC/SINK
bleiben bewusst EIN einziger Knoten über den ganzen Horizont (reine Ausgleichsknoten,
keine physische Position). Der Netzwerksimplex selbst braucht dafür **keine einzige
Codezeile Änderung** - er sieht nur ein größeres, aber strukturell identisches
Min-Cost-Flow-Problem.

Der eigentliche Witz der Erweiterung zeigt sich erst mit **Nachfrage-Saisonalität**
(Regler "Nachfrage-Spitze"): Ist die Nachfrage über die Perioden hinweg flach, lohnt
sich Lagerhaltung nie (Lagerhaltungskosten sind nie negativ) - das Modell reduziert sich
dann von selbst auf $T$ unabhängige Ein-Perioden-Probleme, ganz ohne dass das explizit
erzwungen werden müsste (siehe Test `test_flat_demand_across_periods_never_uses_inventory`
in `tests/test_network_simplex.py`). Mit einer Nachfragespitze in der Mitte des
Horizonts (Preset "Nachfragespitze") wird es interessant: die **myopische**
"Unoptimiert"-Baseline plant nie vorausschauend Bestand auf (sie kennt in jeder Periode
nur die aktuelle Route-Wahl, keine Lagerhaltungskante), während der Netzwerksimplex
schon in den Vorperioden gezielt Bestand aufbaut, wenn das günstiger ist als Fehlmenge
in der Spitzen-Periode - sichtbar im Diagramm "Lagerbestand über die Zeit" oben.

**In einem echten Distributionsnetz** kämen weitere Nebenbedingungen dazu (z. B.
Mindestbestellmengen, mehrere Produkte, periodenabhängige Kosten) - das Grundprinzip aus
Knoten, Kanten, Kapazitäten und Kosten sowie der Netzwerksimplex als Lösungsverfahren
bleiben aber dieselben.
"""
    )

with st.expander("📐 Mathematische Formulierung"):
    st.markdown(
        r"""
Gegeben ein gerichteter Graph $G=(V,E)$ mit Knoten $V$ (Werke, Verteilzentrum-Ein-/
Ausgänge, Filialen, sowie den Hilfsknoten $\text{SRC}$ und $\text{SINK}$) und Kanten
$E$, jede Kante $(i,j)$ mit Kosten $c_{ij} \geq 0$ pro Einheit und Kapazität
$u_{ij} \geq 0$. Jeder Knoten $i$ hat einen Bedarfswert $b_i$ (positiv = Angebot,
negativ = Nachfrage, 0 = reiner Durchgangsknoten), mit $\sum_i b_i = 0$. Gesucht sind
Flusswerte $x_{ij} \geq 0$, die die Gesamtkosten minimieren:
"""
    )
    st.latex(r"\min \sum_{(i,j) \in E} c_{ij}\, x_{ij}")
    st.latex(r"\text{u.d.N.} \quad \sum_{j:(i,j)\in E} x_{ij} - \sum_{j:(j,i)\in E} x_{ji} = b_i \quad \forall i \in V")
    st.latex(r"0 \leq x_{ij} \leq u_{ij} \quad \forall (i,j) \in E")
    st.markdown(
        r"""
**Die beiden Modellierungs-Kniffe als Formeln:** Für ein Verteilzentrum $k$ mit
Durchsatzgrenze $\bar{d}_k$ wird der Knoten in $k_{\text{in}}$ und $k_{\text{out}}$
gesplittet, verbunden durch $(k_{\text{in}}, k_{\text{out}}) \in E$ mit
$u_{k_{\text{in}},k_{\text{out}}} = \bar{d}_k$. Für den Ausgleich zwischen
Werkskapazität und Filialnachfrage gilt $b_{\text{SRC}} = \sum_s \text{demand}_s$,
$b_{\text{SINK}} = -\sum_s \text{demand}_s$, mit
$u_{\text{SRC},s} = \text{demand}_s$ (Fehlmengen-Kante, Kosten = Strafkosten) und
$u_{s,\text{SINK}} = \text{demand}_s$ (erzwingt in Summe exakte Bedarfsdeckung je
Filiale, da $\sum_s u_{\text{SRC},s} = \sum_s \text{demand}_s = b_{\text{SRC}}$ keinen
Spielraum lässt).

**Netzwerksimplex - Optimalitätsbedingung:** Jede Basislösung entspricht einem
Spannbaum $T \subseteq E$. Zu jedem Spannbaum gehören eindeutige **Knotenpotentiale**
$\pi_i$ mit $\pi_i - \pi_j = c_{ij}$ für alle Baumkanten $(i,j) \in T$ (o. B. d. A.
$\pi_{\text{root}} = 0$). Für jede Nicht-Baum-Kante $(i,j)$ ist die **reduzierte
Kostengröße**
"""
    )
    st.latex(r"\bar{c}_{ij} = c_{ij} - \pi_i + \pi_j")
    st.markdown(
        r"""
definiert. Die Basislösung ist genau dann optimal, wenn für jede Nicht-Baum-Kante an
ihrer unteren Schranke ($x_{ij}=0$) gilt $\bar{c}_{ij} \geq 0$, und für jede an ihrer
oberen Schranke ($x_{ij}=u_{ij}$) gilt $\bar{c}_{ij} \leq 0$ - äquivalent zur
Komplementaritätsbedingung des generischen Simplex, hier aber in $O(|V|)$ statt über ein
volles Tableau berechenbar.

**Ein Pivot-Schritt:** Verletzt eine Nicht-Baum-Kante $(u,v)$ diese Bedingung, bildet sie
zusammen mit dem eindeutigen Baumpfad zwischen $u$ und $v$ einen Kreis. Der Fluss wird
entlang dieses Kreises um
"""
    )
    st.latex(r"\theta^* = \min_{(i,j) \in \text{Kreis}} \begin{cases} u_{ij} - x_{ij} & \text{Kante in Kreisrichtung} \\ x_{ij} & \text{Kante gegen Kreisrichtung} \end{cases}")
    st.markdown(
        r"""
erhöht - die Kante, die dieses Minimum realisiert, verlässt den Baum (austretende
Kante), $(u,v)$ tritt ein. Terminiert, wenn keine Nicht-Baum-Kante die
Optimalitätsbedingung mehr verletzt.

**Mehrperioden-Erweiterung als Zeit-Expansion:** Für $T$ Perioden $t \in \{0, \ldots,
T{-}1\}$ wird jeder Werks-, DC-Ein-/Ausgangs- und Filial-Knoten dupliziert (Knoten
$i@t$), Produktions- und Durchsatzkapazität gelten je Periode. Für ein DC $k$ mit
Lagerkapazität $\bar{l}_k$ und Lagerhaltungskosten $h_k$ pro Einheit und Periode kommt
je Periodenübergang eine Lagerhaltungskante hinzu:
"""
    )
    st.latex(r"(k_{\text{out}}@t,\ k_{\text{out}}@(t{+}1)) \in E, \quad u = \bar{l}_k, \quad c = h_k \qquad t = 0, \ldots, T{-}2")
    st.markdown("SRC und SINK bleiben dabei EIN Knoten über alle Perioden:")
    st.latex(r"b_{\text{SRC}} = \sum_t \sum_s \text{demand}_{s,t}")
    st.markdown(
        r"""
mit je einer Produktions- und Fehlmengen-Kante pro (Werk, Periode) bzw. (Filiale,
Periode). Diese Erweiterung ändert nichts an der
Optimalitätsbedingung oder der Pivot-Logik oben - der Netzwerksimplex behandelt sie als
ein einziges, größeres Min-Cost-Flow-Problem auf einem größeren Graphen.

**Bezug zum Code:** `flow_network.py` baut Graph und Kapazitäten inkl. der drei
Modellierungs-Kniffe (Knotenkapazität, SRC/SINK-Ausgleich, Zeit-Expansion) auf.
`flow_network_simplex.py` setzt die Formeln oben 1:1 um - Big-M-Startlösung,
Kreiserkennung über den nächsten gemeinsamen Vorfahren im Spannbaum, Pivot mit
Bland's-Regel-ähnlichem Tie-Break zur Vermeidung von Zyklen bei degenerierten
Pivotschritten - unverändert für den Mehrperioden-Fall. `flow_naive.py` implementiert
die FCFS-Baseline (im Mehrperioden-Fall myopisch, Periode für Periode ohne
Lagerhaltungskante), `flow_reference_solver.py` kapselt Google OR-Tools als
unabhängige Gegenprobe.

**Quelle:** Ahuja, R. K., Magnanti, T. L., Orlin, J. B. (1993). *Network Flows: Theory,
Algorithms, and Applications.* Prentice Hall - Kapitel 11 (Network Simplex Algorithm).
"""
    )

st.markdown("---")
st.caption(
    "Diese Demo ist Teil des Portfolios von [Sebastian Hanisch](https://sebastianhanisch.net) – "
    "Operations Research und Machine Learning. Interesse an einer maßgeschneiderten Lösung für "
    "Ihr Unternehmen? [Kontakt aufnehmen](https://sebastianhanisch.net/kontakt.html)"
)
