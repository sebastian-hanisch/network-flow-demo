"""Eigene Implementierung des Netzwerksimplex-Algorithmus für Min-Cost-Flow -
Kernstück dieser Demo (Neuimplementierung eines Verfahrens, das im Mathematischen
Praktikum ursprünglich in einer anderen Sprache entstand).

Klassisches Verfahren (siehe Ahuja/Magnanti/Orlin, "Network Flows", Kap. 11, oder
Bazaraa/Jarvis/Sherali, "Linear Programming and Network Flows"): Jede Basislösung
eines Min-Cost-Flow-Problems entspricht einem Spannbaum über alle Knoten. Ein
Pivot-Schritt tauscht genau einen Bogen im Spannbaum gegen einen Nicht-Baum-Bogen -
dadurch werden weder Tableau-Zeilen noch -Spalten explizit geführt, nur
Spannbaum-Struktur und Knotenpotentiale, was den Netzwerksimplex in der Praxis um
Größenordnungen schneller macht als generischer (Tableau-)Simplex auf derselben
Kanten-Knoten-Inzidenzmatrix.

Ablauf:
1. Startlösung (Phase 1) über einen künstlichen Wurzelknoten: jeder echte Knoten
   erhält einen künstlichen Bogen zur Wurzel mit Kosten M (>> alle echten Kosten),
   der genau den nötigen Ausgleichsfluss trägt ("Big-M-Methode"). Das ist immer ein
   gültiger Spannbaum, unabhängig vom Netzwerk.
2. Pivotisieren: solange ein Nicht-Baum-Bogen die Optimalitätsbedingung verletzt
   (reduzierte Kosten < 0 an der unteren bzw. > 0 an der oberen Schranke), wird er
   zum eintretenden Bogen. Er schließt zusammen mit dem Baumpfad zwischen seinen
   Endknoten einen eindeutigen Kreis; der Fluss wird entlang dieses Kreises maximal
   verschoben, bis ein Baumbogen seine Schranke erreicht (= austretender Bogen).
3. Terminiert, wenn kein Nicht-Baum-Bogen mehr verletzt ist (Optimum) - Big-M sorgt
   dafür, dass künstliche Bögen dabei auf Fluss 0 gedrückt werden, sofern das
   Netzwerk (wie hier per Konstruktion immer) ohne sie lösbar ist.

Für die hier betrachteten Netzgrößen (~15-60 Knoten) wird die Baumstruktur bei
jedem Pivot-Schritt komplett neu aus der aktuellen Bogenmenge aufgebaut (BFS von der
Wurzel, O(Knoten+Bögen) je Iteration) statt sie inkrementell fortzuschreiben (z. B.
über Thread-/Tiefen-Indizes wie in industriellen Implementierungen) - für diese
Größenordnung im Millisekundenbereich ohne spürbaren Laufzeitnachteil, dafür deutlich
weniger fehleranfällig.
"""

from collections import namedtuple

import flow_constants as C

_SArc = namedtuple("_SArc", ["idx", "tail", "head", "cost", "capacity"])

EPS = 1e-7
ARTIFICIAL_CAPACITY = 1e12


class NetworkSimplexResult:
    def __init__(self, flow, cost, iterations, feasible, artificial_flow):
        self.flow = flow  # dict: real Arc.idx -> Flusswert
        self.cost = cost  # Gesamtkosten über alle echten Bögen
        self.iterations = iterations
        self.feasible = feasible
        self.artificial_flow = artificial_flow  # sollte 0 sein, sonst Warnsignal


def _build_tree_structure(root, tree_adjacency):
    """BFS von der Wurzel: liefert parent[node] = (Vorgänger, Bogen) und
    Knotenpotentiale (reduzierte Kosten aller Baumbögen = 0)."""
    parent = {root: None}
    potential = {root: 0.0}
    order = [root]
    frontier = [root]
    while frontier:
        nxt = []
        for x in frontier:
            for (y, arc) in tree_adjacency[x]:
                if y in parent:
                    continue
                parent[y] = (x, arc)
                if arc.tail == x and arc.head == y:
                    potential[y] = potential[x] - arc.cost
                else:
                    potential[y] = potential[x] + arc.cost
                order.append(y)
                nxt.append(y)
        frontier = nxt
    return parent, potential, order


def _path_to_root(node, parent):
    path = [node]
    while parent[path[-1]] is not None:
        path.append(parent[path[-1]][0])
    return path


def _find_cycle(u, v, parent):
    """Findet den (eindeutigen) Baumpfad zwischen u und v über den gemeinsamen
    Vorfahren (LCA) - bildet zusammen mit dem eintretenden Bogen u->v den Kreis."""
    path_u = _path_to_root(u, parent)
    path_v = _path_to_root(v, parent)
    set_u = set(path_u)
    lca = next(n for n in path_v if n in set_u)
    path_u = path_u[: path_u.index(lca) + 1]
    path_v = path_v[: path_v.index(lca) + 1]
    return lca, path_u, path_v


