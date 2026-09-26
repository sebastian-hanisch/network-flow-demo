# Distributionsnetzwerk-Optimierung (Min-Cost-Flow, Netzwerksimplex)

**[→ Demo live ausprobieren](https://sebastianhanisch-network-flow-demo.streamlit.app/)**

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
- **Referenz (Google OR-Tools):** `SimpleMinCostFlow` (ein anderes Verfahren: Cost-Scaling-
  Push-Relabel, industriell gehärtet, C++) als unabhängige Gegenprobe - bei jedem Szenario wird
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

## Neu (2026-09-26): mehr Verfahren, Szenario-Vergleich, Schattenpreise

Wie der Netzwerksimplex selbst arbeitet (Basis, Pivot, Preisregeln, Degeneration), zeigt die Konzept-Demo [netzwerksimplex-demo](https://github.com/sebastian-hanisch/netzwerksimplex-demo) (Stück 19 der Netzwerkfluss-Linie). Diese Demo wurde stärker in Richtung Anwendung ausgebaut; alles ist additiv, die bisherigen Kennzahlen und Beispielszenarien sind unverändert. Die neuen Zahlen sind in `tests/test_claims.py` belegt (die vier Beispielszenarien, Normalfall = Seed 7).

**Mehr Verfahren im Vergleich.** Neben der FCFS-Baseline zwei weitere Praxisregeln – **Größte Nachfrage zuerst** (je Periode die Filiale mit der größten Nachfrage zuerst) und **Regional** (das der Filiale nächste DC mit freier Route, dort das billigste Werk; die übliche zweistufige Regel) – und ein dritter exakter Löser: **HiGHS-LP** (`scipy.optimize.linprog`, ein allgemeines LP auf der Inzidenzmatrix, kein Netzwerkverfahren). Die drei exakten Löser (eigener Netzwerksimplex, OR-Tools, HiGHS) liefern in allen vier Beispielszenarien dieselben Kosten (OR-Tools rechnet mit auf 1e-4 gerundeten Kosten).
Mehrkosten gegenüber dem Optimum (FCFS / Größte zuerst / Regional): Normalfall (43 852 €) **3,95 / 4,13 / 2,59 %**; DC-Engpass (68 043 €) 10,13 / **8,34** / 9,24 %; Knappe Werkskapazität (31 877 €) 28,07 / 28,80 / **26,15 %**; Nachfragespitze (197 481 €) **10,37** / 13,16 / 13,15 %. **Keine Regel gewinnt überall:** Regional gewinnt zweimal, Größte Nachfrage zuerst einmal, die billigste Route je Filiale (FCFS) einmal; alle liegen zwischen 2,6 und 28,8 % über dem Optimum.
Ein Laufzeit-Experiment (3 Größenstufen bis 10 Werke, 14 DCs, 60 Filialen: 100 Knoten, 1 124 Kanten, 295 Simplex-Iterationen) zeigt: OR-Tools ist überall am schnellsten, der eigene Simplex wächst mit Iterationen mal Netzgröße (Baum wird je Iteration neu aufgebaut), HiGHS hat einen festen Startaufwand.

**Szenario-Vergleich (What-if).** Aus dem Netz entsteht eine Variante (Verteilzentrum ausbauen, Werk schließen, Werkskapazität aller Werke ändern, Nachfrage ändern, Notbeschaffung verteuern); beide Szenarien werden exakt mit dem Netzwerksimplex gelöst und nebeneinander gestellt (Kosten, Fehlmenge, Kostenaufschlüsselung), optional mit Amortisation einer Investition.
Normalfall (39 Einheiten Fehlmenge): **DC 1 um 50 % ausbauen spart 12 570 € (−28,7 %) und beseitigt die Fehlmenge**; Werk 1 schließen kostet +2 648 € (+6,0 %, Fehlmenge 46); Werkskapazität −20 % nur +114 € (+0,3 %, Fehlmenge unverändert); Nachfrage +20 % +25 049 € (+57,1 %, Fehlmenge 90); Notbeschaffung 100 % teurer +19 500 € = 39 mal 500 (die Fehlmenge bleibt).

**Schattenpreise und Engpässe.** Der Netzwerksimplex liefert Potenziale und reduzierte Kosten; für jede volle Kante ist der Schattenpreis der Wert einer weiteren Einheit Kapazität. Normalfall: die drei größten sind Durchsatz-Engpässe der Verteilzentren – **DC 2 393,93 €, DC 3 380,00 €, DC 1 329,15 €** je Einheit –, danach Werk 3 → DC 1 mit 35,81 €. Sie liegen knapp unter den Strafkosten der Notbeschaffung (500 €) minus der Kosten der Route, die die zusätzliche Einheit nutzen würde, und nie darüber (in allen vier Szenarien unter 500 €).
Gegenprobe: Kapazität + 1 und neu rechnen – bei **19 von 20** geprüften Engpässen (die fünf größten je Szenario) genau gleich; im DC-Engpass spart DC 1 nachgerechnet 345,43 € statt 351,28 € (die Basis wechselt). Knappe Werkskapazität: die Werke 343,24 / 340,29 / 316,82 €; Nachfragespitze: DC 1 in Periode 3 mit 367,38 €.

**Was nicht wie erwartet ausfiel.**
- **„Die billigste Route je Filiale (FCFS) ist die beste Praxisregel“ – widerlegt:** die einfache Regionalregel schlägt sie in zwei von vier Szenarien (zweimal um etwa 1 bis 2 Prozentpunkte); die beste Regel wechselt mit dem Szenario.
- **„Schattenpreis mal Ausbau = Ersparnis“ – nur für die ersten Einheiten:** DC 1 um 50 % (101 auf 152 Einheiten) spart 12 570 €, das sind 246 € je zusätzliche Einheit, der Schattenpreis von DC 1 ist 329 €. Der Wert gilt nur, solange die Basis optimal bleibt.
- **„20 % weniger Werkskapazität tut weh“ – im Normalfall kaum:** +0,3 %; der Engpass sind hier die Verteilzentren, nicht die Werke.

## Dateien (Ergänzungen)

| Datei | Inhalt |
|---|---|
| `flow_naive.py` | jetzt mit Reihenfolge und Routenregel als Parameter (Standard = FCFS unverändert), `solve_rule` für „Größte Nachfrage zuerst“ und „Regional“ |
| `flow_lp_solver.py` | HiGHS-LP (`scipy`) als dritter exakter Löser |
| `flow_variants.py` | Szenario-Varianten über `build_instance` (Ausbau, Schließung, Kapazität, Nachfrage, Strafkosten) |
| `flow_network_simplex.py` | liefert zusätzlich Potenziale, reduzierte Kosten und Status der Basis |
| `flow_evaluation.py` | Vergleichstabelle, Szenario-Kennzahlen, Engpassliste mit Gegenprobe |
| `tests/test_rules.py`, `test_variants.py`, `test_shadow_prices.py`, `test_claims.py`, `test_app_sections.py` | Regeln und LP, Varianten, Schattenpreise, belegte Zahlen, neue App-Abschnitte |

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
