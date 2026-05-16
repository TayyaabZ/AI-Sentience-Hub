# pyrefly: ignore [missing-import]
import pygame
import json
import os
import time
import psutil

# Global Color Palette
COLORS = {
    "BG": "#070C18",
    "SURFACE": "#0C1620",
    "BORDER": "#192030",
    "TEXT_PRIMARY": "#E2EAF8",
    "TEXT_DIM": "#243040",
    "TEXT_MONO": "#3A5570",
    "GREEN": "#00C97A",
    "GREEN_DIM": "#0A1F10",
    "BLUE": "#3B8BFF",
    "BLUE_DIM": "#071220",
    "PURPLE": "#8B5CF6",
    "PURPLE_DIM": "#120920",
    "WINDOW_BAR": "#0D1524",
    "MAC_RED": "#FF5F56",
    "MAC_AMBER": "#FFBD2E",
    "MAC_GREEN": "#27C93F",
}

# Font cache
_fonts = {}

def get_font(size):
    """Loads and caches consolas font with monospace fallback."""
    if size not in _fonts:
        if not pygame.font.get_init():
            pygame.font.init()
            
        font_name = pygame.font.match_font('consolas')
        if font_name:
            _fonts[size] = pygame.font.Font(font_name, size)
        else:
            _fonts[size] = pygame.font.SysFont('monospace', size)
    return _fonts[size]

