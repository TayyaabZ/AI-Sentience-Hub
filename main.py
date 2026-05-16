# pyrefly: ignore [missing-import]
import pygame
import sys
import os
import math
import ctypes
try:
    ctypes.windll.user32.SetProcessDPIAware()
except:
    pass
import random
import subprocess
import theme

def wrap_text(text, font, max_width):
    words = text.split(' ')
    lines = []
    current_line = []
    for word in words:
        test_line = ' '.join(current_line + [word]) if current_line else word
        w, _ = font.size(test_line)
        if w <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(' '.join(current_line))
            current_line = [word]
    if current_line:
        lines.append(' '.join(current_line))
    return lines

def create_description_surface(text, color, max_width):
    font = theme.get_font(11)
    lines = wrap_text(text, font, max_width)
    line_height = font.get_linesize()
    surf = pygame.Surface((max_width, len(lines) * line_height), pygame.SRCALPHA)
    for i, line in enumerate(lines):
        line_surf = font.render(line, True, color)
        surf.blit(line_surf, (0, i * line_height))
    return surf

def render_modal_content(modal_idx):
    surf = pygame.Surface((700, 480))
    surf.fill(theme.COLORS["SURFACE"])
    
    accent_colors = [theme.COLORS["GREEN"], theme.COLORS["BLUE"], theme.COLORS["PURPLE"]]
    accent = accent_colors[modal_idx]
    
    pygame.draw.rect(surf, accent, (0, 0, 700, 480), 1)
    pygame.draw.rect(surf, accent, (0, 0, 700, 3))
    
    data = [
        {
            "title": "EvoMap: Genetic Algorithm + BFS",
            "body1": "A population of random dungeons is created each generation. Every dungeon is scored by a Fitness Function: BFS checks if a path exists from Spawn to Boss. Dungeons that pass get higher scores. The top 50% survive (Elitism). Pairs of survivors are combined via Row-Splice Crossover — a horizontal band of rows is swapped between two parents. Random tiles are flipped via Mutation (rate: 5%). A Repair pass ensures Spawn, Boss, and Treasure tiles always exist. After 60 generations, the fittest dungeon is displayed.",
            "bullets": [
                "Fitness Function: scores dungeon traversability",
                "BFS (Breadth-First Search): guarantees shortest path check",
                "Crossover: row-splice gene mixing",
                "Mutation: random tile flipping at 5% rate",
                "Elitism: top 50% of population survives"
            ],
            "complexity": "O(P × G × (W×H)) where P=population, G=generations, W×H=grid size (50×50)."
        },
        {
            "title": "Aegis Grid: A* vs Minimax",
            "body1": "The Red agent uses A* Search to find the lowest-cost path to the goal. A* maintains an open set sorted by f(n) = g(n) + h(n), where g is the actual cost from start and h is a heuristic estimate (Manhattan distance). The Blue agent uses Minimax with Alpha-Beta Pruning to choose the single wall placement that maximally lengthens Red's path. It explores a game tree of depth 3, pruning branches where α ≥ β to skip irrelevant moves.",
            "bullets": [
                "A* Search: optimal pathfinding with heuristic guidance",
                "Heuristic h(n): Manhattan distance to goal",
                "Minimax: models adversarial two-player decisions",
                "Alpha-Beta Pruning: skips provably suboptimal branches",
                "Game Tree Depth: 3 ply lookahead"
            ],
            "complexity": "A*: O(E log V). Minimax with pruning: O(b^(d/2)) where b=branching factor, d=depth."
        },
        {
            "title": "Crypto-Glyph: ML Classification",
            "body1": "Your drawing is downscaled to 28×28 pixels (matching MNIST format), flattened to a 784-feature vector, and standardized by a pre-fitted StandardScaler. Three classifiers then predict the digit independently. Naive Bayes assumes feature independence and applies Bayes' theorem: P(class|features) ∝ P(features|class)×P(class). Decision Tree partitions the feature space by Gini impurity at each node. KNN finds the 5 nearest neighbors by Euclidean distance in 784-dimensional space and takes a majority vote.",
            "bullets": [
                "MNIST: 70,000 labeled 28×28 handwritten digit images",
                "Naive Bayes: probabilistic classifier assuming feature independence",
                "Decision Tree: recursive feature-space partitioning",
                "KNN (k=5): majority vote from 5 nearest training samples",
                "StandardScaler: zero-mean unit-variance normalization"
            ],
            "complexity": "Naive Bayes: O(n×d) train, O(d) predict. Decision Tree: O(n×d×log n) train. KNN: O(n×d) per prediction."
        }
    ]
    
    m_data = data[modal_idx]
    current_y = 30
    
    font_title = theme.get_font(24)
    t_surf = font_title.render(m_data["title"], True, theme.COLORS["TEXT_PRIMARY"])
    surf.blit(t_surf, (30, current_y))
    current_y += 40
    
    font_header = theme.get_font(16)
    h1_surf = font_header.render("How It Works", True, accent)
    surf.blit(h1_surf, (30, current_y))
    current_y += 25
    
    font_body = theme.get_font(12)
    lines = wrap_text(m_data["body1"], font_body, 640)
    for line in lines:
        l_surf = font_body.render(line, True, theme.COLORS["TEXT_PRIMARY"])
        surf.blit(l_surf, (30, current_y))
        current_y += 18
        
    current_y += 10
    
    h2_surf = font_header.render("Key Concepts", True, accent)
    surf.blit(h2_surf, (30, current_y))
    current_y += 25
    
    for b in m_data["bullets"]:
        b_surf = font_body.render("• " + b, True, theme.COLORS["TEXT_DIM"])
        surf.blit(b_surf, (40, current_y))
        current_y += 18
        
    current_y += 10
    
    h3_surf = font_header.render("Complexity", True, accent)
    surf.blit(h3_surf, (30, current_y))
    current_y += 25
    
    c_surf = font_body.render(m_data["complexity"], True, theme.COLORS["TEXT_PRIMARY"])
    surf.blit(c_surf, (30, current_y))
    
    return surf

