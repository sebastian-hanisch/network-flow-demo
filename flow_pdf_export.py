"""Erzeugt den Distributionsplan (Netzwerksimplex-Lösung) als downloadbares PDF
(in-memory). Umlaute sind mit der FPDF-Kernschrift Helvetica unproblematisch - nur
der Halbgeviertstrich (–) wird vermieden (siehe nutrition_pdf_export.py)."""

import time

from flow_evaluation import cost_breakdown, shortfall_total


def generate_distribution_plan_pdf(instance, result_label, flow, cost, runtime_ms):
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Distributionsplan (Min-Cost-Flow, Netzwerksimplex)", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 6, f"Erstellt: {time.strftime('%d.%m.%Y %H:%M')} Uhr", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(3)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, "Zusammenfassung", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Verfahren: {result_label}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    if instance.n_periods > 1:
        pdf.cell(0, 6, f"Planungshorizont: {instance.n_periods} Perioden", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 6, f"Gesamtkosten: {cost:,.2f} EUR", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 6, f"Rechenzeit: {runtime_ms:.2f} ms", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    shortfall = shortfall_total(instance, flow)
    if shortfall > 1e-6:
        pdf.cell(0, 6, f"Nicht wirtschaftlich gedeckte Nachfrage (Notbeschaffung): {shortfall:.1f} Einheiten", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    cost_by_kind, units_by_kind = cost_breakdown(instance, flow)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, "Kostenaufschlüsselung", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    headers = ["Kostenart", "Menge (Einheiten)", "Kosten (EUR)"]
    widths = [90, 45, 45]
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(235, 235, 235)
    for h, w in zip(headers, widths):
        pdf.cell(w, 7, h, border=1, fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.ln(7)
    pdf.set_font("Helvetica", "", 9)
    labels = {
        "produktion": "Produktion", "umschlag": "Umschlag (DC)",
        "transport_werk_dc": "Transport Werk->DC", "transport_dc_filiale": "Transport DC->Filiale",
        "lagerhaltung": "Lagerhaltung (Bestand)", "fehlmenge": "Fehlmenge (Notbeschaffung)",
    }
    for kind, label in labels.items():
        row = [label, f"{units_by_kind.get(kind, 0.0):.1f}", f"{cost_by_kind.get(kind, 0.0):,.2f}"]
        for val, w in zip(row, widths):
            pdf.cell(w, 6, val, border=1, new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.ln(6)
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, "Flüsse Werk -> Verteilzentrum -> Filiale", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    show_period = instance.n_periods > 1
    if show_period:
        headers = ["Periode", "Von", "Nach", "Menge", "Kosten/Einheit"]
        widths = [18, 62, 62, 21, 21]
    else:
        headers = ["Von", "Nach", "Menge", "Kosten/Einheit"]
        widths = [60, 60, 30, 30]
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(235, 235, 235)
    for h, w in zip(headers, widths):
        pdf.cell(w, 7, h, border=1, fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.ln(7)
    pdf.set_font("Helvetica", "", 9)
    relevant_kinds = {"transport_werk_dc", "transport_dc_filiale", "lagerhaltung", "fehlmenge"}
    for a in instance.arcs:
        f = flow.get(a.idx, 0.0)
        if a.kind not in relevant_kinds or f <= 1e-6:
            continue
        von = a.tail.split("@")[0].replace("_in", "").replace("_out", "")
        nach = a.head.split("@")[0].replace("_in", "").replace("_out", "")
        if a.kind == "fehlmenge":
            von = "Notbeschaffung"
        if a.kind == "lagerhaltung":
            nach = f"{nach} (Periode {a.period + 2})"
        row = ([str(a.period + 1)] if show_period else []) + [von, nach, f"{f:.1f}", f"{a.cost:.2f}"]
        for val, w in zip(row, widths):
            pdf.cell(w, 6, val, border=1, new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.ln(6)

    return bytes(pdf.output())
