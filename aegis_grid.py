import sys
import ctypes
import math
import time
import threading
import heapq
import pygame
import numpy as np
import theme

try:
    ctypes.windll.user32.SetProcessDPIAware()
except AttributeError:
    pass

def C(h):
    return pygame.Color(h)

def generate_maze():
    grid = np.zeros((20, 20), dtype=np.int8)
    np.random.seed(int(time.time() * 1000) % (2**32))
    for r in range(2, 19, 2):
        for c in range(1, 19):
            grid[r, c] = 1
    for c in range(2, 19, 2):
        for r in range(1, 19):
            grid[r, c] = 1
    for r in range(2, 19, 2):
        for c in range(2, 19, 2):
            nr, nc = [(r-1, c), (r+1, c), (r, c-1), (r, c+1)][np.random.randint(4)]
            grid[nr, nc] = 0
    for r in range(1, 19):
        for c in range(1, 19):
            if grid[r, c] == 1:
                e = 0
                for dr, dc in [(-1,0), (1,0), (0,-1), (0,1)]:
                    if 0 <= r+dr < 20 and 0 <= c+dc < 20 and grid[r+dr, c+dc] == 0:
                        e += 1
                if e >= 3 and np.random.rand() < 0.3:
                    grid[r, c] = 0
    for r, c in [(1,1),(1,2),(2,1),(18,18),(17,18),(18,17),(3,9),(2,9),(4,9),(3,8),(3,10),(18,1),(17,1),(18,2)]:
        grid[r, c] = 0
    q = [(1, 1)]
    v = {(1, 1)}
    f = False
    while q:
        cr, cc = q.pop(0)
        if cr == 18 and cc == 18:
            f = True
            break
        for dr, dc in [(-1,0), (1,0), (0,-1), (0,1)]:
            nr, nc = cr+dr, cc+dc
            if 0 <= nr < 20 and 0 <= nc < 20 and grid[nr, nc] == 0 and (nr, nc) not in v:
                v.add((nr, nc))
                q.append((nr, nc))
    if not f:
        grid = np.zeros((20, 20), dtype=np.int8)
    grid[1, 1] = 2
    grid[18, 18] = 4
    return grid

def get_heuristic(pos, goal, h_type):
    dx = abs(pos[0] - goal[0])
    dy = abs(pos[1] - goal[1])
    if h_type == 'Euclidean':
        return (dx**2 + dy**2) ** 0.5
    elif h_type == 'Chebyshev':
        return max(dx, dy)
    return dx + dy

def a_star(grid, start, goal, h_type):
    open_set = []
    heapq.heappush(open_set, (0, 0, start))
    open_set_tracker = {start}
    came_from = {}
    g_score = {start: 0}
    oh = []
    ch = []
    cs = set()
    ne = 0
    while open_set:
        oh.append(list(open_set_tracker))
        ch.append(list(cs))
        if len(oh) > 200:
            oh.pop(0)
            ch.pop(0)
        _, _, current = heapq.heappop(open_set)
        if current not in open_set_tracker:
            continue
        open_set_tracker.remove(current)
        if current == goal:
            p = []
            while current in came_from:
                p.append(current)
                current = came_from[current]
            p.append(start)
            p.reverse()
            oh.append(list(open_set_tracker))
            ch.append(list(cs))
            if len(oh) > 200:
                oh.pop(0)
                ch.pop(0)
            return p, oh, ch, ne
        cs.add(current)
        ne += 1
        for dr, dc in [(-1,0), (1,0), (0,-1), (0,1)]:
            nr, nc = current[0]+dr, current[1]+dc
            if 0 <= nr < 20 and 0 <= nc < 20 and grid[nr, nc] != 1:
                nbr = (nr, nc)
                tg = g_score[current] + 1
                if tg < g_score.get(nbr, float('inf')):
                    came_from[nbr] = current
                    g_score[nbr] = tg
                    f_score = tg + get_heuristic(nbr, goal, h_type)
                    heapq.heappush(open_set, (f_score, tg, nbr))
                    open_set_tracker.add(nbr)
    oh.append(list(open_set_tracker))
    ch.append(list(cs))
    if len(oh) > 200:
        oh.pop(0)
        ch.pop(0)
    return [], oh, ch, ne

