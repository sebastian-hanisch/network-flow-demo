# Distributionsnetzwerk-Optimierung (Min-Cost-Flow, Netzwerksimplex)

Interaktive Demo zu einem mehrstufigen Distributionsnetz: Werke beliefern Filialen über
Verteilzentren, gesucht ist der kostenminimale Warenfluss durchs gesamte Netzwerk unter
Produktions-, Umschlag- und Transportkapazitäten. Kernstück ist eine **eigene
Implementierung des Netzwerksimplex-Algorithmus** für das Min-Cost-Flow-Problem -
klassisches Verfahren der Netzwerkoptimierung (Ahuja/Magnanti/Orlin, *Network Flows*,
Kap. 11), hier in Python neu umgesetzt und live gegen Google OR-Tools verifiziert.

## Worum geht's?

Fachlich ein **kapazitiertes Transportproblem mit Zwischenlagern** (Transshipment
Problem) - eine Spezialform des Min-Cost-Flow-Problems. Zwei Modellierungs-Kniffe machen
daraus ein "sauberes" Netzwerkfluss-Modell:

- **Knotenkapazität als Kantenkapazität:** Jedes Verteilzentrum wird in Eingang/Ausgang
  gesplittet, verbunden durch eine interne Kante mit Kapazität = Durchsatzgrenze - ein
  Min-Cost-Flow-Modell kennt sonst nur Kantenkapazitäten, keine Knotenkapazitäten.
- **SRC/SINK als Ausgleichsknoten:** Werkskapazität und Filialnachfrage stimmen in Summe
  praktisch nie exakt überein, der Netzwerksimplex braucht aber ein ausgeglichenes Netz.
  Ein Hilfsknoten speist Werke UND (teuer, als Notbeschaffung) jede Filiale direkt - das
  Netz ist damit immer lösbar, auch bei einem harten Kapazitätsengpass, und macht
  sichtbar, wie viel Nachfrage nicht wirtschaftlich bedient werden kann.

Drei Verfahren im direkten Vergleich, alle auf demselben Netzwerk:

- **Unoptimiert (FCFS je Filiale):** jede Filiale wird nacheinander über die jeweils
  güns­tigste noch verfügbare komplette Route beliefert - keine netzweite Koordination,
  frühe Filialen verbrauchen ggf. Kapazität, die später anders besser eingesetzt worden
  wäre.
- **Netzwerksimplex (eigene Implementierung):** löst dasselbe Problem exakt. Jede
  Basislösung eines Min-Cost-Flow-Problems entspricht einem Spannbaum - ein Pivot-Schritt
  tauscht genau eine Kante des Spannbaums gegen eine Nicht-Baum-Kante, ohne ein volles
  Simplex-Tableau zu führen. Startlösung über eine künstliche Wurzel mit Big-M-Kosten
  (Phase 1), danach Pivotisieren bis alle Optimalitätsbedingungen (reduzierte Kosten je
  nach Schrankenstatus) erfüllt sind.
- **Referenz (Google OR-Tools):** `SimpleMinCostFlow` (ebenfalls Netzwerksimplex,
  industriell gehärtet, C++) als unabhängige Gegenprobe - bei jedem Szenario wird
  geprüft, dass beide Lösungen exakt dieselben Gesamtkosten liefern, plus
  Laufzeitvergleich.

## Methodik

- Zufallsnetzwerk aus Werken (Produktionskosten/-kapazität), Verteilzentren
  (Umschlagkosten/-durchsatz) und Filialen (feste Nachfrage), Transportkosten
  proportional zur euklidischen Distanz - Seed-gesteuert und per Permalink
  reproduzierbar.
- Drei Beispielszenarien: Normalfall, DC-Engpass (erzwingt Notbeschaffung) und Knappe
  Werkskapazität (zeigt hier den größten Koordinationsgewinn ggü. der FCFS-Baseline).
- Sankey-Flussdiagramm je Verfahren, Kostenaufschlüsselung (Produktion/Umschlag/
  Transport/Fehlmenge), Kapazitätsauslastung je Werk/DC, Laufzeitvergleich, PDF-Export,
  Permalink.
- Korrektheits-Check bei jedem Szenario-Wechsel: eigener Netzwerksimplex vs. OR-Tools
  müssen dieselben Gesamtkosten liefern.

## Dateistruktur

| Datei | Inhalt |
|---|---|
| `app.py` | Streamlit-Hauptablauf (Sidebar, Primäransicht, Tabs) |
| `flow_constants.py` | Default-/Grenzwerte, Beispielszenarien |
| `flow_network.py` | Baut die ProblemInstance (Knoten, Kanten, Kapazitäten, Kosten) inkl. der beiden Modellierungs-Kniffe |
| `flow_scenario.py` | Zufällige, Seed-gesteuerte Szenariogenerierung |
| `flow_network_simplex.py` | Eigene Netzwerksimplex-Implementierung (Kernstück) |
| `flow_naive.py` | FCFS-Baseline (je Filiale güns­tigste verfügbare Route) |
| `flow_reference_solver.py` | Google OR-Tools `SimpleMinCostFlow` als Cross-Check |
| `flow_evaluation.py` | Kostenaufschlüsselung, Kapazitätsauslastung, Vergleichstabelle |
| `flow_visualization.py` | Sankey-Diagramm, Kostenaufschlüsselung, Auslastung, Laufzeitvergleich (Plotly) |
| `flow_pdf_export.py` | PDF-Distributionsplan |
| `flow_presets.py` | Beispielszenarien, Permalink-Logik (`SettingSpec`-Pattern) |
| `tests/` | Netzwerkaufbau-Korrektheit, Netzwerksimplex vs. OR-Tools auf Zufallsinstanzen (inkl. Engpass-Szenario), Flusserhaltung/Kapazitätseinhaltung für beide Solver, Iterationsgrenze |

## Lokal ausführen

```bash
pip install -r requirements-dev.txt
streamlit run app.py
```

Tests: `pytest tests/ -v`

---

Teil des [Operations-Research-Demo-Portfolios](https://sebastianhanisch.net/demos.html) von
[Sebastian Hanisch](https://sebastianhanisch.net) – Operations Research und Machine Learning.
Interesse an einer maßgeschneiderten Lösung? [Kontakt aufnehmen](https://sebastianhanisch.net/kontakt.html).
