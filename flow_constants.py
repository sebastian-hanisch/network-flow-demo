"""Default-/Grenzwerte und Konfiguration für die Distributionsnetzwerk-Demo."""

# Netzgröße (Regler-Grenzen)
N_PLANTS_RANGE = (2, 6)
N_DCS_RANGE = (2, 5)
N_STORES_RANGE = (4, 14)
N_PLANTS_DEFAULT = 3
N_DCS_DEFAULT = 3
N_STORES_DEFAULT = 8

# Geografie: Werke/DCs/Filialen liegen auf einem Raster [0, MAP_SIZE] x [0, MAP_SIZE],
# Transportkosten pro Einheit sind proportional zur euklidischen Distanz.
MAP_SIZE = 100.0
COST_PER_DISTANCE_UNIT = 1.0

# Werke: Produktionskosten pro Einheit (€) und Produktionskapazität (Einheiten)
PLANT_UNIT_COST_RANGE = (8.0, 20.0)
PLANT_CAPACITY_RANGE = (60, 160)

# Verteilzentren: Umschlagkosten pro Einheit und Durchsatzkapazität
DC_HANDLING_COST_RANGE = (1.0, 4.0)
DC_THROUGHPUT_RANGE = (40, 160)
DC_THROUGHPUT_SLIDER_RANGE = (20, 220)

# Filialen: Nachfrage pro Filiale
STORE_DEMAND_RANGE = (10, 45)

# Kanten-Kapazität Werk->DC bzw. DC->Filiale (z. B. LKW-Ladung je Route und Periode)
LANE_CAPACITY_RANGE = (25, 70)

# Fehlmengen-Strafkosten pro nicht gelieferter Einheit - deutlich teurer als jede reale
# Transport-/Produktionsroute, damit Fehlmengen nur auftreten, wenn eine echte
# Kapazitätsgrenze im Netz keine andere Lösung zulässt (klassischer "künstlicher
# Fehlmengen-Bogen" der Transportproblem-Literatur).
SHORTFALL_PENALTY_PER_UNIT = 500.0

# Mehrperioden-Erweiterung: Verteilzentren können Bestand von einer Periode in die
# nächste mitnehmen (Lagerhaltungskosten pro Einheit und Periode, Lagerkapazität).
# Die Lagerkapazität wird bewusst nicht als eigener Regler geführt, sondern an die
# ohnehin vorhandene Durchsatzkapazität gekoppelt (ein Lager kann typischerweise etwas
# mehr bevorraten, als in einer einzelnen Periode durch es hindurchgeht).
N_PERIODS_RANGE = (1, 6)
N_PERIODS_DEFAULT = 1
DC_HOLDING_COST_RANGE = (0.4, 1.5)
DC_STORAGE_CAPACITY_THROUGHPUT_MULTIPLIER = 1.3

# Nachfrage-Saisonalität über die Perioden: ein glockenförmiger Verlauf um eine
# Spitzen-Periode (standardmäßig die mittlere Periode). Faktor 1.0 = keine Saisonalität
# (flache Nachfrage über alle Perioden, reduziert die Mehrperioden-Erweiterung auf T
# strukturell unabhängige Ein-Perioden-Probleme).
DEMAND_PEAK_MULTIPLIER_RANGE = (1.0, 3.0)
DEMAND_PEAK_MULTIPLIER_DEFAULT = 1.0

COLOR_INVENTORY = "#d97706"

# Big-M für die künstliche Wurzel der Anfangs-Spannbaumlösung des Netzwerksimplex -
# muss jede realistische Kombination aus Kosten und Fluss im Netz dominieren, damit
# künstliche Bögen im Optimum nie mit echten Bögen konkurrieren.
BIG_M_MULTIPLIER = 1000.0

# Sicherheitsgrenze für Simplex-Iterationen (wie GRASP_ITERATIONS o.ä. in den anderen
# Demos: verhindert eine Endlosschleife bei degenerierten Pivotfolgen, wird bei den hier
# betrachteten Netzgrößen nie annähernd erreicht).
MAX_SIMPLEX_ITERATIONS = 20_000

RANDOM_SEED_DEFAULT = 7
RANDOM_SEED_RANGE = (0, 2_000_000_000)

# Farben (konsistent mit den anderen Demos: Blau = optimiert/exakt, Grau = naiv/Baseline,
# Orange/Rot = Engpass/Fehlmenge)
COLOR_PLANT = "#2563eb"
COLOR_DC = "#0f766e"
COLOR_STORE = "#64748b"
COLOR_NAIVE = "#94a3b8"
COLOR_OPTIMAL = "#2563eb"
COLOR_SHORTFALL = "#dc2626"
COLOR_REFERENCE = "#7c3aed"

PRESETS = {
    "Normalfall": dict(
        n_plants=3, n_dcs=3, n_stores=8, dc_throughput_scale=1.0, seed=7,
    ),
    "DC-Engpass": dict(
        n_plants=3, n_dcs=3, n_stores=10, dc_throughput_scale=0.65, seed=11,
    ),
    "Knappe Werkskapazität": dict(
        n_plants=3, n_dcs=3, n_stores=9, dc_throughput_scale=1.0, seed=23,
        plant_capacity_scale=0.82,
    ),
    "Nachfragespitze": dict(
        n_plants=3, n_dcs=3, n_stores=9, dc_throughput_scale=1.0, seed=12,
        n_periods=4, demand_peak_multiplier=1.5,
    ),
}
