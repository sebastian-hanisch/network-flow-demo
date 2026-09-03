"""Plotly-Visualisierungen für die Distributionsnetzwerk-Demo: Sankey-Flussdiagramm
(je Periode), Kostenaufschlüsselung, Kapazitätsauslastung, Laufzeitvergleich,
Lagerbestand über die Zeit (Mehrperioden-Fall)."""

import plotly.graph_objects as go

import flow_constants as C
from flow_evaluation import KIND_LABELS, cost_breakdown, dc_utilization, inventory_by_period, plant_utilization
from flow_network import dc_in, dc_out, node_name


def sankey_figure(instance, flow, title, period=0):
    """Warenfluss-Diagramm für EINE Periode (Default: Periode 0 - im Ein-Perioden-Fall
    die einzige, im Mehrperioden-Fall über den period-Parameter wählbar). Die
    Lagerhaltungskante taucht hier bewusst nicht auf - sie verbindet zwei
    verschiedene Perioden und passt nicht in die Momentaufnahme einer einzelnen
    Periode; siehe stattdessen inventory_figure()."""
    n = instance.n_periods
    dc_in_to_dc = {dc_in(dc, period, n): dc for dc in instance.dcs}
    dc_out_to_dc = {dc_out(dc, period, n): dc for dc in instance.dcs}
    plant_node_to_base = {node_name(p, period, n): p for p in instance.plants}
    store_node_to_base = {node_name(s, period, n): s for s in instance.stores}

    has_shortfall = any(
        flow.get(a.idx, 0.0) > 1e-6 for a in instance.arcs if a.kind == "fehlmenge" and a.period == period
    )
    nodes = list(instance.plants) + list(instance.dcs) + list(instance.stores)
    if has_shortfall:
        nodes = nodes + ["Notbeschaffung"]
    idx_of = {n_: i for i, n_ in enumerate(nodes)}
    colors = (
        [C.COLOR_PLANT] * len(instance.plants)
        + [C.COLOR_DC] * len(instance.dcs)
        + [C.COLOR_STORE] * len(instance.stores)
        + ([C.COLOR_SHORTFALL] if has_shortfall else [])
    )

    link_source, link_target, link_value, link_color = [], [], [], []
    for a in instance.arcs:
        if a.period != period:
            continue
        f = flow.get(a.idx, 0.0)
        if f <= 1e-6:
            continue
        if a.kind == "transport_werk_dc":
            link_source.append(idx_of[plant_node_to_base[a.tail]])
            link_target.append(idx_of[dc_in_to_dc[a.head]])
            link_value.append(f)
            link_color.append("rgba(37,99,235,0.35)")
        elif a.kind == "transport_dc_filiale":
            link_source.append(idx_of[dc_out_to_dc[a.tail]])
            link_target.append(idx_of[store_node_to_base[a.head]])
            link_value.append(f)
            link_color.append("rgba(15,118,110,0.35)")
        elif a.kind == "fehlmenge":
            link_source.append(idx_of["Notbeschaffung"])
            link_target.append(idx_of[store_node_to_base[a.head]])
            link_value.append(f)
            link_color.append("rgba(220,38,38,0.45)")

    fig = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(label=nodes, color=colors, pad=14, thickness=16, line=dict(width=0)),
        link=dict(source=link_source, target=link_target, value=link_value, color=link_color),
    ))
    fig.update_layout(title=title, height=480, font=dict(size=12), margin=dict(t=60, l=10, r=10, b=10))
    return fig


def inventory_figure(instance, flow, title):
    """Gestapelte Fläche: wie viel Bestand liegt am Übergang in jede Periode je DC
    im Lager - macht sichtbar, WANN im Zeitverlauf Bestand für eine spätere
    Nachfragespitze aufgebaut wird. Nur sinnvoll für n_periods > 1."""
    rows = inventory_by_period(instance, flow)
    fig = go.Figure()
    for dc in instance.dcs:
        dc_rows = sorted((r for r in rows if r["DC"] == dc), key=lambda r: r["Periode"])
        periods = [0] + [r["Periode"] for r in dc_rows]
        values = [0.0] + [r["Lagerbestand"] for r in dc_rows]
        fig.add_scatter(
            x=periods, y=values, mode="lines+markers", name=dc,
            stackgroup="inventar", line=dict(width=1.5),
        )
    fig.update_layout(
        title=title, xaxis_title="Periode", yaxis_title="Lagerbestand (Einheiten)",
        height=350, legend=dict(orientation="h", y=1.15),
        xaxis=dict(tickmode="linear", tick0=0, dtick=1),
    )
    return fig


def cost_breakdown_figure(instance, results):
    labels = list(results.keys())
    kinds = ["produktion", "umschlag", "transport_werk_dc", "transport_dc_filiale", "lagerhaltung", "fehlmenge"]
    palette = {
        "produktion": "#2563eb", "umschlag": "#0f766e", "transport_werk_dc": "#60a5fa",
        "transport_dc_filiale": "#5eead4", "lagerhaltung": C.COLOR_INVENTORY, "fehlmenge": "#dc2626",
    }
    fig = go.Figure()
    for k in kinds:
        ys = [cost_breakdown(instance, results[label]["flow"])[0].get(k, 0.0) for label in labels]
        if all(abs(y) < 1e-9 for y in ys):
            continue
        fig.add_bar(name=KIND_LABELS[k], x=labels, y=ys, marker_color=palette[k])
    fig.update_layout(
        barmode="stack", title="Kostenaufschlüsselung je Verfahren", yaxis_title="€",
        height=420, legend=dict(orientation="h", y=1.15),
    )
    return fig


def utilization_figure(instance, flow, title):
    dc_rows = dc_utilization(instance, flow)
    plant_rows = plant_utilization(instance, flow)
    fig = go.Figure()
    fig.add_bar(
        name="Werke", x=[r["Werk"] for r in plant_rows], y=[r["Auslastung"] for r in plant_rows],
        marker_color=C.COLOR_PLANT, text=[f"{r['Auslastung']:.0f}%" for r in plant_rows], textposition="outside",
    )
    fig.add_bar(
        name="Verteilzentren", x=[r["DC"] for r in dc_rows], y=[r["Auslastung"] for r in dc_rows],
        marker_color=C.COLOR_DC, text=[f"{r['Auslastung']:.0f}%" for r in dc_rows], textposition="outside",
    )
    fig.add_hline(y=100, line_dash="dot", line_color="gray")
    fig.update_layout(
        title=title, yaxis_title="Auslastung (%)", yaxis_range=[0, 118], height=380,
        legend=dict(orientation="h", y=1.15),
    )
    return fig


def runtime_figure(results):
    labels = list(results.keys())
    ys = [max(results[l]["runtime"] * 1000, 0.001) for l in labels]
    colors = [C.COLOR_NAIVE, C.COLOR_OPTIMAL, C.COLOR_REFERENCE][: len(labels)]
    fig = go.Figure(go.Bar(x=labels, y=ys, marker_color=colors, text=[f"{y:.2f} ms" for y in ys], textposition="outside"))
    fig.update_layout(title="Laufzeit je Verfahren (log-Skala)", yaxis_title="ms", yaxis_type="log", height=350)
    return fig
