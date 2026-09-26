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
    # fixedrange auf beiden Achsen: verhindert Pinch-Zoom/Drag-Pan im Chart,
    # damit auf Touch-Geräten stattdessen die Seite normal gescrollt wird
    # (Hover-Tooltips bleiben davon unberührt).
    fig.update_xaxes(fixedrange=True)
    fig.update_yaxes(fixedrange=True)
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
    fig.update_xaxes(fixedrange=True)
    fig.update_yaxes(fixedrange=True)
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
    fig.update_xaxes(fixedrange=True)
    fig.update_yaxes(fixedrange=True)
    return fig


def runtime_figure(results):
    labels = list(results.keys())
    ys = [max(results[l]["runtime"] * 1000, 0.001) for l in labels]
    colors = [C.COLOR_NAIVE, C.COLOR_OPTIMAL, C.COLOR_REFERENCE][: len(labels)]
    fig = go.Figure(go.Bar(x=labels, y=ys, marker_color=colors, text=[f"{y:.2f} ms" for y in ys], textposition="outside"))
    fig.update_layout(title="Laufzeit je Verfahren (log-Skala)", yaxis_title="ms", yaxis_type="log", height=350)
    fig.update_xaxes(fixedrange=True)
    fig.update_yaxes(fixedrange=True)
    return fig


def rules_figure(rows):
    """Abstand zum Optimum in Prozent je Verfahren (Praxisregeln grau, exakte Löser blau)."""
    fig = go.Figure(go.Bar(
        y=[r["Verfahren"] for r in reversed(rows)], x=[r["Abstand zum Optimum (%)"] for r in reversed(rows)], orientation="h",
        marker_color=[C.COLOR_NAIVE if r["Art"] == "Praxisregel" else C.COLOR_OPTIMAL for r in reversed(rows)],
        text=[f"{r['Abstand zum Optimum (%)']:.1f} %".replace(".", ",") for r in reversed(rows)], textposition="auto",
    ))
    fig.update_layout(title="Mehrkosten gegenüber dem Optimum", height=300, margin=dict(l=10, r=10, t=40, b=10), xaxis_title="% über den optimalen Gesamtkosten")
    fig.update_xaxes(fixedrange=True)
    fig.update_yaxes(fixedrange=True)
    return fig


def scenario_figure(row_a, row_b, label_a, label_b):
    """Kostenaufschlüsselung je Art für zwei Szenarien nebeneinander (gestapelt)."""
    kinds = [k for k in KIND_LABELS if k != "nachfrage" and (row_a["by_kind"].get(k, 0.0) > 1e-6 or row_b["by_kind"].get(k, 0.0) > 1e-6)]
    palette = {"produktion": "#2563eb", "umschlag": "#0f766e", "transport_werk_dc": "#7c3aed", "transport_dc_filiale": "#64748b", "fehlmenge": "#dc2626", "lagerhaltung": "#d97706"}
    fig = go.Figure()
    for k in kinds:
        fig.add_trace(go.Bar(x=[label_a, label_b], y=[row_a["by_kind"].get(k, 0.0), row_b["by_kind"].get(k, 0.0)], name=KIND_LABELS[k], marker_color=palette.get(k)))
    fig.update_layout(barmode="stack", title="Kostenaufschlüsselung: Ausgangslage gegen Variante", height=340, margin=dict(l=10, r=10, t=40, b=10), yaxis_title="Gesamtkosten (€)", legend=dict(orientation="h", y=-0.25))
    fig.update_xaxes(fixedrange=True)
    fig.update_yaxes(fixedrange=True)
    return fig


def bottleneck_figure(rows):
    """Wert einer weiteren Einheit Kapazität je volle Kante (€ je Einheit und Periode)."""
    rows = list(reversed(rows))
    fig = go.Figure(go.Bar(y=[r["label"] for r in rows], x=[r["value"] for r in rows], orientation="h", marker_color=C.COLOR_SHORTFALL,
                           text=[f"{r['value']:.1f} €".replace(".", ",") for r in rows], textposition="auto"))
    fig.update_layout(title="Engpässe: was spart eine weitere Einheit Kapazität?", height=max(260, 34 * len(rows) + 80), margin=dict(l=10, r=10, t=40, b=10), xaxis_title="€ je zusätzliche Einheit")
    fig.update_xaxes(fixedrange=True)
    fig.update_yaxes(fixedrange=True)
    return fig


def scaling_figure(rows):
    """Laufzeit je Verfahren gegen die Netzgröße (Kanten), logarithmisch."""
    fig = go.Figure()
    colors = {"FCFS": C.COLOR_NAIVE, "Netzwerksimplex (eigen)": C.COLOR_OPTIMAL, "HiGHS-LP": "#0f766e", "OR-Tools": C.COLOR_REFERENCE}
    for name in ("FCFS", "Netzwerksimplex (eigen)", "HiGHS-LP", "OR-Tools"):
        fig.add_trace(go.Scatter(x=[r["arcs"] for r in rows], y=[r["runtime_ms"][name] for r in rows], mode="lines+markers", name=name, line=dict(color=colors[name])))
    fig.update_layout(title="Laufzeit gegen Netzgröße", height=340, margin=dict(l=10, r=10, t=40, b=10), xaxis_title="Kanten", yaxis_title="Laufzeit (ms)", legend=dict(orientation="h", y=-0.25))
    fig.update_xaxes(type="log", fixedrange=True)
    fig.update_yaxes(type="log", fixedrange=True)
    return fig