def draw_window_bar(surface, width, title="The AI Sentience Hub"):
    """Draws a dark title bar with Mac-style window controls, title, and a live clock."""
    bar_rect = pygame.Rect(0, 0, width, 30)
    pygame.draw.rect(surface, COLORS["WINDOW_BAR"], bar_rect)
    
    # Mac buttons
    center_y = 15
    pygame.draw.circle(surface, COLORS["MAC_RED"], (18, center_y), 7)
    pygame.draw.circle(surface, COLORS["MAC_AMBER"], (38, center_y), 7)
    pygame.draw.circle(surface, COLORS["MAC_GREEN"], (58, center_y), 7)
    
    mx, my = pygame.mouse.get_pos()
    is_hovering_controls = (my < 40 and mx < 80)
    
    if is_hovering_controls:
        sym_color = COLORS["TEXT_MONO"]
        # Red (X)
        pygame.draw.line(surface, sym_color, (15, 12), (21, 18), 1)
        pygame.draw.line(surface, sym_color, (21, 12), (15, 18), 1)
        # Yellow (-)
        pygame.draw.line(surface, sym_color, (34, 15), (42, 15), 1)
        # Green (expand rect)
        pygame.draw.rect(surface, sym_color, (54, 11, 8, 8), 1)
    
    # Title
    font_title = get_font(13)
    title_surf = font_title.render(title, True, COLORS["TEXT_PRIMARY"])
    title_rect = title_surf.get_rect(center=(width // 2, center_y))
    surface.blit(title_surf, title_rect)
    
    # Live clock
    ticks = pygame.time.get_ticks()
    seconds = (ticks // 1000) % 60
    minutes = (ticks // 60000) % 60
    hours = (ticks // 3600000)
    time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    font_clock = get_font(13)
    clock_surf = font_clock.render(time_str, True, COLORS["TEXT_MONO"])
    clock_rect = clock_surf.get_rect(midright=(width - 15, center_y))
    surface.blit(clock_surf, clock_rect)

def draw_tag_pill(surface, x, y, text, color):
    """Draws a small rounded rectangle with text label."""
    font = get_font(10)
    text_surf = font.render(text.upper(), True, color)
    padding_x = 8
    padding_y = 4
    pill_rect = pygame.Rect(x, y, text_surf.get_width() + padding_x * 2, text_surf.get_height() + padding_y * 2)
    
    # Attempt to pick the correct dim background
    dim_color = COLORS["TEXT_DIM"]
    if color == COLORS["GREEN"]: dim_color = COLORS["GREEN_DIM"]
    elif color == COLORS["BLUE"]: dim_color = COLORS["BLUE_DIM"]
    elif color == COLORS["PURPLE"]: dim_color = COLORS["PURPLE_DIM"]
    
    pygame.draw.rect(surface, dim_color, pill_rect, border_radius=10)
    pygame.draw.rect(surface, color, pill_rect, width=1, border_radius=10)
    
    text_rect = text_surf.get_rect(center=pill_rect.center)
    surface.blit(text_surf, text_rect)
    return pill_rect.width

def draw_module_card(surface, x, y, w, h, accent_color, mod_id, title, tags, preview_surface=None):
    """Draws a clickable module card with hover effects."""
    rect = pygame.Rect(x, y, w, h)
    mouse_pos = pygame.mouse.get_pos()
    is_hovered = rect.collidepoint(mouse_pos)
    
    # Card background and border glow
    pygame.draw.rect(surface, COLORS["SURFACE"], rect, border_radius=6)
    border_color = accent_color if is_hovered else COLORS["BORDER"]
    pygame.draw.rect(surface, border_color, rect, width=1, border_radius=6)
    
    # Top accent bar
    top_bar = pygame.Rect(x, y, w, 3)
    pygame.draw.rect(surface, accent_color, top_bar, border_top_left_radius=6, border_top_right_radius=6)
    
    current_y = y + 15
    
    # Mod ID
    font_mod = get_font(10)
    mod_surf = font_mod.render(mod_id, True, accent_color)
    surface.blit(mod_surf, (x + 15, current_y))
    current_y += mod_surf.get_height() + 10
    
    # Preview image surface
    if preview_surface:
        preview_rect = preview_surface.get_rect(centerx=x + w//2, top=current_y)
        surface.blit(preview_surface, preview_rect)
        current_y += preview_surface.get_height() + 15
    else:
        current_y += 100 # Default spacing if no preview
        
    # Title
    font_title = get_font(16)
    title_surf = font_title.render(title, True, COLORS["TEXT_PRIMARY"])
    surface.blit(title_surf, (x + 15, current_y))
    current_y += title_surf.get_height() + 10
    
    # Tags
    current_x = x + 15
    for tag in tags:
        pill_w = draw_tag_pill(surface, current_x, current_y, tag, COLORS["TEXT_MONO"])
        current_x += pill_w + 5
        
    # Launch Button
    btn_h = 30
    btn_rect = pygame.Rect(x + 15, y + h - btn_h - 15, w - 30, btn_h)
    
    btn_bg = accent_color if is_hovered else COLORS["BG"]
    btn_fg = COLORS["BG"] if is_hovered else accent_color
    
    pygame.draw.rect(surface, btn_bg, btn_rect, border_radius=4)
    if not is_hovered:
        pygame.draw.rect(surface, accent_color, btn_rect, width=1, border_radius=4)
        
    font_btn = get_font(13)
    btn_surf = font_btn.render("LAUNCH", True, btn_fg)
    btn_text_rect = btn_surf.get_rect(center=btn_rect.center)
    surface.blit(btn_surf, btn_text_rect)
    
    return rect, is_hovered

def draw_stats_bar(surface, y, dungeons, games, digits):
    """Draws a 4-column row showing global session statistics."""
    width = surface.get_width()
    col_w = width // 4
    
    ticks = pygame.time.get_ticks()
    session_mins = ticks // 60000
    
    stats_data = [
        {"value": str(dungeons), "label": "DUNGEONS EVOLVED", "color": COLORS["GREEN"]},
        {"value": str(games), "label": "GAMES PLAYED", "color": COLORS["BLUE"]},
        {"value": str(digits), "label": "DIGITS DECODED", "color": COLORS["PURPLE"]},
        {"value": f"{session_mins}M", "label": "SESSION TIME", "color": COLORS["TEXT_PRIMARY"]},
    ]
    
    font_val = get_font(28)
    font_lbl = get_font(10)
    
    for i, stat in enumerate(stats_data):
        center_x = (i * col_w) + (col_w // 2)
        
        val_surf = font_val.render(stat["value"], True, stat["color"])
        val_rect = val_surf.get_rect(centerx=center_x, bottom=y + 35)
        surface.blit(val_surf, val_rect)
        
        lbl_surf = font_lbl.render(stat["label"], True, COLORS["TEXT_DIM"])
        lbl_rect = lbl_surf.get_rect(centerx=center_x, top=y + 45)
        surface.blit(lbl_surf, lbl_rect)

def draw_separator(surface, y, width):
    """Draws a subtle 1px line with a dot in the center."""
    line_rect = pygame.Rect(0, y, width, 1)
    pygame.draw.rect(surface, COLORS["BORDER"], line_rect)
    
    center_x = width // 2
    pygame.draw.rect(surface, COLORS["TEXT_MONO"], (center_x - 1, y - 1, 3, 3))

def draw_system_status(surface, y, models_loaded=0):
    now = time.time()
    if not hasattr(draw_system_status, '_cache_time') or now - draw_system_status._cache_time >= 0.5:
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory().used // 1024 // 1024
        draw_system_status._cached_text = f"CPU: {cpu:.0f}%  |  MEM: {mem}MB  |  MODELS LOADED: {models_loaded}"
        draw_system_status._cache_time = now
    width = surface.get_width()
    font = get_font(10)
    surf = font.render(draw_system_status._cached_text, True, COLORS["TEXT_MONO"])
    bg_rect = pygame.Rect(width // 2 - surf.get_width()//2 - 15, y, surf.get_width() + 30, 24)
    pygame.draw.rect(surface, COLORS["SURFACE"], bg_rect, border_radius=12)
    pygame.draw.rect(surface, COLORS["BORDER"], bg_rect, width=1, border_radius=12)
    text_rect = surf.get_rect(center=bg_rect.center)
    surface.blit(surf, text_rect)

class StatsManager:
    """Manages reading and updating stats.json."""
    def __init__(self, filepath="stats.json"):
        self.filepath = filepath
        self.stats = {
            "dungeons_generated": 0,
            "games_played": 0,
            "digits_recognized": 0
        }
        self.load()

    def load(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r') as f:
                    data = json.load(f)
                    self.stats.update(data)
            except Exception as e:
                print(f"Error loading stats: {e}")

    def save(self):
        try:
            with open(self.filepath, 'w') as f:
                json.dump(self.stats, f, indent=4)
        except Exception as e:
            print(f"Error saving stats: {e}")

    def increment(self, key, amount=1):
        if key in self.stats:
            self.stats[key] += amount
            self.save()
