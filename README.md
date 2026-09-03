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

**Mehrperioden-Erweiterung:** Ab zwei Perioden wird das Netzwerk zeit-expandiert - Werke,
DC-Ein-/Ausgänge und Filialen werden je Periode dupliziert, Produktions- und
Durchsatzkapazität gelten pro Periode. Verteilzentren können über eine zusätzliche
Lagerhaltungskante (Lagerhaltungskosten, Lagerkapazität) Bestand von einer Periode in die
nächste mitnehmen. Der Netzwerksimplex selbst braucht dafür keine Änderung - er sieht nur
ein größeres, strukturell identisches Min-Cost-Flow-Problem. Bei flacher Nachfrage über
alle Perioden lohnt sich Lagerhaltung nie und das Modell reduziert sich von selbst auf T
unabhängige Ein-Perioden-Probleme; mit einer Nachfrage-Saisonalität (Regler
"Nachfrage-Spitze", Preset "Nachfragespitze") baut der Netzwerksimplex sichtbar Bestand
vor der Spitzen-Periode auf, während die myopische FCFS-Baseline nie vorausschauend plant.

## Methodik

- Zufallsnetzwerk aus Werken (Produktionskosten/-kapazität), Verteilzentren
  (Umschlagkosten/-durchsatz) und Filialen (feste Nachfrage), Transportkosten
  proportional zur euklidischen Distanz - Seed-gesteuert und per Permalink
  reproduzierbar.
- Vier Beispielszenarien: Normalfall, DC-Engpass (erzwingt Notbeschaffung), Knappe
  Werkskapazität (größter Koordinationsgewinn ggü. der FCFS-Baseline) und Nachfragespitze
  (Mehrperioden-Szenario mit Lagerhaltung vor einer Nachfrage-Spitze).
- Sankey-Flussdiagramm je Verfahren und Periode, Lagerbestand-über-Zeit-Diagramm
  (Mehrperioden-Fall), Kostenaufschlüsselung (Produktion/Umschlag/Transport/Lagerhaltung/
  Fehlmenge), Kapazitätsauslastung je Werk/DC, Laufzeitvergleich, PDF-Export, Permalink.
- Korrektheits-Check bei jedem Szenario-Wechsel: eigener Netzwerksimplex vs. OR-Tools
  müssen dieselben Gesamtkosten liefern - auch im Mehrperioden-Fall.

## Dateistruktur

| Datei | Inhalt |
|---|---|
| `app.py` | Streamlit-Hauptablauf (Sidebar, Primäransicht, Tabs) |
| `flow_constants.py` | Default-/Grenzwerte, Beispielszenarien |
| `flow_network.py` | Baut die ProblemInstance (Knoten, Kanten, Kapazitäten, Kosten) inkl. der drei Modellierungs-Kniffe (Knotenkapazität, SRC/SINK-Ausgleich, Zeit-Expansion) |
| `flow_scenario.py` | Zufällige, Seed-gesteuerte Szenariogenerierung inkl. Nachfrage-Saisonalitätskurve |
| `flow_network_simplex.py` | Eigene Netzwerksimplex-Implementierung (Kernstück), unverändert für den Mehrperioden-Fall |
| `flow_naive.py` | FCFS-Baseline (je Filiale güns­tigste verfügbare Route; im Mehrperioden-Fall myopisch, Periode für Periode ohne Lagerhaltung) |
| `flow_reference_solver.py` | Google OR-Tools `SimpleMinCostFlow` als Cross-Check |
| `flow_evaluation.py` | Kostenaufschlüsselung, Kapazitätsauslastung, Lagerbestand je Periode, Vergleichstabelle |
| `flow_visualization.py` | Sankey-Diagramm je Periode, Lagerbestand-über-Zeit, Kostenaufschlüsselung, Auslastung, Laufzeitvergleich (Plotly) |
| `flow_pdf_export.py` | PDF-Distributionsplan (mit Periodenspalte im Mehrperioden-Fall) |
| `flow_presets.py` | Beispielszenarien, Permalink-Logik (`SettingSpec`-Pattern) |
| `tests/` | Netzwerkaufbau-Korrektheit (Ein- und Mehrperioden-Fall), Netzwerksimplex vs. OR-Tools auf Zufallsinstanzen (inkl. Engpass- und Nachfragespitze-Szenarien), Flusserhaltung/Kapazitätseinhaltung für beide Solver, Iterationsgrenze, Lagerhaltungs-Eigenschaften (myopische Baseline nutzt sie nie, flache Nachfrage löst sie nie aus) |

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
