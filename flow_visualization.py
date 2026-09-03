"""Plotly-Visualisierungen für die Distributionsnetzwerk-Demo: Sankey-Flussdiagramm,
Kostenaufschlüsselung, Kapazitätsauslastung, Laufzeitvergleich."""

import plotly.graph_objects as go

import flow_constants as C
from flow_evaluation import KIND_LABELS, cost_breakdown, dc_utilization, plant_utilization
from flow_network import dc_in, dc_out


def sankey_figure(instance, flow, title):
    dc_in_to_dc = {dc_in(dc): dc for dc in instance.dcs}
    dc_out_to_dc = {dc_out(dc): dc for dc in instance.dcs}

    has_shortfall = any(flow.get(a.idx, 0.0) > 1e-6 for a in instance.arcs if a.kind == "fehlmenge")
    nodes = list(instance.plants) + list(instance.dcs) + list(instance.stores)
    if has_shortfall:
        nodes = nodes + ["Notbeschaffung"]
    idx_of = {n: i for i, n in enumerate(nodes)}
    colors = (
        [C.COLOR_PLANT] * len(instance.plants)
        + [C.COLOR_DC] * len(instance.dcs)
        + [C.COLOR_STORE] * len(instance.stores)
        + ([C.COLOR_SHORTFALL] if has_shortfall else [])
    )

    link_source, link_target, link_value, link_color = [], [], [], []
    for a in instance.arcs:
        f = flow.get(a.idx, 0.0)
        if f <= 1e-6:
            continue
        if a.kind == "transport_werk_dc":
            link_source.append(idx_of[a.tail])
            link_target.append(idx_of[dc_in_to_dc[a.head]])
            link_value.append(f)
            link_color.append("rgba(37,99,235,0.35)")
        elif a.kind == "transport_dc_filiale":
            link_source.append(idx_of[dc_out_to_dc[a.tail]])
            link_target.append(idx_of[a.head])
            link_value.append(f)
            link_color.append("rgba(15,118,110,0.35)")
        elif a.kind == "fehlmenge":
            link_source.append(idx_of["Notbeschaffung"])
            link_target.append(idx_of[a.head])
            link_value.append(f)
            link_color.append("rgba(220,38,38,0.45)")

    fig = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(label=nodes, color=colors, pad=14, thickness=16, line=dict(width=0)),
        link=dict(source=link_source, target=link_target, value=link_value, color=link_color),
    ))
    fig.update_layout(title=title, height=480, font=dict(size=12), margin=dict(t=60, l=10, r=10, b=10))
    return fig


def cost_breakdown_figure(instance, results):
    labels = list(results.keys())
    kinds = ["produktion", "umschlag", "transport_werk_dc", "transport_dc_filiale", "fehlmenge"]
    palette = {
        "produktion": "#2563eb", "umschlag": "#0f766e", "transport_werk_dc": "#60a5fa",
        "transport_dc_filiale": "#5eead4", "fehlmenge": "#dc2626",
    }
    fig = go.Figure()
    for k in kinds:
        ys = [cost_breakdown(instance, results[label]["flow"])[0].get(k, 0.0) for label in labels]
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