def solve_network_simplex(instance, max_iterations=None):
    max_iterations = max_iterations or C.MAX_SIMPLEX_ITERATIONS
    real_arcs = {a.idx: _SArc(a.idx, a.tail, a.head, a.cost, a.capacity) for a in instance.arcs}
    supply = dict(instance.supply)

    root = "__ROOT__"
    big_m = 1.0 + C.BIG_M_MULTIPLIER * max((a.cost for a in real_arcs.values()), default=1.0) * (len(instance.nodes) + 1)

    flow = {idx: 0.0 for idx in real_arcs}
    artificial = {}
    next_idx = (max(real_arcs) + 1) if real_arcs else 0
    # Bilanzkonvention hier: (Abfluss - Zufluss)(v) = b(v). Ein Angebotsknoten
    # (b(v) >= 0) braucht also einen künstlichen ABFLUSS v->root von genau b(v),
    # ein Nachfrageknoten (b(v) < 0) einen künstlichen ZUFLUSS root->v von -b(v).
    for v in instance.nodes:
        b = supply.get(v, 0.0)
        if b >= 0:
            a = _SArc(next_idx, v, root, big_m, ARTIFICIAL_CAPACITY)
            flow[next_idx] = b
        else:
            a = _SArc(next_idx, root, v, big_m, ARTIFICIAL_CAPACITY)
            flow[next_idx] = -b
        artificial[next_idx] = a
        next_idx += 1

    all_arcs = {**real_arcs, **artificial}
    tree_set = set(artificial.keys())
    status = {idx: "L" for idx in real_arcs}  # Nicht-Baum-Status; nur für echte Bögen relevant

    iterations = 0
    feasible = True
    while True:
        tree_adjacency = {v: [] for v in instance.nodes}
        tree_adjacency[root] = []
        for idx in tree_set:
            a = all_arcs[idx]
            tree_adjacency[a.tail].append((a.head, a))
            tree_adjacency[a.head].append((a.tail, a))

        parent, potential, _ = _build_tree_structure(root, tree_adjacency)

        entering_idx = None
        entering_dir = 1
        best_violation = EPS
        for idx, st in status.items():
            a = all_arcs[idx]
            rc = a.cost - potential[a.tail] + potential[a.head]
            if st == "L" and rc < -best_violation:
                best_violation = -rc
                entering_idx = idx
                entering_dir = 1
            elif st == "U" and rc > best_violation:
                best_violation = rc
                entering_idx = idx
                entering_dir = -1

        if entering_idx is None:
            break

        iterations += 1
        if iterations > max_iterations:
            feasible = False
            break

        entering = all_arcs[entering_idx]
        u, v = entering.tail, entering.head
        lca, path_u, path_v = _find_cycle(u, v, parent)

        # Kreis-Schritte unter der Annahme entering_dir == +1 aufbauen (u->v->...->LCA->...->u);
        # bei entering_dir == -1 wird die Richtung aller Schritte am Ende umgedreht.
        steps = []  # (arc, is_forward_structural)
        for i in range(len(path_v) - 1):
            x, y = path_v[i], path_v[i + 1]
            a = tree_adjacency_arc(parent, x)
            steps.append((a, a.tail == x and a.head == y))
        rev_u = list(reversed(path_u))
        for i in range(len(rev_u) - 1):
            x, y = rev_u[i], rev_u[i + 1]
            a = tree_adjacency_arc(parent, y)
            steps.append((a, a.tail == x and a.head == y))

        cycle_arcs = [(entering, True)] + steps
        if entering_dir == -1:
            cycle_arcs = [(a, not fwd) for a, fwd in cycle_arcs]

        theta = None
        leaving_idx = None
        leaving_hits_upper = None
        for a, is_forward in cycle_arcs:
            limit = (a.capacity - flow[a.idx]) if is_forward else flow[a.idx]
            better = theta is None or limit < theta - 1e-9
            tied_but_smaller_idx = theta is not None and abs(limit - theta) <= 1e-9 and a.idx < leaving_idx
            if better or tied_but_smaller_idx:
                theta = limit
                leaving_idx = a.idx
                leaving_hits_upper = is_forward
        theta = max(theta, 0.0)

        for a, is_forward in cycle_arcs:
            flow[a.idx] += theta if is_forward else -theta

        if leaving_idx == entering_idx:
            status[entering_idx] = "U" if entering_dir == 1 else "L"
        else:
            tree_set.discard(leaving_idx)
            tree_set.add(entering_idx)
            status.pop(entering_idx, None)
            if leaving_idx in real_arcs:
                status[leaving_idx] = "U" if leaving_hits_upper else "L"

    artificial_flow = sum(flow[idx] for idx in artificial)
    if artificial_flow > 1e-4:
        feasible = False

    real_flow = {idx: max(0.0, flow[idx]) for idx in real_arcs}
    cost = sum(real_arcs[idx].cost * real_flow[idx] for idx in real_arcs)
    return NetworkSimplexResult(real_flow, cost, iterations, feasible, artificial_flow)


def tree_adjacency_arc(parent, node):
    return parent[node][1]
