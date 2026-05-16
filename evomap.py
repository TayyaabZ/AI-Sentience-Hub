# pyrefly: ignore [missing-import]
"""
EvoMap — Evolutionary Dungeon Generator
Generates 50x50 dungeons using a genetic algorithm.

Tile Legend:
    0 = Wall
    1 = Floor
    2 = Corridor
    3 = Spawn
    4 = Boss
    5 = Treasure
"""

import numpy as np
import random
import copy
from collections import deque

# --- Constants ---
GRID_W, GRID_H = 50, 50
WALL, FLOOR, CORRIDOR, SPAWN, BOSS, TREASURE = 0, 1, 2, 3, 4, 5

ROOM_MIN_SIZE = 4
ROOM_MAX_SIZE = 10
ROOM_COUNT_MIN = 5
ROOM_COUNT_MAX = 12

MUTATION_RATE = 0.05
ELITE_FRACTION = 0.5  # top 50% survive

TREASURE_VALUE = 0.5
STEP_PENALTY = 0.01


# ──────────────────────────────────────────────
# Dungeon generation
# ──────────────────────────────────────────────

def _place_rooms(dungeon):
    """Carve 5-12 random rectangular rooms into the dungeon. Returns list of room rects."""
    rooms = []
    num_rooms = random.randint(ROOM_COUNT_MIN, ROOM_COUNT_MAX)
    attempts = 0

    while len(rooms) < num_rooms and attempts < 300:
        attempts += 1
        w = random.randint(ROOM_MIN_SIZE, ROOM_MAX_SIZE)
        h = random.randint(ROOM_MIN_SIZE, ROOM_MAX_SIZE)
        x = random.randint(1, GRID_W - w - 1)
        y = random.randint(1, GRID_H - h - 1)

        new_room = (x, y, w, h)

        # Check overlap (with 1-tile padding)
        overlap = False
        for (rx, ry, rw, rh) in rooms:
            if (x - 1 < rx + rw and x + w + 1 > rx and
                    y - 1 < ry + rh and y + h + 1 > ry):
                overlap = True
                break

        if not overlap:
            rooms.append(new_room)
            dungeon[y:y + h, x:x + w] = FLOOR

    return rooms


def _connect_rooms(dungeon, rooms):
    """Connect each room to the next with an L-shaped corridor."""
    for i in range(len(rooms) - 1):
        x1, y1, w1, h1 = rooms[i]
        x2, y2, w2, h2 = rooms[i + 1]

        # Center of each room
        cx1, cy1 = x1 + w1 // 2, y1 + h1 // 2
        cx2, cy2 = x2 + w2 // 2, y2 + h2 // 2

        # Randomly pick horizontal-first or vertical-first
        if random.random() < 0.5:
            _carve_h_corridor(dungeon, cx1, cx2, cy1)
            _carve_v_corridor(dungeon, cy1, cy2, cx2)
        else:
            _carve_v_corridor(dungeon, cy1, cy2, cx1)
            _carve_h_corridor(dungeon, cx1, cx2, cy2)


def _carve_h_corridor(dungeon, x1, x2, y):
    """Carve a horizontal corridor between two x coordinates at row y."""
    for x in range(min(x1, x2), max(x1, x2) + 1):
        if 0 <= x < GRID_W and 0 <= y < GRID_H:
            if dungeon[y, x] == WALL:
                dungeon[y, x] = CORRIDOR


def _carve_v_corridor(dungeon, y1, y2, x):
    """Carve a vertical corridor between two y coordinates at column x."""
    for y in range(min(y1, y2), max(y1, y2) + 1):
        if 0 <= x < GRID_W and 0 <= y < GRID_H:
            if dungeon[y, x] == WALL:
                dungeon[y, x] = CORRIDOR