def draw_evomap_thumbnail(t, frame_count):
    surf = pygame.Surface((290, 160))
    surf.fill(theme.COLORS["GREEN_DIM"])
    
    random.seed(frame_count // 90)
    grid = [[random.choice(['wall', 'floor', 'corridor']) for _ in range(10)] for _ in range(10)]
    spawn = (random.randint(0,9), random.randint(0,9))
    boss = (random.randint(0,9), random.randint(0,9))
    while boss == spawn: 
        boss = (random.randint(0,9), random.randint(0,9))
    
    path = []
    curr = spawn
    while curr != boss:
        path.append(curr)
        dx = 1 if boss[0] > curr[0] else -1 if boss[0] < curr[0] else 0
        dy = 1 if boss[1] > curr[1] else -1 if boss[1] < curr[1] else 0
        if dx != 0 and dy != 0:
            if random.random() < 0.5: curr = (curr[0] + dx, curr[1])
            else: curr = (curr[0], curr[1] + dy)
        elif dx != 0: curr = (curr[0] + dx, curr[1])
        else: curr = (curr[0], curr[1] + dy)
    path.append(boss)
    
    for r in range(10):
        for c in range(10):
            cell = grid[r][c]
            color = "#1a1a2e" if cell == 'wall' else "#2a4a3a" if cell == 'floor' else "#1a3a2a"
            pygame.draw.rect(surf, pygame.Color(color), (75 + c*14, 10 + r*14, 14, 14))
            
    pygame.draw.rect(surf, theme.COLORS["GREEN"], (75 + spawn[1]*14, 10 + spawn[0]*14, 14, 14))
    pygame.draw.rect(surf, pygame.Color("#8b0000"), (75 + boss[1]*14, 10 + boss[0]*14, 14, 14))
    
    path_idx = (frame_count // 3) % max(1, len(path))
    for i in range(path_idx + 1):
        pr, pc = path[i]
        pygame.draw.circle(surf, pygame.Color("cyan"), (75 + pc*14 + 7, 10 + pr*14 + 7), 4)
        
    overlay = pygame.Surface((290, 160), pygame.SRCALPHA)
    for y in range(0, 160, 4):
        pygame.draw.line(overlay, (255, 255, 255, 40), (0, y), (290, y))
    surf.blit(overlay, (0,0))
    
    return surf

def draw_aegis_thumbnail(t, frame_count):
    surf = pygame.Surface((290, 160))
    surf.fill(theme.COLORS["BLUE_DIM"])
    
    random.seed(42)
    walls = set()
    while len(walls) < 8:
        r, c = random.randint(0, 11), random.randint(0, 11)
        if (r,c) != (0,0) and (r,c) != (11,11):
            walls.add((r,c))
            
    path = []
    curr = [0,0]
    while curr != [11,11]:
        path.append(tuple(curr))
        if curr[0] < 11: curr[0] += 1
        elif curr[1] < 11: curr[1] += 1
    path.append((11,11))
    
    num_steps = len(path)
    step = int((frame_count % 120) / 120.0 * num_steps)
    
    for r in range(12):
        for c in range(12):
            pygame.draw.rect(surf, theme.COLORS["BORDER"], (73 + c*12, 8 + r*12, 12, 12), 1)
            
    for r,c in walls:
        pygame.draw.rect(surf, theme.COLORS["BORDER"], (73 + c*12, 8 + r*12, 12, 12))
        
    for i in range(step):
        r, c = path[i]
        s = pygame.Surface((12, 12), pygame.SRCALPHA)
        s.fill((59, 139, 255, 100))
        surf.blit(s, (73 + c*12, 8 + r*12))
        
    ar, ac = path[step]
    pygame.draw.circle(surf, pygame.Color("red"), (73 + ac*12 + 6, 8 + ar*12 + 6), 4)
    
    pulse_r = 6 + math.sin(t * 5) * 3
    pygame.draw.circle(surf, theme.COLORS["BLUE"], (73 + ac*12 + 6, 8 + ar*12 + 6), int(pulse_r), 1)
    
    font = theme.get_font(10)
    star = font.render("★", True, pygame.Color("gold"))
    surf.blit(star, (73 + 11*12 + 1, 8 + 11*12 - 1))
    
    return surf

def draw_crypto_thumbnail(t, frame_count):
    surf = pygame.Surface((290, 160))
    surf.fill(theme.COLORS["PURPLE_DIM"])
    
    pygame.draw.rect(surf, theme.COLORS["SURFACE"], (89, 24, 112, 112))
    for i in range(29):
        pygame.draw.line(surf, theme.COLORS["BORDER"], (89 + i*4, 24), (89 + i*4, 24 + 112))
        pygame.draw.line(surf, theme.COLORS["BORDER"], (89, 24 + i*4), (89 + 112, 24 + i*4))
        
    pts_3 = [(0.25,0.25),(0.35,0.15),(0.5,0.1),(0.65,0.15),(0.75,0.25),(0.75,0.35),(0.65,0.45),(0.5,0.5),
             (0.65,0.55),(0.75,0.65),(0.8,0.75),(0.75,0.85),(0.6,0.95),(0.4,0.95),(0.25,0.85)]
    pts_7 = [(0.2,0.2),(0.4,0.2),(0.6,0.2),(0.8,0.2),(0.7,0.4),(0.6,0.6),(0.5,0.8),(0.4,0.9)]
    pts_1 = [(0.5,0.1),(0.5,0.3),(0.5,0.5),(0.5,0.7),(0.5,0.9)]
    
    digits = [("3", pts_3), ("7", pts_7), ("1", pts_1)]
    
    cycle = frame_count % (240 * 3)
    digit_idx = cycle // 240
    local_frame = cycle % 240
    
    digit_label, pts = digits[digit_idx]
    scaled_pts = [(89 + p[0]*112, 24 + p[1]*112) for p in pts]
    
    if local_frame < 180:
        progress = local_frame / 180.0
        total_segs = len(scaled_pts) - 1
        current_seg = progress * total_segs
        idx = int(current_seg)
        frac = current_seg - idx
        
        drawn_pts = scaled_pts[:idx+1]
        if idx < total_segs:
            p1 = scaled_pts[idx]
            p2 = scaled_pts[idx+1]
            interp_p = (p1[0] + (p2[0]-p1[0])*frac, p1[1] + (p2[1]-p1[1])*frac)
            drawn_pts.append(interp_p)
            
        if len(drawn_pts) >= 2:
            pygame.draw.lines(surf, pygame.Color("white"), False, drawn_pts, 3)
    else:
        pygame.draw.lines(surf, pygame.Color("white"), False, scaled_pts, 3)
        if (local_frame // 10) % 2 == 0:
            font = theme.get_font(24)
            text = font.render(f"→ {digit_label}", True, theme.COLORS["PURPLE"])
            surf.blit(text, (89 + 112 + 10, 24 + 50))
            
    return surf

def draw_custom_card(surface, x, y, accent_color, mod_id, title, desc_surf, tags, thumb_surf, modal_open):
    w, h = 320, 430
    rect = pygame.Rect(x, y, w, h)
    mouse_pos = pygame.mouse.get_pos()
    
    is_hovered = rect.collidepoint(mouse_pos) and not modal_open
    
    pygame.draw.rect(surface, theme.COLORS["SURFACE"], rect, border_radius=6)
    border_color = accent_color if is_hovered else theme.COLORS["BORDER"]
    pygame.draw.rect(surface, border_color, rect, width=1, border_radius=6)
    
    top_bar = pygame.Rect(x, y, w, 3)
    pygame.draw.rect(surface, accent_color, top_bar, border_top_left_radius=6, border_top_right_radius=6)
    
    current_y = y + 15
    
    font_mod = theme.get_font(10)
    mod_surf = font_mod.render(mod_id, True, accent_color)
    surface.blit(mod_surf, (x + 15, current_y))
    current_y += mod_surf.get_height() + 10
    
    if thumb_surf:
        surface.blit(thumb_surf, (x + 15, current_y))
        current_y += 160 + 15
        
    font_title = theme.get_font(16)
    title_surf = font_title.render(title, True, theme.COLORS["TEXT_PRIMARY"])
    surface.blit(title_surf, (x + 15, current_y))
    current_y += title_surf.get_height() + 8
    
    if desc_surf:
        surface.blit(desc_surf, (x + 15, current_y))
        current_y += desc_surf.get_height() + 8
        
    current_x = x + 15
    for tag in tags:
        pill_w = theme.draw_tag_pill(surface, current_x, current_y, tag, theme.COLORS["TEXT_MONO"])
        current_x += pill_w + 5
        
    btn_h = 30
    btn_rect = pygame.Rect(x + 15, y + h - btn_h - 15, w - 30, btn_h)
    
    btn_bg = accent_color if is_hovered else theme.COLORS["BG"]
    btn_fg = theme.COLORS["BG"] if is_hovered else accent_color
    
    pygame.draw.rect(surface, btn_bg, btn_rect, border_radius=4)
    if not is_hovered:
        pygame.draw.rect(surface, accent_color, btn_rect, width=1, border_radius=4)
        
    font_btn = theme.get_font(13)
    btn_surf = font_btn.render("LAUNCH", True, btn_fg)
    btn_text_rect = btn_surf.get_rect(center=btn_rect.center)
    surface.blit(btn_surf, btn_text_rect)
    
    i_radius = 10
    i_center = (x + w - 12 - i_radius, y + 12 + i_radius)
    dist = math.hypot(mouse_pos[0] - i_center[0], mouse_pos[1] - i_center[1])
    i_hovered = (dist <= i_radius) and not modal_open
    
    if i_hovered:
        pygame.draw.circle(surface, accent_color, i_center, i_radius)
        i_color = theme.COLORS["BG"]
    else:
        pygame.draw.circle(surface, theme.COLORS["SURFACE"], i_center, i_radius)
        pygame.draw.circle(surface, accent_color, i_center, i_radius, 1)
        i_color = accent_color
        
    font_i = theme.get_font(12)
    i_surf = font_i.render("i", True, i_color)
    i_rect_bounds = i_surf.get_rect(center=i_center)
    surface.blit(i_surf, i_rect_bounds)
    
    i_hit_rect = pygame.Rect(i_center[0] - i_radius, i_center[1] - i_radius, i_radius*2, i_radius*2)
    
    return rect, i_hit_rect

def main():
    os.environ['SDL_VIDEO_CENTERED'] = '1'
    pygame.init()
    WIDTH, HEIGHT = 1200, 800
    
    screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.NOFRAME | pygame.SCALED)
    pygame.display.set_caption("The AI Sentience Hub")
    clock = pygame.time.Clock()

    is_fullscreen = False

    def toggle_fullscreen():
        nonlocal is_fullscreen
        is_fullscreen = not is_fullscreen
        pygame.display.toggle_fullscreen()

    stats_manager = theme.StatsManager()
    stats_path = stats_manager.filepath
    last_stats_mtime = 0

    class Node:
        def __init__(self):
            self.x = random.randint(0, WIDTH)
            self.y = random.randint(0, HEIGHT)
            self.vx = random.uniform(-0.5, 0.5)
            self.vy = random.uniform(-0.5, 0.5)
            self.pulse = random.uniform(0, math.pi * 2)
            self.base_radius = random.uniform(1.5, 3.0)

        def update(self):
            self.x += self.vx
            self.y += self.vy
            
            if self.x < 0 or self.x > WIDTH:
                self.vx *= -1
            if self.y < 0 or self.y > HEIGHT:
                self.vy *= -1
            
            self.pulse += 0.05

        def draw(self, surface):
            r = self.base_radius + math.sin(self.pulse) * 1.0
            pygame.draw.circle(surface, theme.COLORS["TEXT_DIM"], (int(self.x), int(self.y)), int(r))

    nodes = [Node() for _ in range(50)]

    CARD_W, CARD_H = 320, 430
    GAP = 40
    START_X = (WIDTH - (3 * CARD_W + 2 * GAP)) // 2
    CARD_Y = 180

    models_count = sum(1 for f in ["naive_bayes.pkl", "decision_tree.pkl", "knn.pkl"] if os.path.exists(os.path.join("models", f)))

    desc1_text = "Breeds dungeons through natural selection. Rooms and corridors evolve across 60 generations until BFS confirms a Spawn-to-Boss path."
    desc2_text = "A* hunts the shortest path to the goal. Minimax Blue agent counters by placing walls — demonstrating adversarial AI in real time."
    desc3_text = "Draw any digit 0–9. Three ML classifiers — Naive Bayes, Decision Tree, and KNN — instantly vote on what you wrote."
    
    desc1_surf = create_description_surface(desc1_text, theme.COLORS["TEXT_DIM"], CARD_W - 30)
    desc2_surf = create_description_surface(desc2_text, theme.COLORS["TEXT_DIM"], CARD_W - 30)
    desc3_surf = create_description_surface(desc3_text, theme.COLORS["TEXT_DIM"], CARD_W - 30)

    modal_cache = {
        0: render_modal_content(0),
        1: render_modal_content(1),
        2: render_modal_content(2)
    }

    modal_open = False
    modal_index = 0
    frame_count = 0

    running = True
    while running:
        if os.path.exists(stats_path):
            mtime = os.path.getmtime(stats_path)
            if mtime > last_stats_mtime:
                stats_manager.load()
                last_stats_mtime = mtime

        screen.fill(theme.COLORS["BG"])

        for node in nodes:
            node.update()
            node.draw(screen)
            
        for i, n1 in enumerate(nodes):
            for n2 in nodes[i+1:]:
                dist = math.hypot(n1.x - n2.x, n1.y - n2.y)
                if dist < 150:
                    pygame.draw.line(screen, theme.COLORS["BORDER"], (int(n1.x), int(n1.y)), (int(n2.x), int(n2.y)))

        theme.draw_window_bar(screen, WIDTH)

        font_hub = theme.get_font(28)
        title_surf = font_hub.render("T H E   A I   S E N T I E N C E   H U B", True, theme.COLORS["TEXT_PRIMARY"])
        title_rect = title_surf.get_rect(center=(WIDTH // 2, 90))
        screen.blit(title_surf, title_rect)

        t = pygame.time.get_ticks() / 1000.0
        
        thumb1 = draw_evomap_thumbnail(t, frame_count)
        thumb2 = draw_aegis_thumbnail(t, frame_count)
        thumb3 = draw_crypto_thumbnail(t, frame_count)

        rect1, i_rect1 = draw_custom_card(
            screen, START_X, CARD_Y, theme.COLORS["GREEN"],
            "MOD-01", "EvoMap", desc1_surf, ["Genetic Algorithms"], thumb1, modal_open
        )
        
        rect2, i_rect2 = draw_custom_card(
            screen, START_X + CARD_W + GAP, CARD_Y, theme.COLORS["BLUE"],
            "MOD-02", "Aegis Grid", desc2_surf, ["A* vs Minimax"], thumb2, modal_open
        )
        
        rect3, i_rect3 = draw_custom_card(
            screen, START_X + 2*(CARD_W + GAP), CARD_Y, theme.COLORS["PURPLE"],
            "MOD-03", "Crypto-Glyph", desc3_surf, ["ML Recognition"], thumb3, modal_open
        )

        dungeons = stats_manager.stats.get("dungeons_generated", 0)
        games = stats_manager.stats.get("games_played", 0)
        digits = stats_manager.stats.get("digits_recognized", 0)
        
        theme.draw_stats_bar(screen, HEIGHT - 150, dungeons, games, digits)
        theme.draw_system_status(screen, HEIGHT - 40, models_loaded=models_count)

        if modal_open:
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 160))
            screen.blit(overlay, (0, 0))
            
            m_surf = modal_cache[modal_index]
            m_rect = m_surf.get_rect(center=(WIDTH // 2, HEIGHT // 2))
            screen.blit(m_surf, m_rect)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN and (pygame.key.get_mods() & pygame.KMOD_ALT):
                    toggle_fullscreen()
                elif event.key == pygame.K_ESCAPE:
                    if modal_open:
                        modal_open = False
                    
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    mouse_pos = pygame.mouse.get_pos()
                    x, y = mouse_pos
                    
                    if modal_open:
                        m_rect = modal_cache[modal_index].get_rect(center=(WIDTH // 2, HEIGHT // 2))
                        if not m_rect.collidepoint(mouse_pos):
                            modal_open = False
                    else:
                        if y < 40:
                            if x < 28:
                                pygame.quit()
                                sys.exit()
                            elif 28 <= x < 48:
                                if not is_fullscreen:
                                    pygame.display.iconify()
                            elif 48 <= x < 68:
                                toggle_fullscreen()
                                
                        if i_rect1.collidepoint(mouse_pos):
                            modal_index = 0
                            modal_open = True
                        elif i_rect2.collidepoint(mouse_pos):
                            modal_index = 1
                            modal_open = True
                        elif i_rect3.collidepoint(mouse_pos):
                            modal_index = 2
                            modal_open = True
                        else:
                            if rect1.collidepoint(mouse_pos):
                                pygame.display.quit()
                                subprocess.run([sys.executable, "evomap_ui.py"])
                                pygame.display.init()
                                screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.NOFRAME | pygame.SCALED)
                            elif rect2.collidepoint(mouse_pos):
                                pygame.display.quit()
                                subprocess.run([sys.executable, "aegis_grid.py"])
                                pygame.display.init()
                                screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.NOFRAME | pygame.SCALED)
                            elif rect3.collidepoint(mouse_pos):
                                pygame.display.quit()
                                subprocess.run([sys.executable, "crypto_glyph.py"])
                                pygame.display.init()
                                screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.NOFRAME | pygame.SCALED)

        pygame.display.flip()
        clock.tick(60)
        frame_count += 1

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