def get_best_wall(grid, red_pos, goal_pos, blue_pos, h_type, depth=3):
    path, _, _, _ = a_star(grid, red_pos, goal_pos, h_type)
    if not path:
        return None, 0
    s = {'p': 0}
    def _mm(g, r_pos, d, alpha, beta, is_blue):
        p, _, _, _ = a_star(g, r_pos, goal_pos, h_type)
        if not p:
            return 9999 + (depth - d), None
        if r_pos == goal_pos:
            return -9999, None
        if d == 0:
            return len(p), None
        if is_blue:
            cands = set()
            for pr, pc in p:
                for dr in range(-2, 3):
                    for dc in range(-2, 3):
                        if abs(dr) + abs(dc) <= 2:
                            nr, nc = pr+dr, pc+dc
                            if 0 <= nr < 20 and 0 <= nc < 20 and g[nr, nc] == 0:
                                if abs(nr - goal_pos[0]) + abs(nc - goal_pos[1]) > 3:
                                    if abs(nr - r_pos[0]) + abs(nc - r_pos[1]) > 2:
                                        if (nr, nc) not in (r_pos, goal_pos, blue_pos):
                                            cands.add((nr, nc))
            mid = p[len(p)//2]
            c_list = sorted(list(cands), key=lambda x: abs(x[0]-mid[0]) + abs(x[1]-mid[1]))[:15]
            if not c_list:
                return len(p), None
            bv = -float('inf')
            ba = None
            for r, c in c_list:
                g[r, c] = 1
                v, _ = _mm(g, r_pos, d-1, alpha, beta, False)
                g[r, c] = 0
                if v > bv:
                    bv = v
                    ba = (r, c)
                alpha = max(alpha, bv)
                if beta <= alpha:
                    s['p'] += 1
                    break
            return bv, ba
        else:
            bv = float('inf')
            ba = None
            m = []
            for dr, dc in [(-1,0), (1,0), (0,-1), (0,1)]:
                nr, nc = r_pos[0]+dr, r_pos[1]+dc
                if 0 <= nr < 20 and 0 <= nc < 20 and g[nr, nc] != 1:
                    m.append((nr, nc))
            m.sort(key=lambda x: abs(x[0]-goal_pos[0]) + abs(x[1]-goal_pos[1]))
            for nr, nc in m:
                t = g[nr, nc]
                g[r_pos] = 0
                g[nr, nc] = 2
                v, _ = _mm(g, (nr, nc), d-1, alpha, beta, True)
                g[nr, nc] = t
                g[r_pos] = 2
                if v < bv:
                    bv = v
                    ba = (nr, nc)
                beta = min(beta, bv)
                if beta <= alpha:
                    s['p'] += 1
                    break
            return bv, ba
    _, bw = _mm(grid.copy(), red_pos, depth, -float('inf'), float('inf'), True)
    return bw, s['p']

def step_game(grid, red_pos, goal_pos, blue_pos, blue_target, h_type, step_count, max_steps=150):
    new_grid = grid.copy()
    p, _, _, n1 = a_star(new_grid, red_pos, goal_pos, h_type)
    if not p:
        return new_grid, red_pos, {'status': 'blue_wins', 'path': p, 'open_history': [], 'closed_history': [], 'nodes_explored': n1, 'pruned': 0, 'blue_wall': None, 'blue_target': blue_target, 'blue_pos': blue_pos}
    nrp = red_pos
    if len(p) > 1:
        new_grid[nrp] = 0
        nrp = p[1]
        new_grid[nrp] = 2
        p2, _, _, _ = a_star(new_grid, nrp, goal_pos, h_type)
        if p2 and len(p2) > 1:
            new_grid[nrp] = 0
            nrp = p2[1]
            new_grid[nrp] = 2
    if nrp == goal_pos:
        return new_grid, nrp, {'status': 'red_wins', 'path': [], 'open_history': [], 'closed_history': [], 'nodes_explored': n1, 'pruned': 0, 'blue_wall': None, 'blue_target': blue_target, 'blue_pos': blue_pos}
    if step_count >= max_steps:
        return new_grid, nrp, {'status': 'draw', 'path': [], 'open_history': [], 'closed_history': [], 'nodes_explored': n1, 'pruned': 0, 'blue_wall': None, 'blue_target': blue_target, 'blue_pos': blue_pos}
    p_current, _, _, n_extra = a_star(new_grid, nrp, goal_pos, h_type)
    n1 += n_extra
    if blue_target is not None:
        if p_current:
            is_relevant = False
            for pr, pc in p_current:
                if abs(blue_target[0] - pr) + abs(blue_target[1] - pc) <= 2:
                    is_relevant = True
                    break
            if not is_relevant or new_grid[blue_target] != 0 or blue_target == nrp or blue_target == goal_pos:
                blue_target = None
        else:
            if new_grid[blue_target] != 0 or blue_target == nrp or blue_target == goal_pos:
                blue_target = None
    pr = 0
    if blue_target is None:
        bw, pr = get_best_wall(new_grid, nrp, goal_pos, blue_pos, h_type, depth=3)
        if bw is not None:
            blue_target = bw
    new_blue_pos = blue_pos
    intermediate = blue_pos
    blue_wall_result = None
    if blue_target is not None:
        q = [blue_pos]
        visited = {blue_pos: None}
        while q:
            cur = q.pop(0)
            if cur == blue_target:
                break
            for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
                nr, nc = cur[0]+dr, cur[1]+dc
                if 0 <= nr < 20 and 0 <= nc < 20 and new_grid[nr,nc] != 1 and (nr,nc) not in visited:
                    visited[(nr,nc)] = cur
                    q.append((nr,nc))
        if blue_target not in visited:
            blue_target = None
            new_blue_pos = blue_pos
            blue_wall_result = None
        else:
            if blue_pos == blue_target:
                new_grid[blue_target] = 1
                blue_wall_result = blue_target
                blue_target = None
            else:
                step = blue_target
                while visited[step] != blue_pos:
                    step = visited[step]
                intermediate = step
                if intermediate == blue_target:
                    new_grid[blue_target] = 1
                    blue_wall_result = blue_target
                    blue_target = None
                    new_blue_pos = intermediate
                else:
                    q2 = [intermediate]
                    visited2 = {intermediate: None}
                    while q2:
                        cur = q2.pop(0)
                        if cur == blue_target:
                            break
                        for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
                            nr, nc = cur[0]+dr, cur[1]+dc
                            if 0 <= nr < 20 and 0 <= nc < 20 and new_grid[nr,nc] != 1 and (nr,nc) not in visited2:
                                visited2[(nr,nc)] = cur
                                q2.append((nr,nc))
                    if blue_target not in visited2:
                        new_blue_pos = intermediate
                        blue_wall_result = None
                    else:
                        if intermediate == blue_target:
                            new_grid[blue_target] = 1
                            blue_wall_result = blue_target
                            blue_target = None
                            new_blue_pos = intermediate
                        else:
                            step2 = blue_target
                            while visited2[step2] != intermediate:
                                step2 = visited2[step2]
                            new_blue_pos = step2
                            blue_wall_result = None
    if new_blue_pos == nrp or new_blue_pos == goal_pos:
        if intermediate != nrp and intermediate != goal_pos:
            new_blue_pos = intermediate
        else:
            new_blue_pos = blue_pos
    p3, oh, ch, n2 = a_star(new_grid, nrp, goal_pos, h_type)
    if not p3:
        return new_grid, nrp, {'status': 'blue_wins', 'path': p3, 'open_history': oh, 'closed_history': ch, 'nodes_explored': n1+n2, 'pruned': pr, 'blue_wall': blue_wall_result, 'blue_target': blue_target, 'blue_pos': new_blue_pos}
    return new_grid, nrp, {'status': 'ongoing', 'path': p3, 'open_history': oh, 'closed_history': ch, 'nodes_explored': n1+n2, 'pruned': pr, 'blue_wall': blue_wall_result, 'blue_target': blue_target, 'blue_pos': new_blue_pos}

class GameState:
    def __init__(self):
        self.grid = generate_maze()
        self.red_pos = (1, 1)
        self.goal_pos = (18, 18)
        self.blue_pos = (3, 9)
        self.blue_target = None
        self.status = "Ongoing"
        self.path = []
        self.open_history = []
        self.closed_history = []
        self.nodes_explored = 0
        self.pruned_total = 0
        self.last_blue_wall = None
        self.last_blue_wall_time = 0.0
        self.is_thinking = False
        self.stats_incremented = False
        self.step_count = 0
        self.move_log = []
        self.astar_frame_idx = 0
        self.path_draw_progress = 0.0
        self.path_draw_active = False
        self.path_draw_start_time = 0.0

def main():
    pygame.init()
    WIDTH, HEIGHT = 1100, 750
    screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.NOFRAME | pygame.SCALED)
    pygame.display.set_caption("Aegis Grid")
    clock = pygame.time.Clock()
    CELL = 28
    GRID_X, GRID_Y = 30, 50
    HEURISTICS = ['Manhattan', 'Euclidean', 'Chebyshev']
    h_idx = 0
    SPEEDS = [0.6, 0.15, 0.0]
    speed_idx = 1
    mode = 'visualise'
    human_mode = False
    is_running = False
    last_step_time = time.time()
    overlay_start_time = None
    frame_counter = 0
    red_wins = 0
    blue_wins = 0
    draws = 0
    state = GameState()
    red_render_pos = [1.0, 1.0]
    blue_render_pos = [3.0, 9.0]
    px = 625
    btn_visualise = pygame.Rect(px, 70, 140, 28)
    btn_adversarial = pygame.Rect(px+148, 70, 140, 28)
    h_btns = [pygame.Rect(px, 142, 138, 26), pygame.Rect(px+144, 142, 138, 26), pygame.Rect(px+288, 142, 138, 26)]
    s_btns = [pygame.Rect(px, 196, 138, 26), pygame.Rect(px+144, 196, 138, 26), pygame.Rect(px+288, 196, 138, 26)]
    btn_ai_blue = pygame.Rect(px, 428, 190, 26)
    btn_human_blue = pygame.Rect(px+196, 428, 230, 26)
    btn_run = pygame.Rect(px, 658, 190, 32)
    btn_step = pygame.Rect(px+196, 658, 90, 32)
    btn_reset = pygame.Rect(px, 698, 190, 32)
    btn_back_adv = pygame.Rect(px+196, 698, 230, 32)
    btn_rerun = pygame.Rect(px, 658, 190, 32)
    btn_back_vis = pygame.Rect(px+196, 658, 230, 32)

    def log(st, text, color_hex):
        st.move_log.insert(0, {'text': text, 'color': color_hex, 'time': time.time()})
        if len(st.move_log) > 8:
            st.move_log.pop()

    def draw_btn(r, label, color_hex, disabled=False):
        mx, my = pygame.mouse.get_pos()
        hover = r.collidepoint(mx, my) and not disabled
        bg = C(color_hex) if hover else C(theme.COLORS["SURFACE"])
        border = C(theme.COLORS["TEXT_DIM"]) if disabled else C(color_hex)
        text_c = C(theme.COLORS["TEXT_DIM"]) if disabled else C(theme.COLORS["BG"]) if hover else C(color_hex)
        pygame.draw.rect(screen, bg, r, border_radius=6)
        pygame.draw.rect(screen, border, r, 1, border_radius=6)
        t = theme.get_font(13).render(label, True, text_c)
        screen.blit(t, t.get_rect(center=r.center))

    def trigger_visualise_astar(st, h_type):
        st.is_thinking = True
        def w():
            p, oh, ch, ne = a_star(st.grid, st.red_pos, st.goal_pos, h_type)
            st.path = p
            st.open_history = oh
            st.closed_history = ch
            st.nodes_explored = ne
            st.astar_frame_idx = 0
            st.path_draw_progress = 0.0
            st.path_draw_active = False
            st.is_thinking = False
        threading.Thread(target=w, daemon=True).start()

    trigger_visualise_astar(state, HEURISTICS[h_idx])

    def trigger_step():
        if state.is_thinking or state.status != "Ongoing":
            return
        state.is_thinking = True
        def w():
            nonlocal red_wins, blue_wins, draws, is_running
            if human_mode:
                ng = state.grid.copy()
                p, _, _, n1 = a_star(ng, state.red_pos, state.goal_pos, HEURISTICS[h_idx])
                if not p:
                    res = {'status': 'blue_wins', 'path': p, 'open_history': [], 'closed_history': [], 'nodes_explored': n1, 'pruned': 0, 'blue_wall': None, 'blue_target': state.blue_target}
                    nrp = state.red_pos
                else:
                    nrp = state.red_pos
                    if len(p) > 1:
                        ng[nrp] = 0
                        nrp = p[1]
                        ng[nrp] = 2
                    if nrp == state.goal_pos:
                        res = {'status': 'red_wins', 'path': [], 'open_history': [], 'closed_history': [], 'nodes_explored': n1, 'pruned': 0, 'blue_wall': None, 'blue_target': state.blue_target}
                    elif state.step_count >= 150:
                        res = {'status': 'draw', 'path': [], 'open_history': [], 'closed_history': [], 'nodes_explored': n1, 'pruned': 0, 'blue_wall': None, 'blue_target': state.blue_target}
                    else:
                        p2, oh, ch, n2 = a_star(ng, nrp, state.goal_pos, HEURISTICS[h_idx])
                        if not p2:
                            res = {'status': 'blue_wins', 'path': p2, 'open_history': oh, 'closed_history': ch, 'nodes_explored': n1+n2, 'pruned': 0, 'blue_wall': None, 'blue_target': state.blue_target}
                        else:
                            res = {'status': 'ongoing', 'path': p2, 'open_history': oh, 'closed_history': ch, 'nodes_explored': n1+n2, 'pruned': 0, 'blue_wall': None, 'blue_target': state.blue_target}
            else:
                ng, nrp, res = step_game(state.grid, state.red_pos, state.goal_pos, state.blue_pos, state.blue_target, HEURISTICS[h_idx], state.step_count, 150)
            if nrp != state.red_pos:
                log(state, f"→ Red  ({nrp[0]},{nrp[1]})", theme.COLORS["GREEN"])
            if res.get('blue_wall'):
                bw = res['blue_wall']
                state.last_blue_wall = bw
                state.last_blue_wall_time = time.time()
                log(state, f"■ Blue walled ({bw[0]},{bw[1]})", theme.COLORS["BLUE"])
            elif res.get('blue_target'):
                bt = res['blue_target']
                log(state, f"→ Blue→({bt[0]},{bt[1]})", theme.COLORS["TEXT_MONO"])
            state.grid = ng
            state.red_pos = nrp
            state.blue_pos = res.get('blue_pos', state.blue_pos)
            state.blue_target = res.get('blue_target', None)
            state.status = res['status']
            if state.status == 'red_wins': state.status = "Red Wins"
            elif state.status == 'blue_wins': state.status = "Blue Wins"
            elif state.status == 'draw': state.status = "Draw"
            else: state.status = "Ongoing"
            state.path = res.get('path', [])
            state.open_history = res.get('open_history', [])
            state.closed_history = res.get('closed_history', [])
            state.nodes_explored += res.get('nodes_explored', 0)
            state.pruned_total += res.get('pruned', 0)
            state.step_count += 1
            if state.status != "Ongoing":
                if state.status == "Red Wins":
                    log(state, "✓ Red reaches goal", theme.COLORS["GREEN"])
                elif state.status == "Blue Wins":
                    log(state, "✗ Blue blocks all paths", theme.COLORS["MAC_RED"])
                elif state.status == "Draw":
                    log(state, "— Draw after 150 steps", theme.COLORS["TEXT_PRIMARY"])
                if not state.stats_incremented:
                    theme.StatsManager().increment("games_played")
                    state.stats_incremented = True
                    is_running = False
                    if state.status == "Red Wins": red_wins += 1
                    elif state.status == "Blue Wins": blue_wins += 1
                    elif state.status == "Draw": draws += 1
            state.is_thinking = False
        threading.Thread(target=w, daemon=True).start()

    while True:
        now = time.time()
        mx, my = pygame.mouse.get_pos()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                sys.exit(0)
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if pygame.Rect(11, 8, 14, 14).collidepoint(mx, my):
                    sys.exit(0)
                if not state.is_thinking:
                    if btn_visualise.collidepoint(mx, my):
                        mode = 'visualise'
                        trigger_visualise_astar(state, HEURISTICS[h_idx])
                    if btn_adversarial.collidepoint(mx, my):
                        mode = 'adversarial'
                    for i, btn in enumerate(h_btns):
                        if btn.collidepoint(mx, my):
                            h_idx = i
                            if mode == 'visualise':
                                trigger_visualise_astar(state, HEURISTICS[h_idx])
                    for i, btn in enumerate(s_btns):
                        if btn.collidepoint(mx, my):
                            speed_idx = i
                    if mode == 'adversarial':
                        if btn_ai_blue.collidepoint(mx, my):
                            human_mode = False
                        if btn_human_blue.collidepoint(mx, my):
                            human_mode = True
                        if btn_run.collidepoint(mx, my) and state.status == "Ongoing":
                            is_running = not is_running
                        if btn_step.collidepoint(mx, my) and not is_running and state.status == "Ongoing":
                            trigger_step()
                        if btn_reset.collidepoint(mx, my):
                            state = GameState()
                            is_running = False
                            red_render_pos = [1.0, 1.0]
                            blue_render_pos = [3.0, 9.0]
                            overlay_start_time = None
                            log(state, "Grid reset", theme.COLORS["TEXT_DIM"])
                        if human_mode and state.status == "Ongoing" and not is_running:
                            c = (mx - GRID_X) // CELL
                            r = (my - GRID_Y) // CELL
                            if 0 <= r < 20 and 0 <= c < 20:
                                if state.grid[r, c] == 0 and (r, c) != state.red_pos and (r, c) != state.goal_pos:
                                    state.grid[r, c] = 1
                                    state.last_blue_wall = (r, c)
                                    state.last_blue_wall_time = time.time()
                                    log(state, f"■ Human walled ({r},{c})", theme.COLORS["PURPLE"])
                                    trigger_step()
                        if btn_back_adv.collidepoint(mx, my):
                            sys.exit(0)
                    if mode == 'visualise':
                        if btn_rerun.collidepoint(mx, my):
                            trigger_visualise_astar(state, HEURISTICS[h_idx])
                        c = (mx - GRID_X) // CELL
                        r = (my - GRID_Y) // CELL
                        if 0 <= r < 20 and 0 <= c < 20:
                            if state.grid[r, c] == 0 and (r, c) not in [(1,1), (18,18)]:
                                state.grid[r, c] = 1
                                trigger_visualise_astar(state, HEURISTICS[h_idx])
                            elif state.grid[r, c] == 1:
                                state.grid[r, c] = 0
                                trigger_visualise_astar(state, HEURISTICS[h_idx])
                        if btn_back_vis.collidepoint(mx, my):
                            sys.exit(0)
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    sys.exit(0)
                if event.key == pygame.K_r:
                    state = GameState()
                    is_running = False
                    red_render_pos = [1.0, 1.0]
                    blue_render_pos = [3.0, 9.0]
                    overlay_start_time = None
                    log(state, "Grid reset", theme.COLORS["TEXT_DIM"])
                    if mode == 'visualise':
                        trigger_visualise_astar(state, HEURISTICS[h_idx])
                if event.key == pygame.K_SPACE and mode == 'adversarial':
                    if state.status == "Ongoing":
                        is_running = not is_running

        if mode == 'adversarial' and is_running and state.status == "Ongoing" and not state.is_thinking:
            if now - last_step_time >= SPEEDS[speed_idx]:
                trigger_step()
                last_step_time = now

        if state.status != "Ongoing" and overlay_start_time is None:
            overlay_start_time = now

        if mode == 'visualise' and not state.is_thinking and state.open_history:
            max_frame = len(state.open_history) - 1
            if state.astar_frame_idx < max_frame:
                if speed_idx == 2:
                    state.astar_frame_idx = max_frame
                elif speed_idx == 1:
                    state.astar_frame_idx = min(max_frame, state.astar_frame_idx + 3)
                else:
                    if frame_counter % 3 == 0:
                        state.astar_frame_idx = min(max_frame, state.astar_frame_idx + 1)
            elif not state.path_draw_active and state.path:
                state.path_draw_active = True
                state.path_draw_start_time = time.time()

        if state.path_draw_active:
            elapsed = time.time() - state.path_draw_start_time
            state.path_draw_progress = min(1.0, elapsed / 0.4)

        red_render_pos[0] += (state.red_pos[0] - red_render_pos[0]) * 0.25
        red_render_pos[1] += (state.red_pos[1] - red_render_pos[1]) * 0.25
        blue_render_pos[0] += (state.blue_pos[0] - blue_render_pos[0]) * 0.25
        blue_render_pos[1] += (state.blue_pos[1] - blue_render_pos[1]) * 0.25

        screen.fill(C(theme.COLORS["BG"]))
        theme.draw_window_bar(screen, 1100, "AEGIS GRID — Pathfinding & Adversarial Search")
        pygame.draw.rect(screen, C(theme.COLORS["BORDER"]), pygame.Rect(GRID_X-1, GRID_Y-1, 20*CELL+2, 20*CELL+2), 1)

        oset = state.open_history[state.astar_frame_idx] if (mode == 'visualise' and state.open_history and state.astar_frame_idx < len(state.open_history)) else (state.open_history[-1] if state.open_history else [])
        cset = state.closed_history[state.astar_frame_idx] if (mode == 'visualise' and state.closed_history and state.astar_frame_idx < len(state.closed_history)) else (state.closed_history[-1] if state.closed_history else [])

        for r in range(20):
            for c in range(20):
                rect = pygame.Rect(GRID_X + c*CELL, GRID_Y + r*CELL, CELL, CELL)
                if state.grid[r, c] == 1:
                    if (r, c) == state.last_blue_wall and time.time() - state.last_blue_wall_time < 0.5:
                        t = 1.0 - (time.time() - state.last_blue_wall_time) / 0.5
                        bc = C(theme.COLORS["BLUE"])
                        dc = C(theme.COLORS["BORDER"])
                        fc = pygame.Color(int(bc.r + (dc.r - bc.r) * t), int(bc.g + (dc.g - bc.g) * t), int(bc.b + (dc.b - bc.b) * t))
                        pygame.draw.rect(screen, fc, rect)
                        pygame.draw.rect(screen, C(theme.COLORS["BLUE"]), rect, 1)
                    else:
                        pygame.draw.rect(screen, C(theme.COLORS["BORDER"]), rect)
                        pygame.draw.rect(screen, C(theme.COLORS["BORDER"]), rect, 1)
                else:
                    pygame.draw.rect(screen, C(theme.COLORS["SURFACE"]), rect)
                    if (r, c) in cset:
                        s = pygame.Surface((CELL, CELL), pygame.SRCALPHA)
                        s.fill((89, 89, 89, 80))
                        screen.blit(s, rect.topleft)
                    if (r, c) in oset:
                        alpha = int(60 + 40 * math.sin(pygame.time.get_ticks() * 0.005 + r * 0.3 + c * 0.3))
                        s = pygame.Surface((CELL, CELL), pygame.SRCALPHA)
                        s.fill((239, 159, 39, alpha))
                        screen.blit(s, rect.topleft)
                    pygame.draw.rect(screen, C(theme.COLORS["BORDER"]), rect, 1)
                    if r == 18 and c == 18:
                        pygame.draw.rect(screen, C(theme.COLORS["GREEN"]), rect.inflate(-6, -6), border_radius=4)
                        g_alpha = int(180 + 60 * math.sin(pygame.time.get_ticks() * 0.003))
                        s = pygame.Surface((CELL, CELL), pygame.SRCALPHA)
                        pygame.draw.circle(s, (255, 255, 255, g_alpha), (CELL//2, CELL//2), CELL//2 - 2)
                        screen.blit(s, rect.topleft)


        if state.path and state.path_draw_progress > 0:
            pts = [(GRID_X + c*CELL + CELL//2, GRID_Y + r*CELL + CELL//2) for r, c in state.path]
            d_len = int(state.path_draw_progress * (len(state.path) - 1))
            if d_len > 0:
                pygame.draw.lines(screen, C("#00FFFF"), False, pts[:d_len+1], 3)
            if state.path_draw_progress >= 1.0:
                for pt in pts:
                    pygame.draw.circle(screen, C("#00FFFF"), pt, 2)

        rx = GRID_X + red_render_pos[1]*CELL + CELL//2
        ry = GRID_Y + red_render_pos[0]*CELL + CELL//2
        pygame.draw.circle(screen, C("#E24B4A"), (int(rx), int(ry)), CELL//2 - 3)
        pygame.draw.circle(screen, C(theme.COLORS["TEXT_PRIMARY"]), (int(rx), int(ry)), CELL//2 - 3, 1)
        if mode == 'adversarial':
            bx = GRID_X + blue_render_pos[1]*CELL + CELL//2
            by = GRID_Y + blue_render_pos[0]*CELL + CELL//2
            pygame.draw.circle(screen, C(theme.COLORS["BLUE"]), (int(bx), int(by)), CELL//2 - 3)
            pygame.draw.circle(screen, C(theme.COLORS["TEXT_PRIMARY"]), (int(bx), int(by)), CELL//2 - 3, 1)

        if state.status != "Ongoing" and overlay_start_time is not None:
            st = min(1.0, (now - overlay_start_time) / 0.4)
            st = 1.0 - (1.0 - st) ** 3
            fs = int(16 + 20 * st)
            s = pygame.Surface((20*CELL, 20*CELL), pygame.SRCALPHA)
            s.fill((0, 0, 0, 160))
            screen.blit(s, (GRID_X, GRID_Y))
            f_res = theme.get_font(fs)
            if state.status == "Red Wins":
                rt = "RED WINS"
                rc = C(theme.COLORS["GREEN"])
            elif state.status == "Blue Wins":
                rt = "BLUE WINS"
                rc = C(theme.COLORS["MAC_RED"])
            else:
                rt = "DRAW"
                rc = C(theme.COLORS["TEXT_PRIMARY"])
            rs = f_res.render(rt, True, rc)
            rr = rs.get_rect(center=(GRID_X + 10*CELL, GRID_Y + 10*CELL))
            screen.blit(rs, rr)
            sub = theme.get_font(13).render("Press RESET to play again", True, C(theme.COLORS["TEXT_DIM"]))
            subr = sub.get_rect(center=(GRID_X + 10*CELL, GRID_Y + 10*CELL + 40))
            screen.blit(sub, subr)

        pr = pygame.Rect(610, 40, 470, 700)
        pygame.draw.rect(screen, C(theme.COLORS["SURFACE"]), pr, border_radius=8)
        pygame.draw.rect(screen, C(theme.COLORS["BORDER"]), pr, 1, border_radius=8)

        f10 = theme.get_font(10)
        f11 = theme.get_font(11)
        f16 = theme.get_font(16)
        f20 = theme.get_font(20)

        screen.blit(f10.render("MODE", True, C(theme.COLORS["TEXT_DIM"])), (px, 55))
        pygame.draw.rect(screen, C(theme.COLORS["BLUE_DIM"] if mode == 'visualise' else theme.COLORS["BG"]), btn_visualise, border_radius=4)
        pygame.draw.rect(screen, C(theme.COLORS["BLUE"] if mode == 'visualise' else theme.COLORS["BORDER"]), btn_visualise, 1, border_radius=4)
        vs = f11.render("VISUALISE", True, C(theme.COLORS["BLUE"] if mode == 'visualise' else theme.COLORS["TEXT_DIM"]))
        screen.blit(vs, vs.get_rect(center=btn_visualise.center))
        pygame.draw.rect(screen, C(theme.COLORS["BLUE_DIM"] if mode == 'adversarial' else theme.COLORS["BG"]), btn_adversarial, border_radius=4)
        pygame.draw.rect(screen, C(theme.COLORS["BLUE"] if mode == 'adversarial' else theme.COLORS["BORDER"]), btn_adversarial, 1, border_radius=4)
        ads = f11.render("ADVERSARIAL", True, C(theme.COLORS["BLUE"] if mode == 'adversarial' else theme.COLORS["TEXT_DIM"]))
        screen.blit(ads, ads.get_rect(center=btn_adversarial.center))

        screen.blit(f10.render("HEURISTIC", True, C(theme.COLORS["TEXT_DIM"])), (px, 110))
        h_strs = ["h = |\u0394r| + |\u0394c|", "h = \u221a(\u0394r\u00b2 + \u0394c\u00b2)", "h = max(|\u0394r|, |\u0394c|)"]
        screen.blit(f11.render(h_strs[h_idx], True, C(theme.COLORS["TEXT_MONO"])), (px, 124))
        for i, btn in enumerate(h_btns):
            hov = btn.collidepoint(mx, my) and not state.is_thinking
            bc = C(theme.COLORS["BLUE_DIM"] if h_idx == i else theme.COLORS["BG"])
            bor = C(theme.COLORS["BLUE"] if h_idx == i else theme.COLORS["TEXT_DIM"] if hov else theme.COLORS["BORDER"])
            tc = C(theme.COLORS["BLUE"] if h_idx == i else theme.COLORS["TEXT_PRIMARY"] if hov else theme.COLORS["TEXT_DIM"])
            pygame.draw.rect(screen, bc, btn, border_radius=4)
            pygame.draw.rect(screen, bor, btn, 1, border_radius=4)
            ts = f11.render(HEURISTICS[i].upper(), True, tc)
            screen.blit(ts, ts.get_rect(center=btn.center))

        screen.blit(f10.render("SPEED", True, C(theme.COLORS["TEXT_DIM"])), (px, 182))
        s_lbls = ["SLOW", "FAST", "INSTANT"]
        for i, btn in enumerate(s_btns):
            hov = btn.collidepoint(mx, my) and not state.is_thinking
            bc = C(theme.COLORS["GREEN_DIM"] if speed_idx == i else theme.COLORS["BG"])
            bor = C(theme.COLORS["GREEN"] if speed_idx == i else theme.COLORS["TEXT_DIM"] if hov else theme.COLORS["BORDER"])
            tc = C(theme.COLORS["GREEN"] if speed_idx == i else theme.COLORS["TEXT_PRIMARY"] if hov else theme.COLORS["TEXT_DIM"])
            pygame.draw.rect(screen, bc, btn, border_radius=4)
            pygame.draw.rect(screen, bor, btn, 1, border_radius=4)
            ts = f11.render(s_lbls[i], True, tc)
            screen.blit(ts, ts.get_rect(center=btn.center))

        screen.blit(f10.render("NODES EXPLORED", True, C(theme.COLORS["TEXT_DIM"])), (px, 240))
        screen.blit(f20.render(str(state.nodes_explored), True, C(theme.COLORS["TEXT_PRIMARY"])), (px, 254))
        screen.blit(f10.render("PATH LENGTH", True, C(theme.COLORS["TEXT_DIM"])), (px+220, 240))
        pl = str(len(state.path)-1) if state.path else "BLOCKED"
        screen.blit(f20.render(pl, True, C(theme.COLORS["TEXT_PRIMARY"])), (px+220, 254))
        screen.blit(f10.render("OPEN SET", True, C(theme.COLORS["TEXT_DIM"])), (px, 284))
        screen.blit(f20.render(str(len(oset)), True, C(theme.COLORS["GREEN"])), (px, 298))
        screen.blit(f10.render("CLOSED SET", True, C(theme.COLORS["TEXT_DIM"])), (px+220, 284))
        screen.blit(f20.render(str(len(cset)), True, C(theme.COLORS["TEXT_MONO"])), (px+220, 298))

        if mode == 'adversarial':
            pygame.draw.rect(screen, C(theme.COLORS["BORDER"]), (610, 325, 470, 1))
            pygame.draw.rect(screen, C(theme.COLORS["TEXT_MONO"]), (844, 324, 3, 3))
            screen.blit(f10.render("ALPHA-BETA PRUNED", True, C(theme.COLORS["TEXT_DIM"])), (px, 330))
            screen.blit(f20.render(str(state.pruned_total), True, C(theme.COLORS["MAC_AMBER"])), (px, 344))
            screen.blit(f10.render("STEP COUNT", True, C(theme.COLORS["TEXT_DIM"])), (px+220, 330))
            screen.blit(f20.render(str(state.step_count), True, C(theme.COLORS["TEXT_PRIMARY"])), (px+220, 344))
            screen.blit(f10.render("SESSION WINS", True, C(theme.COLORS["TEXT_DIM"])), (px, 374))
            screen.blit(f16.render(f"R {red_wins}  B {blue_wins}  D {draws}", True, C(theme.COLORS["TEXT_PRIMARY"])), (px, 388))
            pygame.draw.rect(screen, C(theme.COLORS["BORDER"]), (610, 410, 470, 1))
            pygame.draw.rect(screen, C(theme.COLORS["TEXT_MONO"]), (844, 409, 3, 3))
            screen.blit(f10.render("CONTROL", True, C(theme.COLORS["TEXT_DIM"])), (px, 414))
            
            ai_bg = C(theme.COLORS["PURPLE_DIM"] if not human_mode else theme.COLORS["BG"])
            ai_bor = C(theme.COLORS["PURPLE"] if not human_mode else theme.COLORS["BORDER"])
            ai_tc = C(theme.COLORS["PURPLE"] if not human_mode else theme.COLORS["TEXT_DIM"])
            pygame.draw.rect(screen, ai_bg, btn_ai_blue, border_radius=4)
            pygame.draw.rect(screen, ai_bor, btn_ai_blue, 1, border_radius=4)
            ts = f11.render("AI PLAYS BLUE", True, ai_tc)
            screen.blit(ts, ts.get_rect(center=btn_ai_blue.center))
            
            hm_bg = C(theme.COLORS["PURPLE_DIM"] if human_mode else theme.COLORS["BG"])
            hm_bor = C(theme.COLORS["PURPLE"] if human_mode else theme.COLORS["BORDER"])
            hm_tc = C(theme.COLORS["PURPLE"] if human_mode else theme.COLORS["TEXT_DIM"])
            pygame.draw.rect(screen, hm_bg, btn_human_blue, border_radius=4)
            pygame.draw.rect(screen, hm_bor, btn_human_blue, 1, border_radius=4)
            ts = f11.render("HUMAN PLAYS BLUE", True, hm_tc)
            screen.blit(ts, ts.get_rect(center=btn_human_blue.center))
            
            if human_mode:
                screen.blit(f10.render("Click grid to place wall as Blue", True, C(theme.COLORS["TEXT_DIM"])), (px, 458))

        log_y = 470 if mode == 'adversarial' else 340
        pygame.draw.rect(screen, C(theme.COLORS["BORDER"]), (610, log_y-5, 470, 1))
        pygame.draw.rect(screen, C(theme.COLORS["TEXT_MONO"]), (844, log_y-6, 3, 3))
        screen.blit(f10.render("MOVE LOG", True, C(theme.COLORS["TEXT_DIM"])), (px, log_y))
        if not state.move_log:
            screen.blit(f11.render("No moves yet", True, C(theme.COLORS["TEXT_DIM"])), (px, log_y+20))
        else:
            for i, ml in enumerate(state.move_log):
                screen.blit(f11.render(ml['text'], True, C(ml['color'])), (px, log_y+20 + i*18))

        pygame.draw.rect(screen, C(theme.COLORS["BORDER"]), (610, 620, 470, 1))
        pygame.draw.rect(screen, C(theme.COLORS["TEXT_MONO"]), (844, 619, 3, 3))
        
        st_c = theme.COLORS["BLUE"]
        if state.status == "Red Wins": st_c = theme.COLORS["GREEN"]
        elif state.status == "Blue Wins": st_c = theme.COLORS["MAC_RED"]
        elif state.status == "Draw": st_c = theme.COLORS["TEXT_PRIMARY"]
        theme.draw_tag_pill(screen, px, 628, state.status, st_c)
        
        if state.is_thinking:
            screen.blit(f10.render("thinking...", True, C(theme.COLORS["TEXT_DIM"])), (px+160, 632))

        if mode == 'adversarial':
            draw_btn(btn_run, "STOP" if is_running else "RUN", theme.COLORS["BLUE"], state.is_thinking)
            draw_btn(btn_step, "STEP", theme.COLORS["GREEN"], is_running or state.is_thinking)
            draw_btn(btn_reset, "RESET", theme.COLORS["MAC_AMBER"], state.is_thinking)
            draw_btn(btn_back_adv, "BACK TO HUB", theme.COLORS["MAC_RED"])
        else:
            draw_btn(btn_rerun, "RERUN A*", theme.COLORS["GREEN"])
            draw_btn(btn_back_vis, "BACK TO HUB", theme.COLORS["MAC_RED"])

        frame_counter += 1
        pygame.display.flip()
        clock.tick(60)

if __name__ == "__main__":
    main()