def _place_special_tiles(dungeon, rooms):
    """Place spawn in the first room, boss in the last, and treasure in a random middle room."""
    if len(rooms) < 2:
        return

    # Spawn — center of first room
    sx, sy, sw, sh = rooms[0]
    dungeon[sy + sh // 2, sx + sw // 2] = SPAWN

    # Boss — center of last room
    bx, by, bw, bh = rooms[-1]
    dungeon[by + bh // 2, bx + bw // 2] = BOSS

    # Treasure — center of a random middle room
    if len(rooms) > 2:
        mid = random.choice(rooms[1:-1])
        tx, ty, tw, th = mid
        dungeon[ty + th // 2, tx + tw // 2] = TREASURE


def generate_dungeon():
    """Create a single random dungeon with rooms, corridors, and special tiles."""
    dungeon = np.zeros((GRID_H, GRID_W), dtype=np.int8)
    rooms = _place_rooms(dungeon)
    _connect_rooms(dungeon, rooms)
    _place_special_tiles(dungeon, rooms)
    return dungeon


# ──────────────────────────────────────────────
# Fitness evaluation
# ──────────────────────────────────────────────

def _find_tile(dungeon, tile_type):
    """Return (row, col) of the first occurrence of tile_type, or None."""
    positions = np.argwhere(dungeon == tile_type)
    if len(positions) > 0:
        return tuple(positions[0])
    return None


def _bfs(dungeon, start):
    """BFS from start position. Returns set of all reachable (row, col) walkable tiles."""
    visited = set()
    queue = deque([start])
    visited.add(start)

    while queue:
        r, c = queue.popleft()
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = r + dr, c + dc
            if 0 <= nr < GRID_H and 0 <= nc < GRID_W and (nr, nc) not in visited:
                if dungeon[nr, nc] != WALL:
                    visited.add((nr, nc))
                    queue.append((nr, nc))

    return visited


def _bfs_path_length(dungeon, start, target):
    """BFS shortest path length from start to target. Returns int step count, or None if unreachable."""
    if start is None or target is None:
        return None
    if start == target:
        return 0

    visited = set()
    visited.add(start)
    queue = deque([(start, 0)])

    while queue:
        (r, c), dist = queue.popleft()
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = r + dr, c + dc
            if 0 <= nr < GRID_H and 0 <= nc < GRID_W and (nr, nc) not in visited:
                if dungeon[nr, nc] != WALL:
                    if (nr, nc) == target:
                        return dist + 1
                    visited.add((nr, nc))
                    queue.append(((nr, nc), dist + 1))

    return None


def get_path_through(dungeon, waypoints):
    """
    Returns a continuous path list [(row, col), ...] that passes
    through each waypoint in order, using BFS for each segment.
    Returns [] if any segment is unreachable.

    Example: get_path_through(dungeon, [spawn, treasure, boss])
    returns the full path spawn→treasure→boss concatenated.
    """
    if len(waypoints) < 2:
        return list(waypoints)

    def bfs_segment(start, end):
        if start is None or end is None:
            return None
        if start == end:
            return [start]
        visited = {start}
        queue = deque([(start, [start])])
        while queue:
            (r, c), path = queue.popleft()
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nr, nc = r + dr, c + dc
                if (0 <= nr < GRID_H and 0 <= nc < GRID_W
                        and (nr, nc) not in visited
                        and dungeon[nr, nc] != WALL):
                    new_path = path + [(nr, nc)]
                    if (nr, nc) == end:
                        return new_path
                    visited.add((nr, nc))
                    queue.append(((nr, nc), new_path))
        return None

    full_path = []
    for i in range(len(waypoints) - 1):
        seg = bfs_segment(waypoints[i], waypoints[i + 1])
        if seg is None:
            return []
        if full_path:
            full_path.extend(seg[1:])  # skip duplicate waypoint
        else:
            full_path.extend(seg)

    return full_path


def _count_dead_ends(dungeon):
    """Count corridor/floor tiles that have exactly one walkable neighbour."""
    walkable = (dungeon != WALL).astype(np.int8)
    neighbours = (np.roll(walkable, 1, 0) + np.roll(walkable, -1, 0) +
                  np.roll(walkable, 1, 1) + np.roll(walkable, -1, 1))
    return int(np.sum((walkable == 1) & (neighbours == 1)))


def _count_rooms(dungeon):
    """
    Count contiguous FLOOR regions (>= 4 tiles). Tries scipy for O(n) speed;
    falls back to BFS if scipy is unavailable.
    """
    try:
        from scipy.ndimage import label as ndlabel
        floor_mask = (dungeon == FLOOR).astype(np.int8)
        labeled, num_features = ndlabel(floor_mask)
        count = 0
        for region_id in range(1, num_features + 1):
            if np.sum(labeled == region_id) >= 4:
                count += 1
        return count
    except ImportError:
        # BFS fallback
        visited = set()
        room_count = 0
        for r in range(GRID_H):
            for c in range(GRID_W):
                if dungeon[r, c] == FLOOR and (r, c) not in visited:
                    queue = deque([(r, c)])
                    visited.add((r, c))
                    region_size = 0
                    while queue:
                        cr, cc = queue.popleft()
                        region_size += 1
                        for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
                            nr, nc = cr+dr, cc+dc
                            if (0 <= nr < GRID_H and 0 <= nc < GRID_W
                                    and (nr, nc) not in visited
                                    and dungeon[nr, nc] == FLOOR):
                                visited.add((nr, nc))
                                queue.append((nr, nc))
                    if region_size >= 4:
                        room_count += 1
        return room_count


def fitness_score(dungeon):
    """
    Evaluate dungeon quality.

    score = (reachable / total_walkable) + room_count * 0.1 − dead_ends * 0.05

    Returns 0 if no path exists from spawn to boss.
    """
    spawn_pos = _find_tile(dungeon, SPAWN)
    boss_pos = _find_tile(dungeon, BOSS)

    if spawn_pos is None or boss_pos is None:
        return 0.0

    reachable = _bfs(dungeon, spawn_pos)

    # No path to boss → instant zero
    if boss_pos not in reachable:
        return 0.0

    total_walkable = int(np.count_nonzero(dungeon))
    if total_walkable == 0:
        return 0.0

    reachability = len(reachable) / total_walkable
    room_count = _count_rooms(dungeon)
    dead_ends = _count_dead_ends(dungeon)

    score = reachability + room_count * 0.1 - dead_ends * 0.05

    # Treasure cost-benefit scoring — rewards treasure ON or NEAR the main path.
    # Detour = extra steps a player must walk to collect treasure vs skipping it.
    # detour = (spawn→treasure) + (treasure→boss) − (spawn→boss)
    # bonus  = max(0, TREASURE_VALUE − detour × STEP_PENALTY)
    # detour=0 means treasure sits on the direct path → full +0.5 bonus.
    treasure_pos = _find_tile(dungeon, TREASURE)
    if treasure_pos is not None:
        spawn_to_treasure = _bfs_path_length(dungeon, spawn_pos, treasure_pos)
        treasure_to_boss  = _bfs_path_length(dungeon, treasure_pos, boss_pos)
        spawn_to_boss     = _bfs_path_length(dungeon, spawn_pos, boss_pos)
        if (spawn_to_treasure is not None
                and treasure_to_boss is not None
                and spawn_to_boss is not None
                and spawn_to_boss > 0):
            detour = (spawn_to_treasure + treasure_to_boss) - spawn_to_boss
            treasure_bonus = max(0.0, TREASURE_VALUE - detour * STEP_PENALTY)
        else:
            treasure_bonus = 0.0
    else:
        treasure_bonus = 0.0
    score += treasure_bonus

    return max(score, 0.0)


# ──────────────────────────────────────────────
# Genetic algorithm operators
# ──────────────────────────────────────────────

def _selection(population, scores):
    """Keep the top 50% of the population by fitness."""
    paired = list(zip(scores, population))
    paired.sort(key=lambda x: x[0], reverse=True)
    cutoff = max(2, int(len(paired) * ELITE_FRACTION))
    return [ind for _, ind in paired[:cutoff]]


def _crossover(parent_a, parent_b):
    """Tile-row splice crossover: take a random contiguous band of rows from parent_b."""
    child = parent_a.copy()
    cut1 = random.randint(0, GRID_H - 2)
    cut2 = random.randint(cut1 + 1, GRID_H)
    child[cut1:cut2, :] = parent_b[cut1:cut2, :]
    return child


def _mutate(dungeon):
    """Randomly flip wall↔floor tiles at the mutation rate."""
    mutated = dungeon.copy()
    mask = np.random.random((GRID_H, GRID_W)) < MUTATION_RATE
    special = np.isin(mutated, [SPAWN, BOSS, TREASURE])
    mutated[mask & ~special & (mutated == WALL)] = FLOOR
    mutated[mask & ~special & (mutated != WALL)] = WALL
    return mutated


def _repair(dungeon):
    """
    Post-crossover / mutation repair pass.
    Ensures exactly one spawn, one boss, and one treasure tile exist.
    If any are missing, re-places them deterministically.
    """
    repaired = dungeon.copy()

    # Ensure spawn exists
    if _find_tile(repaired, SPAWN) is None:
        candidates = np.argwhere(repaired == FLOOR)
        if len(candidates) > 0:
            r, c = candidates[0]
            repaired[r, c] = SPAWN

    # Ensure boss exists
    if _find_tile(repaired, BOSS) is None:
        candidates = np.argwhere(repaired == FLOOR)
        if len(candidates) > 0:
            r, c = candidates[-1]
            repaired[r, c] = BOSS

    # Ensure treasure exists — place in a random floor tile
    # that is not spawn and not boss and not already treasure
    if _find_tile(repaired, TREASURE) is None:
        spawn_pos = _find_tile(repaired, SPAWN)
        boss_pos  = _find_tile(repaired, BOSS)
        excluded  = set()
        if spawn_pos: excluded.add(spawn_pos)
        if boss_pos:  excluded.add(boss_pos)
        candidates = [
            (r, c) for r, c in map(tuple, np.argwhere(repaired == FLOOR))
            if (r, c) not in excluded
        ]
        if candidates:
            # Pick a tile roughly in the middle of the dungeon for variety
            mid_idx = len(candidates) // 2
            r, c = candidates[mid_idx]
            repaired[r, c] = TREASURE

    return repaired


def evolve(population_size=30, generations=60, progress_callback=None, seed=None):
    """
    Run the evolutionary algorithm.

    Args:
        population_size: Number of dungeons per generation.
        generations: How many generations to run.
        progress_callback: Optional callable(gen) invoked each generation.
        seed: Optional int for reproducible runs.

    Returns:
        dict with keys:
            best_per_gen: List of (dungeon, score) tuples — the best dungeon from each generation.
            final_treasure_steps: int or None — steps from spawn to treasure in the best dungeon of the final generation.
    """
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)

    # Seed the initial population
    population = [generate_dungeon() for _ in range(population_size)]
    best_per_gen = []

    for gen in range(generations):
        # Score everyone
        scores = [fitness_score(d) for d in population]

        # Track the best
        best_idx = int(np.argmax(scores))
        best_per_gen.append((population[best_idx].copy(), scores[best_idx]))

        # Report progress
        if progress_callback is not None:
            progress_callback(gen + 1)

        # Selection — keep the elite
        survivors = _selection(population, scores)

        # Breed the next generation
        next_gen = [s.copy() for s in survivors]  # elites carry forward

        while len(next_gen) < population_size:
            p1, p2 = random.sample(survivors, 2)
            child = _crossover(p1, p2)
            child = _mutate(child)
            child = _repair(child)
            next_gen.append(child)

        population = next_gen

    # Compute treasure steps for the best dungeon of the final generation
    final_dungeon = best_per_gen[-1][0] if best_per_gen else None
    if final_dungeon is not None:
        spawn_pos = _find_tile(final_dungeon, SPAWN)
        treasure_pos = _find_tile(final_dungeon, TREASURE)
        steps_to_treasure_of_best = _bfs_path_length(final_dungeon, spawn_pos, treasure_pos)
    else:
        steps_to_treasure_of_best = None

    return {"best_per_gen": best_per_gen, "final_treasure_steps": steps_to_treasure_of_best}


# ──────────────────────────────────────────────
# Standalone test
# ──────────────────────────────────────────────

if __name__ == "__main__":
    print("EvoMap — Evolutionary Dungeon Generator")
    print("=" * 40)
    print(f"Grid: {GRID_W}x{GRID_H}")
    print(f"Running evolution: 30 individuals, 60 generations...")
    print()

    results = evolve(population_size=30, generations=60)

    # Print generation progression
    for i, (dungeon, score) in enumerate(results["best_per_gen"]):
        bar = "#" * int(score * 4)
        print(f"  Gen {i + 1:3d}  |  fitness: {score:6.3f}  {bar}")

    # Show the final best dungeon as ASCII
    best_dungeon, best_score = results["best_per_gen"][-1]
    tile_chars = {WALL: "##", FLOOR: "  ", CORRIDOR: "..", SPAWN: "SP", BOSS: "BO", TREASURE: "$$"}

    print()
    print(f"Best dungeon (fitness {best_score:.3f}):")
    for row in best_dungeon:
        print("".join(tile_chars.get(t, "??") for t in row))
