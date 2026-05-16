import sys
import math
import ctypes
import threading
import time
from collections import deque
import pygame
import numpy as np
import theme
import evomap

try:
    ctypes.windll.user32.SetProcessDPIAware()
except AttributeError:
    pass

evolution_progress = 0

def C(hex_str):
    return pygame.Color(hex_str)

def main():
    global evolution_progress

    pygame.init()
    WIDTH, HEIGHT = 900, 700
    screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.NOFRAME | pygame.SCALED)
    pygame.display.set_caption("EvoMap — Evolutionary Dungeon Generator")
    clock = pygame.time.Clock()

    # ── Thread safety ─────────────────────────────────────────
    _evo_lock = threading.Lock()

    # ── Evolution state ───────────────────────────────────────
    evolution_results   = []      # List of (dungeon, score) per generation
    is_evolving         = False
    evo_start_time      = 0.0     # time.time() when last run started
    evo_elapsed         = 0.0     # seconds, updated each frame during evolution

    # ── Playback state ────────────────────────────────────────
    playback_gen        = -1      # which generation is currently displayed (-1 = none)
    is_paused           = False
    is_manual_scrub     = False   # True when user is using arrow keys
    playback_interval   = 1/30    # seconds per generation step (30 gen/sec default)
    playback_timer      = 0.0     # last time playback advanced a generation

    # ── BFS trail state ───────────────────────────────────────
    path_trail          = []      # list of (row, col) from spawn to boss
    path_index          = 0       # how far along the trail is drawn
    trail_timer         = 0.0     # separate timer for trail animation

    # ── Per-generation caches (avoid recomputing each frame) ──
    rooms_cache         = {}      # gen_index -> int room count
    spawn_screen_cache  = {}      # gen_index -> (px, py) on screen
    boss_screen_cache   = {}      # gen_index -> (px, py) on screen
    treasure_screen_cache = {}    # gen_index -> (px, py) or None
    treasure_cache_steps  = {}      # gen_index -> int steps spawn→treasure, or None
    treasure_cache_bonus  = {}      # gen_index -> float bonus using detour formula
    path_len_cache        = {}      # gen_index -> int path length (lazy, computed first time gen is viewed)

    # ── Dungeon surface cache (pre-render, blit each frame) ───
    dungeon_surface     = None    # pygame.Surface of rendered grid
    surface_gen         = -2      # which gen the surface was rendered for

    # ── Flash / transition effects ────────────────────────────
    complete_flash      = 0       # countdown frames (60 = 1 sec) for completion flash
    gen_flash           = 0       # countdown frames (8) for per-gen transition flash

    # ── Playback speed state ──────────────────────────────────
    SPEEDS = [("½×", 1/15), ("1×", 1/30), ("2×", 1/60), ("⚡", 0.0)]
    speed_idx = 1  # default "1×"

    class Slider:
        def __init__(self, x, y, w, h, min_val, max_val, initial, label):
            self.rect = pygame.Rect(x, y, w, h)
            self.min_val = min_val
            self.max_val = max_val
            self.val = initial
            self.label = label
            self.dragging = False

        def draw(self, surface):
            # Draw background track
            pygame.draw.rect(surface, C(theme.COLORS["BORDER"]), self.rect, border_radius=self.rect.height//2)
            # Draw fill track
            pct = (self.val - self.min_val) / (self.max_val - self.min_val)
            fill_w = max(self.rect.height, int(pct * self.rect.width))
            fill_rect = pygame.Rect(self.rect.x, self.rect.y, fill_w, self.rect.height)
            pygame.draw.rect(surface, C(theme.COLORS["BLUE"]), fill_rect, border_radius=self.rect.height//2)

            # Draw Label
            font = theme.get_font(12)
            val_str = f"{int(self.val)}%" if "Rate" in self.label else str(int(self.val))
            lbl_surf = font.render(f"{self.label}: {val_str}", True, C(theme.COLORS["TEXT_PRIMARY"]))
            lbl_rect = lbl_surf.get_rect(midbottom=(self.rect.centerx, self.rect.top - 6))
            surface.blit(lbl_surf, lbl_rect)

        def handle_event(self, event):
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                click_rect = self.rect.inflate(0, 20)
                if click_rect.collidepoint(event.pos):
                    self.dragging = True
                    self.update_val(event.pos[0])
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                self.dragging = False
            elif event.type == pygame.MOUSEMOTION and self.dragging:
                self.update_val(event.pos[0])

        def update_val(self, mx):
            rel_x = max(0, min(mx - self.rect.x, self.rect.width))
            pct = rel_x / self.rect.width
            self.val = self.min_val + pct * (self.max_val - self.min_val)

    sliders = {
        "mutation":   Slider(30,  675, 150, 8, 0,  20, 5,  "Mutation Rate"),
        "population": Slider(220, 675, 150, 8, 10, 100, 30, "Population"),
        "rooms":      Slider(410, 675, 150, 8, 5,  15, 8,  "Target Rooms"),
    }

    btn_run_rect   = pygame.Rect(630, 580, 260, 36)
    btn_back_rect  = pygame.Rect(630, 648, 260, 32)

    # Four speed buttons — 61px wide each, below progress bar
    speed_btn_rects = []
    for i, (label, _) in enumerate(SPEEDS):
        speed_btn_rects.append(pygame.Rect(630 + i * 65, 626, 60, 20))

    def run_evolution():
        nonlocal is_evolving, evolution_results, evo_elapsed
        global evolution_progress

        evolution_progress = 0

        evomap.MUTATION_RATE  = int(sliders["mutation"].val) / 100.0
        evomap.ROOM_COUNT_MIN = int(sliders["rooms"].val)
        evomap.ROOM_COUNT_MAX = int(sliders["rooms"].val)
        pop_size = int(sliders["population"].val)

        def _on_progress(gen):
            global evolution_progress
            evolution_progress = gen

        results_dict = evomap.evolve(
            population_size=pop_size,
            generations=60,
            progress_callback=_on_progress,
        )
        results = results_dict["best_per_gen"]

        with _evo_lock:
            evolution_results = results
            is_evolving       = False

        sm = theme.StatsManager()
        sm.increment("dungeons_generated")

    def get_shortest_path(dungeon):
        """
        Returns the BFS shortest path from SPAWN to BOSS.
        If the treasure is on an optimal path (detour == 0),
        forces the route through the treasure tile so the
        visual trail matches the score calculation.
        Returns list of (row, col) tuples.
        """
        spawn = evomap._find_tile(dungeon, evomap.SPAWN)
        boss  = evomap._find_tile(dungeon, evomap.BOSS)
        if spawn is None or boss is None:
            return []

        treasure = evomap._find_tile(dungeon, evomap.TREASURE)

        # Check if routing through treasure costs zero extra steps
        if treasure is not None:
            s2t = evomap._bfs_path_length(dungeon, spawn, treasure)
            t2b = evomap._bfs_path_length(dungeon, treasure, boss)
            s2b = evomap._bfs_path_length(dungeon, spawn, boss)
            if (s2t is not None and t2b is not None and s2b is not None
                    and s2b > 0 and (s2t + t2b) == s2b):
                # Treasure is on an optimal path — force routing through it
                forced = evomap.get_path_through(dungeon, [spawn, treasure, boss])
                if forced:
                    return forced

        # Default: plain BFS from spawn to boss
        queue   = deque([(spawn, [spawn])])
        visited = {spawn}
        while queue:
            (r, c), path = queue.popleft()
            if (r, c) == boss:
                return path
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nr, nc = r + dr, c + dc
                if 0 <= nr < evomap.GRID_H and 0 <= nc < evomap.GRID_W:
                    if (nr, nc) not in visited and dungeon[nr, nc] != evomap.WALL:
                        visited.add((nr, nc))
                        queue.append(((nr, nc), path + [(nr, nc)]))
        return []

    CELL = 12  # pixels per tile

    WALL_COLOR     = C("#333333")
    FLOOR_COLOR    = C("#AAAAAA")
    CORRIDOR_COLOR = C("#777777")
    SPAWN_COLOR    = C(theme.COLORS["GREEN"])
    BOSS_COLOR     = C("#8B0000")
    TREASURE_COLOR = C("#FFD700")
    PATH_COLOR     = C("#00FFFF")

    TILE_COLORS = {
        evomap.WALL:     WALL_COLOR,
        evomap.FLOOR:    FLOOR_COLOR,
        evomap.CORRIDOR: CORRIDOR_COLOR,
        evomap.SPAWN:    SPAWN_COLOR,
        evomap.BOSS:     BOSS_COLOR,
        evomap.TREASURE: TREASURE_COLOR,
    }

    def draw_dungeon_to_surface(dungeon):
        """Pre-render dungeon to a Surface. Returns the Surface."""
        surf = pygame.Surface((evomap.GRID_W * CELL, evomap.GRID_H * CELL))
        surf.fill(C("#111111"))
        for r in range(evomap.GRID_H):
            for c in range(evomap.GRID_W):
                color = TILE_COLORS.get(int(dungeon[r, c]), C("#000000"))
                pygame.draw.rect(surf, color,
                                 (c * CELL, r * CELL, CELL, CELL))
        return surf

    GRID_X, GRID_Y = 20, 60

    def tile_to_screen(row, col):
        return (GRID_X + col * CELL + CELL // 2,
                GRID_Y + row * CELL + CELL // 2)

    def is_converged(results, window=10, threshold=0.005):
        if len(results) < window + 1:
            return False
        recent = [r[1] for r in results[-window:]]
        return (max(recent) - min(recent)) < threshold

    running = True
    while running:
        now = time.time()
        mx, my = pygame.mouse.get_pos()

        with _evo_lock:
            local_results    = list(evolution_results)
            local_is_evolving = is_evolving

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if pygame.Rect(11, 8, 14, 14).collidepoint(mx, my):
                    running = False

                if btn_run_rect.collidepoint(event.pos) and not local_is_evolving:
                    with _evo_lock:
                        is_evolving      = True
                        evolution_results = []
                    playback_gen     = -1
                    path_trail       = []
                    path_index       = 0
                    is_paused        = False
                    is_manual_scrub  = False
                    rooms_cache.clear()
                    spawn_screen_cache.clear()
                    boss_screen_cache.clear()
                    treasure_screen_cache.clear()
                    treasure_cache_steps.clear()
                    treasure_cache_bonus.clear()
                    path_len_cache.clear()
                    evo_start_time   = now
                    evolution_progress = 0
                    threading.Thread(target=run_evolution, daemon=True).start()

                for i, btn_rect in enumerate(speed_btn_rects):
                    if btn_rect.collidepoint(event.pos):
                        speed_idx = i
                        playback_interval = SPEEDS[i][1]
                        if i == 3 and len(local_results) > 0:
                            playback_gen = len(local_results) - 1
                            path_trail   = get_shortest_path(local_results[-1][0])
                            path_index   = len(path_trail) - 1

                if btn_back_rect.collidepoint(event.pos):
                    sys.exit(0)

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    sys.exit(0)
                if event.key == pygame.K_SPACE and not local_is_evolving:
                    if len(local_results) == 0:
                        if not local_is_evolving:
                            with _evo_lock:
                                is_evolving = True
                                evolution_results = []
                            playback_gen = -1
                            path_trail   = []
                            rooms_cache.clear()
                            treasure_cache_steps.clear()
                            treasure_cache_bonus.clear()
                            evo_start_time = now
                            threading.Thread(target=run_evolution, daemon=True).start()
                    else:
                        is_paused = not is_paused
                        is_manual_scrub = False

                if event.key == pygame.K_r and len(local_results) > 0 and not local_is_evolving:
                    playback_gen    = 0
                    path_trail      = []
                    path_index      = 0
                    is_paused       = False
                    is_manual_scrub = False
                    playback_timer  = now

                if event.key == pygame.K_LEFT and len(local_results) > 0 and not local_is_evolving:
                    playback_gen    = max(0, playback_gen - 1)
                    path_trail      = []
                    path_index      = 0
                    is_manual_scrub = True

                if event.key == pygame.K_RIGHT and len(local_results) > 0 and not local_is_evolving:
                    new_gen = min(len(local_results) - 1, playback_gen + 1)
                    if new_gen != playback_gen:
                        playback_gen    = new_gen
                        is_manual_scrub = True
                        if playback_gen == len(local_results) - 1:
                            path_trail  = get_shortest_path(local_results[-1][0])
                            path_index  = 0

            for s in sliders.values():
                s.handle_event(event)

        if local_is_evolving:
            evo_elapsed = now - evo_start_time

        if (not local_is_evolving
                and not is_paused
                and not is_manual_scrub
                and len(local_results) > 0
                and playback_gen < len(local_results) - 1):
            interval = playback_interval
            if interval == 0.0:
                playback_gen = len(local_results) - 1
            elif now - playback_timer >= interval:
                playback_gen  += 1
                playback_timer = now
                gen_flash      = 8
                if playback_gen == len(local_results) - 1:
                    path_trail  = get_shortest_path(local_results[-1][0])
                    path_index  = 0
                    trail_timer = now
                    complete_flash = 60

        if path_trail and path_index < len(path_trail) - 1:
            if now - trail_timer >= 1/60:
                path_index += 1
                trail_timer = now

        if (playback_gen >= 0
                and playback_gen < len(local_results)
                and playback_gen not in rooms_cache):
            d, _ = local_results[playback_gen]
            rooms_cache[playback_gen] = evomap._count_rooms(d)

            sp = evomap._find_tile(d, evomap.SPAWN)
            bs = evomap._find_tile(d, evomap.BOSS)
            tr = evomap._find_tile(d, evomap.TREASURE)
            spawn_screen_cache[playback_gen]    = tile_to_screen(*sp) if sp else None
            boss_screen_cache[playback_gen]     = tile_to_screen(*bs) if bs else None
            treasure_screen_cache[playback_gen] = tile_to_screen(*tr) if tr else None

            # Cache treasure detour stats so they are never recomputed in the render loop
            if sp and tr and bs:
                s2t = evomap._bfs_path_length(d, sp, tr)
                t2b = evomap._bfs_path_length(d, tr, bs)
                s2b = evomap._bfs_path_length(d, sp, bs)
                if s2t is not None and t2b is not None and s2b is not None and s2b > 0:
                    detour = (s2t + t2b) - s2b
                    treasure_cache_steps[playback_gen]  = s2t
                    treasure_cache_bonus[playback_gen]  = max(
                        0.0, evomap.TREASURE_VALUE - detour * evomap.STEP_PENALTY
                    )
                else:
                    treasure_cache_steps[playback_gen] = None
                    treasure_cache_bonus[playback_gen]  = 0.0
            else:
                treasure_cache_steps[playback_gen] = None
                treasure_cache_bonus[playback_gen]  = 0.0

            # Cache BFS path length for this generation
            if playback_gen not in path_len_cache:
                quick_path = get_shortest_path(d)
                path_len_cache[playback_gen] = len(quick_path) if quick_path else 0

        if (playback_gen >= 0
                and playback_gen < len(local_results)
                and playback_gen != surface_gen):
            dungeon, _ = local_results[playback_gen]
            dungeon_surface = draw_dungeon_to_surface(dungeon)
            surface_gen     = playback_gen

        if complete_flash > 0:
            complete_flash -= 1
        if gen_flash > 0:
            gen_flash -= 1

        screen.fill(C(theme.COLORS["BG"]))
        theme.draw_window_bar(screen, WIDTH, title="EvoMap — Evolutionary Dungeon Generator")
        grid_rect = pygame.Rect(GRID_X, GRID_Y, 600, 600)
        pygame.draw.rect(screen, C(theme.COLORS["SURFACE"]), grid_rect)
        pygame.draw.rect(screen, C(theme.COLORS["BORDER"]),  grid_rect, width=1)

        if dungeon_surface is not None:
            screen.blit(dungeon_surface, (GRID_X, GRID_Y))
        else:
            empty = np.zeros((evomap.GRID_H, evomap.GRID_W), dtype=np.int8)
            screen.blit(draw_dungeon_to_surface(empty), (GRID_X, GRID_Y))

        pulse = (math.sin(now * 4) + 1) / 2
        slow_pulse = (math.sin(now * 1.5) + 1) / 2

        if playback_gen >= 0 and playback_gen < len(local_results):
            sp_pos = spawn_screen_cache.get(playback_gen)
            if sp_pos:
                r_outer = 8 + int(pulse * 4)
                pygame.draw.circle(screen, C(theme.COLORS["GREEN"]),  sp_pos, r_outer, 2)
                pygame.draw.circle(screen, C(theme.COLORS["GREEN_DIM"]), sp_pos, r_outer + 3, 1)

            bs_pos = boss_screen_cache.get(playback_gen)
            if bs_pos:
                r_boss = 9 + int(slow_pulse * 3)
                pygame.draw.circle(screen, C("#8B0000"), bs_pos, r_boss, 2)
                pygame.draw.circle(screen, C("#3D0000"), bs_pos, r_boss + 4, 1)

            tr_pos = treasure_screen_cache.get(playback_gen)
            if tr_pos:
                pygame.draw.circle(screen, C("#FFD700"), tr_pos, 7 + int(pulse * 2), 1)

        if playback_gen >= 0 and playback_gen < len(local_results):
            _, score = local_results[playback_gen]
            max_s = max(r[1] for r in local_results) or 1.0
            norm_score = score / max_s
            if norm_score < 0.2 and playback_gen < len(local_results) - 1:
                kill_surf = pygame.Surface((grid_rect.width, grid_rect.height), pygame.SRCALPHA)
                kill_surf.fill((180, 30, 30, 60))
                screen.blit(kill_surf, (grid_rect.x, grid_rect.y))

        if (playback_gen == len(local_results) - 1
                and path_trail
                and len(local_results) > 0):
            glow_surf = pygame.Surface((grid_rect.width, grid_rect.height), pygame.SRCALPHA)
            for i in range(min(path_index + 1, len(path_trail))):
                r, c = path_trail[i]
                cx = c * CELL + CELL // 2
                cy = r * CELL + CELL // 2
                pygame.draw.circle(glow_surf, (0, 201, 122, 35), (cx, cy), 10)
                if i > 0:
                    pr, pc = path_trail[i - 1]
                    px = pc * CELL + CELL // 2
                    py = pr * CELL + CELL // 2
                    pygame.draw.line(glow_surf, (0, 201, 122, 25), (px, py), (cx, cy), 8)
            screen.blit(glow_surf, (grid_rect.x, grid_rect.y))

            treasure_pos_rc = evomap._find_tile(local_results[playback_gen][0], evomap.TREASURE)
            for i in range(min(path_index + 1, len(path_trail))):
                r, c = path_trail[i]
                center = tile_to_screen(r, c)
                is_treasure_tile = (treasure_pos_rc is not None and (r, c) == treasure_pos_rc)
                if is_treasure_tile:
                    # Draw a bright gold ring around the trail dot at the treasure
                    pygame.draw.circle(screen, pygame.Color("#FFD700"), center, 9, 2)
                    pygame.draw.circle(screen, pygame.Color("#FFF5A0"), center, 5, 1)
                pygame.draw.circle(screen, PATH_COLOR, center, 3)
                if i > 0:
                    pr, pc = path_trail[i - 1]
                    pygame.draw.line(screen, PATH_COLOR, tile_to_screen(pr, pc), center, 2)

            if path_index > 0:
                er, ec = path_trail[path_index]
                ex, ey = tile_to_screen(er, ec)
                lbl_font = theme.get_font(10)
                lbl = lbl_font.render(f"{path_index} steps", True, C(theme.COLORS["GREEN"]))
                screen.blit(lbl, (min(ex + 6, WIDTH - lbl.get_width() - 4), ey - 8))

        if gen_flash > 0:
            alpha = int(gen_flash * 10)
            flash_surf = pygame.Surface((grid_rect.width, grid_rect.height), pygame.SRCALPHA)
            flash_surf.fill((0, 201, 122, alpha))
            screen.blit(flash_surf, (grid_rect.x, grid_rect.y))

        if local_is_evolving:
            overlay = pygame.Surface((grid_rect.width, grid_rect.height), pygame.SRCALPHA)
            overlay.fill((7, 12, 24, 180))
            screen.blit(overlay, (grid_rect.x, grid_rect.y))

            ev_font_lg = theme.get_font(22)
            ev_font_sm = theme.get_font(13)

            ev_label = ev_font_lg.render("EVOLVING", True, C(theme.COLORS["GREEN"]))
            ev_rect  = ev_label.get_rect(center=(grid_rect.centerx, grid_rect.centery - 20))
            screen.blit(ev_label, ev_rect)

            prog_label = ev_font_sm.render(
                f"Generation  {evolution_progress} / 60  |  {evo_elapsed:.1f}s elapsed",
                True, C(theme.COLORS["TEXT_PRIMARY"])
            )
            prog_rect = prog_label.get_rect(center=(grid_rect.centerx, grid_rect.centery + 14))
            screen.blit(prog_label, prog_rect)

            dot_count = int(now * 2) % 4
            dots = "•" * dot_count
            dot_surf = ev_font_sm.render(dots, True, C(theme.COLORS["GREEN"]))
            dot_rect = dot_surf.get_rect(center=(grid_rect.centerx, grid_rect.centery + 38))
            screen.blit(dot_surf, dot_rect)

        if complete_flash > 0:
            alpha = int(complete_flash * 3)
            cf_surf = pygame.Surface((grid_rect.width, grid_rect.height), pygame.SRCALPHA)
            cf_surf.fill((0, 201, 122, alpha))
            screen.blit(cf_surf, (grid_rect.x, grid_rect.y))

            cf_font = theme.get_font(18)
            cf_label = cf_font.render("EVOLUTION COMPLETE", True, C(theme.COLORS["GREEN"]))
            cf_rect  = cf_label.get_rect(center=(grid_rect.centerx, grid_rect.centery))
            screen.blit(cf_label, cf_rect)

        hover_col = (mx - GRID_X) // CELL
        hover_row = (my - GRID_Y) // CELL
        if (0 <= hover_row < evomap.GRID_H and 0 <= hover_col < evomap.GRID_W
                and grid_rect.collidepoint(mx, my)
                and playback_gen >= 0
                and playback_gen < len(local_results)):
            hov_dungeon, _ = local_results[playback_gen]
            tile_val = int(hov_dungeon[hover_row, hover_col])
            tile_names = {0:"Wall", 1:"Floor", 2:"Corridor", 3:"Spawn", 4:"Boss", 5:"Treasure"}
            tile_name  = tile_names.get(tile_val, "Unknown")
            tip_font   = theme.get_font(10)
            tip_surf   = tip_font.render(tile_name, True, C(theme.COLORS["TEXT_PRIMARY"]))
            tip_rect   = pygame.Rect(mx + 10, my - 18,
                                     tip_surf.get_width() + 10, tip_surf.get_height() + 6)
            tip_rect.right  = min(tip_rect.right,  WIDTH  - 2)
            tip_rect.bottom = min(tip_rect.bottom, HEIGHT - 2)
            pygame.draw.rect(screen, C(theme.COLORS["SURFACE"]), tip_rect, border_radius=4)
            pygame.draw.rect(screen, C(theme.COLORS["BORDER"]),  tip_rect, width=1, border_radius=4)
            screen.blit(tip_surf, (tip_rect.x + 5, tip_rect.y + 3))

        if playback_gen >= 0 and not local_is_evolving:
            badge_font = theme.get_font(11)
            mode_str   = "MANUAL" if is_manual_scrub else ("PAUSED" if is_paused else "PLAYBACK")
            badge_text = f"Gen {playback_gen + 1} / {len(local_results)}  [{mode_str}]"
            badge_surf = badge_font.render(badge_text, True, C(theme.COLORS["TEXT_PRIMARY"]))
            bx, by     = GRID_X + 6, GRID_Y + 6
            badge_bg   = pygame.Rect(bx - 4, by - 3, badge_surf.get_width() + 8, badge_surf.get_height() + 6)
            pygame.draw.rect(screen, C(theme.COLORS["SURFACE"]), badge_bg, border_radius=4)
            pygame.draw.rect(screen, C(theme.COLORS["BORDER"]),  badge_bg, width=1, border_radius=4)
            screen.blit(badge_surf, (bx, by))

        for s in sliders.values():
            s.draw(screen)

        panel_rect = pygame.Rect(630, 60, 260, 635)
        pygame.draw.rect(screen, C(theme.COLORS["SURFACE"]), panel_rect, border_radius=8)
        pygame.draw.rect(screen, C(theme.COLORS["BORDER"]),  panel_rect, width=1, border_radius=8)

        current_gen_display = playback_gen + 1 if playback_gen >= 0 else 0
        current_score  = 0.0
        fitness_delta  = 0.0
        max_score_all  = max((r[1] for r in local_results), default=1.0) or 1.0
        rooms_display  = 0
        path_len_display = 0
        treasure_steps_display = None
        treasure_bonus_display = 0.0

        if playback_gen >= 0 and playback_gen < len(local_results):
            dungeon, current_score = local_results[playback_gen]
            rooms_display = rooms_cache.get(playback_gen, 0)

            if path_trail and playback_gen == len(local_results) - 1:
                path_len_display = len(path_trail)
            elif playback_gen in path_len_cache:
                path_len_display = path_len_cache[playback_gen]

            # Read from cache — no BFS call in the render loop
            treasure_steps_display = treasure_cache_steps.get(playback_gen)
            treasure_bonus_display = treasure_cache_bonus.get(playback_gen, 0.0)

            if playback_gen > 0:
                prev_score = local_results[playback_gen - 1][1]
                fitness_delta = current_score - prev_score

        norm_fitness_pct = int((current_score / max_score_all) * 100) if max_score_all > 0 else 0

        if local_is_evolving:
            status_str   = "EVOLVING"
            status_color = theme.COLORS["BLUE"]
        elif len(local_results) == 0:
            status_str   = "IDLE"
            status_color = theme.COLORS["TEXT_DIM"]
        elif is_converged(local_results):
            status_str   = "CONVERGED"
            status_color = theme.COLORS["GREEN"]
        elif playback_gen == len(local_results) - 1:
            status_str   = "COMPLETE"
            status_color = theme.COLORS["GREEN"]
        elif is_paused:
            status_str   = "PAUSED"
            status_color = theme.COLORS["MAC_AMBER"]
        else:
            status_str   = "PLAYING"
            status_color = theme.COLORS["BLUE"]

        font_lg = theme.get_font(20)
        font_md = theme.get_font(13)
        font_sm = theme.get_font(11)
        font_xs = theme.get_font(10)

        px, py = 645, 72
        title_s = font_md.render("EVOLUTION STATS", True, C(theme.COLORS["TEXT_PRIMARY"]))
        screen.blit(title_s, (px, py))
        py += 22

        theme.draw_tag_pill(screen, px, py, status_str, C(status_color))
        py += 24

        def stat_row(surface, x, y, label, value, color=theme.COLORS["GREEN"]):
            """Draw a label + value row. Returns the new y position."""
            lbl_s = font_xs.render(label, True, C(theme.COLORS["TEXT_DIM"]))
            surface.blit(lbl_s, (x, y))
            val_s = font_lg.render(str(value), True, C(color))
            surface.blit(val_s, (x, y + 12))
            return y + 36

        py = stat_row(screen, px, py, "Generation",   f"{current_gen_display} / 60")
        py = stat_row(screen, px, py, "Best Fitness", f"{norm_fitness_pct}%")

        lbl_s = font_xs.render("Δ Fitness", True, C(theme.COLORS["TEXT_DIM"]))
        screen.blit(lbl_s, (px, py))
        if playback_gen > 0:
            delta_str   = f"+{fitness_delta:.3f}" if fitness_delta >= 0 else f"{fitness_delta:.3f}"
            delta_color = theme.COLORS["GREEN"] if fitness_delta >= 0 else "#E24B4A"
        else:
            delta_str, delta_color = "---", theme.COLORS["TEXT_DIM"]
        val_s = font_lg.render(delta_str, True, C(delta_color))
        screen.blit(val_s, (px, py + 12))
        py += 36

        py = stat_row(screen, px, py, "Room Count",   str(rooms_display))
        py = stat_row(screen, px, py, "BFS Path Len", str(path_len_display) if path_len_display > 0 else "---")
        py = stat_row(screen, px, py, "Treasure Steps",
                 str(treasure_steps_display) if treasure_steps_display is not None else "---")
        py = stat_row(screen, px, py, "Treasure Bonus", f"+{treasure_bonus_display:.2f}")
        # Badge: ON PATH when treasure bonus is at maximum (detour == 0)
        if (treasure_bonus_display is not None
                and abs(treasure_bonus_display - evomap.TREASURE_VALUE) < 0.001
                and treasure_steps_display is not None):
            badge_font = theme.get_font(9)
            badge_surf = badge_font.render("★ ON PATH", True, pygame.Color("#FFD700"))
            screen.blit(badge_surf, (px, py))
            py += 14

        if local_is_evolving:
            py = stat_row(screen, px, py, "Elapsed", f"{evo_elapsed:.1f}s", theme.COLORS["BLUE"])

        tile_legend = [
            (WALL_COLOR,     "Wall"),
            (FLOOR_COLOR,    "Floor"),
            (CORRIDOR_COLOR, "Corridor"),
            (SPAWN_COLOR,    "Spawn"),
            (BOSS_COLOR,     "Boss"),
            (TREASURE_COLOR, "Treasure"),
        ]
        legend_font = theme.get_font(10)
        for tile_color, tile_name in tile_legend:
            pygame.draw.rect(screen, tile_color, pygame.Rect(px, py, 11, 11))
            ls = legend_font.render(tile_name, True, C(theme.COLORS["TEXT_PRIMARY"]))
            screen.blit(ls, (px + 15, py))
            py += 14
        py += 6

        chart_rect = pygame.Rect(px, py, 210, 90)
        pygame.draw.rect(screen, C(theme.COLORS["BG"]),     chart_rect)
        pygame.draw.rect(screen, C(theme.COLORS["BORDER"]), chart_rect, width=1)

        ax_font = theme.get_font(9)
        # Y-axis labels — inside chart, top-left and bottom-left corners
        screen.blit(ax_font.render("1.0", True, C(theme.COLORS["TEXT_DIM"])),
                    (chart_rect.x + 2, chart_rect.y + 2))
        screen.blit(ax_font.render("0",   True, C(theme.COLORS["TEXT_DIM"])),
                    (chart_rect.x + 2, chart_rect.bottom - 11))
        # X-axis labels — inside chart, bottom-left and bottom-right
        screen.blit(ax_font.render("G1",  True, C(theme.COLORS["TEXT_DIM"])),
                    (chart_rect.x + 2, chart_rect.bottom - 11))
        screen.blit(ax_font.render("60",  True, C(theme.COLORS["TEXT_DIM"])),
                    (chart_rect.right - 14, chart_rect.bottom - 11))

        if len(local_results) > 0 and playback_gen >= 0:
            points = []
            chart_inner_w = chart_rect.width - 8
            for i in range(playback_gen + 1):
                s   = local_results[i][1]
                pct = min(1.0, s / max_score_all) if max_score_all > 0 else 0
                ppx = chart_rect.x + (i / 59.0) * chart_inner_w
                ppy = chart_rect.bottom - pct * chart_rect.height
                points.append((ppx, ppy))

            ref_y = chart_rect.bottom - 0.5 * chart_rect.height
            pygame.draw.line(screen, C(theme.COLORS["BORDER"]),
                             (chart_rect.x, int(ref_y)),
                             (chart_rect.right, int(ref_y)), 1)

            if len(points) > 1:
                for idx in range(len(points) - 1):
                    seg_score = local_results[idx + 1][1]
                    seg_norm  = seg_score / max_score_all if max_score_all > 0 else 0
                    if seg_norm > 0.6:
                        seg_col = C(theme.COLORS["GREEN"])
                    elif seg_norm >= 0.3:
                        seg_col = C("#EF9F27")
                    else:
                        seg_col = C("#E24B4A")
                    pygame.draw.line(screen, seg_col, points[idx], points[idx + 1], 2)

            if points:
                cx_line = int(points[-1][0])
                pygame.draw.line(screen, C(theme.COLORS["TEXT_DIM"]),
                                 (cx_line, chart_rect.top),
                                 (cx_line, chart_rect.bottom), 1)
                pygame.draw.circle(screen, C(theme.COLORS["TEXT_PRIMARY"]),
                                   (int(points[-1][0]), int(points[-1][1])), 3)

        if len(local_results) > 0 and is_converged(local_results) and not local_is_evolving:
            conv_font = theme.get_font(9)
            conv_s = conv_font.render("CONVERGED", True, C(theme.COLORS["GREEN"]))
            # Draw as a small badge in the top-right of the chart
            cx = chart_rect.right - conv_s.get_width() - 8
            cy = chart_rect.y + 4
            screen.blit(conv_s, (cx, cy))

        run_hover = btn_run_rect.collidepoint((mx, my))
        if local_is_evolving:
            run_bg_col = C(theme.COLORS["SURFACE"])
            run_bd_col = C(theme.COLORS["BORDER"])
            run_tx_col = C(theme.COLORS["TEXT_DIM"])
            run_label  = "EVOLVING..."
        elif run_hover:
            run_bg_col = C(theme.COLORS["GREEN"])
            run_bd_col = C(theme.COLORS["GREEN"])
            run_tx_col = C(theme.COLORS["BG"])
            run_label  = "RUN EVOLUTION"
        else:
            run_bg_col = C(theme.COLORS["SURFACE"])
            run_bd_col = C(theme.COLORS["GREEN"])
            run_tx_col = C(theme.COLORS["GREEN"])
            run_label  = "RUN EVOLUTION"

        pygame.draw.rect(screen, run_bg_col, btn_run_rect, border_radius=6)
        pygame.draw.rect(screen, run_bd_col, btn_run_rect, width=1, border_radius=6)
        run_font = theme.get_font(13)
        run_txt  = run_font.render(run_label, True, run_tx_col)
        screen.blit(run_txt, run_txt.get_rect(center=btn_run_rect.center))

        pbar_rect = pygame.Rect(btn_run_rect.x, btn_run_rect.bottom + 3, btn_run_rect.width, 6)
        pygame.draw.rect(screen, C(theme.COLORS["BORDER"]), pbar_rect, border_radius=3)
        if evolution_progress > 0:
            fill_pct = min(1.0, evolution_progress / 60.0)
            fill_w   = max(1, int(fill_pct * pbar_rect.width))
            fill_col = C(theme.COLORS["GREEN"]) if evolution_progress >= 60 else C(theme.COLORS["BLUE"])
            pygame.draw.rect(screen, fill_col,
                             pygame.Rect(pbar_rect.x, pbar_rect.y, fill_w, pbar_rect.height),
                             border_radius=3)

        spd_font = theme.get_font(10)
        for i, (btn_rect, (label, _)) in enumerate(zip(speed_btn_rects, SPEEDS)):
            is_active = (i == speed_idx)
            is_hov    = btn_rect.collidepoint(mx, my)
            if is_active:
                bg = C(theme.COLORS["BLUE_DIM"])
                bd = C(theme.COLORS["BLUE"])
                fg = C(theme.COLORS["BLUE"])
            elif is_hov:
                bg = C(theme.COLORS["SURFACE"])
                bd = C(theme.COLORS["TEXT_DIM"])
                fg = C(theme.COLORS["TEXT_PRIMARY"])
            else:
                bg = C(theme.COLORS["BG"])
                bd = C(theme.COLORS["BORDER"])
                fg = C(theme.COLORS["TEXT_DIM"])
            pygame.draw.rect(screen, bg, btn_rect, border_radius=4)
            pygame.draw.rect(screen, bd, btn_rect, width=1, border_radius=4)
            ls = spd_font.render(label, True, fg)
            screen.blit(ls, ls.get_rect(center=btn_rect.center))

        back_hover = btn_back_rect.collidepoint((mx, my))
        back_bg    = C(theme.COLORS["MAC_RED"]) if back_hover else C(theme.COLORS["SURFACE"])
        back_tx    = C(theme.COLORS["BG"])      if back_hover else C(theme.COLORS["MAC_RED"])
        pygame.draw.rect(screen, back_bg,                     btn_back_rect, border_radius=6)
        pygame.draw.rect(screen, C(theme.COLORS["MAC_RED"]),  btn_back_rect, width=1, border_radius=6)
        bk_font = theme.get_font(12)
        bk_txt  = bk_font.render("Back to Hub", True, back_tx)
        screen.blit(bk_txt, bk_txt.get_rect(center=btn_back_rect.center))

        ks_font = theme.get_font(9)
        ks_text = "SPC pause  ←→ scrub  R replay  ESC back"
        ks_surf = ks_font.render(ks_text, True, C(theme.COLORS["TEXT_DIM"]))
        screen.blit(ks_surf, (630, HEIGHT - 20))

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()

if __name__ == "__main__":
    main()
