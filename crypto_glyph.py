import sys
import ctypes
import json
import os
import math
import threading
from pathlib import Path
import numpy as np
import pygame
import joblib
from PIL import Image, ImageFilter, ImageOps
from sklearn.metrics import confusion_matrix
import theme

try:
    ctypes.windll.user32.SetProcessDPIAware()
except AttributeError:
    pass

def C(h):
    return pygame.Color(h)

# --- Module-level State ---
scaler = None
nb_model = None
dt_model = None
knn_model = None

feedback_buffer = []
dt_feedback_buffer = []
knn_extra_X = []
knn_extra_y = []

last_raw_array = None
last_scaled_array = None

retraining_in_progress = False
model_lock = threading.Lock()

def _retrain_worker(true_label, last_raw_array_local, last_scaled_array_local):
    global nb_model, dt_model, knn_model, retraining_in_progress, scaler
    
    # Naive Bayes
    try:
        nb_model.partial_fit(last_scaled_array_local, np.array([true_label]), classes=np.arange(10))
        joblib.dump(nb_model, "models/naive_bayes.pkl")
    except Exception as e:
        print("NB retrain error:", e)
        
    # Decision Tree
    dt_feedback_buffer.append((last_scaled_array_local, true_label))
    if len(dt_feedback_buffer) >= 5:
        X_all = np.vstack([x for x, _ in dt_feedback_buffer])
        y_all = np.array([y for _, y in dt_feedback_buffer])
        try:
            dt_model.fit(X_all, y_all)
            joblib.dump(dt_model, "models/decision_tree.pkl")
        except Exception as e:
            print("DT retrain error:", e)

    # KNN
    knn_extra_X.append(last_raw_array_local)
    knn_extra_y.append(true_label)
    try:
        if os.path.exists("models/knn_train_data.pkl"):
            X_base, y_base = joblib.load("models/knn_train_data.pkl")
        else:
            X_base, y_base = np.empty((0, last_scaled_array_local.shape[1])), np.empty(0, dtype=int)
            
        if len(X_base) > 0:
            X_combined = np.vstack([X_base, scaler.transform(np.vstack(knn_extra_X))])
            y_combined = np.concatenate([y_base, np.array(knn_extra_y)])
        else:
            X_combined = scaler.transform(np.vstack(knn_extra_X))
            y_combined = np.array(knn_extra_y)
            
        knn_model.fit(X_combined, y_combined)
        joblib.dump(knn_model, "models/knn.pkl")
    except Exception as e:
        print("KNN retrain error:", e)

    with model_lock:
        retraining_in_progress = False

def main():
    global scaler, nb_model, dt_model, knn_model, feedback_buffer
    global dt_feedback_buffer, knn_extra_X, knn_extra_y
    global retraining_in_progress, model_lock
    global last_raw_array, last_scaled_array
    
    pygame.init()
    WIDTH, HEIGHT = 1200, 800
    screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.NOFRAME | pygame.SCALED)
    pygame.display.set_caption("Crypto-Glyph")
    clock = pygame.time.Clock()

    os.makedirs("models", exist_ok=True)
    try:
        feedback_buffer = joblib.load("models/feedback.pkl")
    except Exception:
        feedback_buffer = []
        
    dt_feedback_buffer = []
    knn_extra_X = []
    knn_extra_y = []
    
    retraining_in_progress = False
    model_lock = threading.Lock()
    
    displayed_confidences = {"nb": [0.0]*10, "dt": [0.0]*10, "knn": [0.0]*10}
    target_confidences = {"nb": [0.0]*10, "dt": [0.0]*10, "knn": [0.0]*10}
    
    prediction_made = False
    feedback_given = False
    retraining_done_timer = 0
    
    confusion_modal_open = False
    confusion_modal_tab = 0
    cached_confusion_matrix = None
    
    inline_input_active = False
    inline_digit = ""

    MODEL_DIR = Path("models")
    load_error = False
    accuracies = {"naive_bayes": "N/A", "decision_tree": "N/A", "knn": "N/A"}
    try:
        scaler    = joblib.load(MODEL_DIR / "scaler.pkl")
        nb_model  = joblib.load(MODEL_DIR / "naive_bayes.pkl")
        dt_model  = joblib.load(MODEL_DIR / "decision_tree.pkl")
        knn_model = joblib.load(MODEL_DIR / "knn.pkl")
        with open(MODEL_DIR / "accuracy.json") as f:
            acc_data = json.load(f)
        accuracies["naive_bayes"]   = f'{acc_data["naive_bayes"]["accuracy"] * 100:.2f}%'
        accuracies["decision_tree"] = f'{acc_data["decision_tree"]["accuracy"] * 100:.2f}%'
        accuracies["knn"]           = f'{acc_data["knn"]["accuracy"] * 100:.2f}%'
    except Exception:
        load_error = True

    canvas = pygame.Surface((480, 480))
    canvas.fill((0, 0, 0))
    canvas_rect = pygame.Rect(35, 50, 480, 480)

    is_drawing = False
    eraser_active = False
    brush_radius = 14
    last_draw_pos = None
    stroke_history = []

    has_prediction = False
    nb_pred = nb_proba = dt_pred = dt_proba = knn_pred = knn_proba = None
    preview_surf = None

    btn_s = pygame.Rect(35, 545, 36, 30)
    btn_m = pygame.Rect(79, 545, 36, 30)
    btn_l = pygame.Rect(123, 545, 36, 30)
    btn_eraser = pygame.Rect(167, 545, 72, 30)
    btn_undo = pygame.Rect(247, 545, 60, 30)
    btn_clear = pygame.Rect(315, 545, 60, 30)
    btn_back = pygame.Rect(35, 724, 150, 34)

    def compute_matrix(tab_index):
        nonlocal cached_confusion_matrix
        if len(feedback_buffer) < 10:
            cached_confusion_matrix = None
            return
            
        X_all = np.vstack([x for x, _ in feedback_buffer])
        true_labels = np.array([y for _, y in feedback_buffer])
        
        with model_lock:
            if tab_index == 0:
                pred = nb_model.predict(X_all)
            elif tab_index == 1:
                pred = dt_model.predict(X_all)
            else:
                pred = knn_model.predict(X_all)
                
        cached_confusion_matrix = confusion_matrix(true_labels, pred, labels=list(range(10)))

    def draw_to_canvas(pos):
        color = (0, 0, 0) if eraser_active else (255, 255, 255)
        lx = max(0, min(pos[0] - canvas_rect.x, 479))
        ly = max(0, min(pos[1] - canvas_rect.y, 479))
        pygame.draw.circle(canvas, color, (lx, ly), brush_radius)
        return (lx, ly)

    def fill_between(p1, p2):
        color = (0, 0, 0) if eraser_active else (255, 255, 255)
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        dist = max(abs(dx), abs(dy), 1)
        for i in range(1, dist + 1):
            t = i / dist
            ix = int(p1[0] + dx * t)
            iy = int(p1[1] + dy * t)
            pygame.draw.circle(canvas, color, (ix, iy), brush_radius)

    def handle_feedback(true_label, model_name):
        nonlocal feedback_given, retraining_done_timer
        global feedback_buffer, retraining_in_progress, last_raw_array, last_scaled_array
        
        feedback_buffer.append((last_scaled_array, true_label))
        try:
            joblib.dump(feedback_buffer, "models/feedback.pkl")
        except Exception:
            pass
            
        theme.StatsManager().increment("feedback_given")
        
        with model_lock:
            feedback_given = True
            retraining_in_progress = True
            
        retraining_done_timer = 0
        threading.Thread(
            target=_retrain_worker,
            args=(true_label, last_raw_array, last_scaled_array),
            daemon=True
        ).start()

    def get_full_proba(model, X):
        raw_proba = model.predict_proba(X)[0]
        full = [0.0] * 10
        for i, c in enumerate(model.classes_):
            if 0 <= int(c) <= 9:
                full[int(c)] = float(raw_proba[i])
        return full

    def run_prediction():
        nonlocal has_prediction, nb_pred, nb_proba, dt_pred, dt_proba, knn_pred, knn_proba, preview_surf
        nonlocal prediction_made, feedback_given, inline_input_active, inline_digit
        global last_raw_array, last_scaled_array
        
        if load_error:
            return
        arr = pygame.surfarray.array3d(canvas)
        arr = arr.transpose(1, 0, 2)
        if arr.max() == 0:
            return
        img = Image.fromarray(arr.astype(np.uint8)).convert("L")
        bbox = img.getbbox()
        if bbox is None:
            return
        img = img.crop(bbox)
        w, h = img.size
        scale = 20 / max(w, h)
        new_w, new_h = max(1, int(w * scale)), max(1, int(h * scale))
        img = img.resize((new_w, new_h), Image.LANCZOS)
        img = img.filter(ImageFilter.GaussianBlur(radius=0.5))
        canvas_28 = Image.new("L", (28, 28), 0)
        paste_x = (28 - new_w) // 2
        paste_y = (28 - new_h) // 2
        canvas_28.paste(img, (paste_x, paste_y))
        img = canvas_28
        
        last_raw_array = np.array(img, dtype=np.float32).flatten()
        last_scaled_array = scaler.transform(last_raw_array.reshape(1, -1))
        
        with model_lock:
            nb_pred  = int(nb_model.predict(last_scaled_array)[0])
            nb_proba  = get_full_proba(nb_model, last_scaled_array)
            dt_pred  = int(dt_model.predict(last_scaled_array)[0])
            dt_proba  = get_full_proba(dt_model, last_scaled_array)
            knn_pred = int(knn_model.predict(last_scaled_array)[0])
            knn_proba = get_full_proba(knn_model, last_scaled_array)
            
        target_confidences["nb"] = nb_proba
        target_confidences["dt"] = dt_proba
        target_confidences["knn"] = knn_proba
            
        img_arr = np.array(img)
        rgb_arr = np.stack([img_arr] * 3, axis=-1)
        preview_surf = pygame.transform.scale(
            pygame.image.frombuffer(rgb_arr.tobytes(), (28, 28), "RGB"),
            (112, 112)
        )
        has_prediction = True
        prediction_made = True
        feedback_given = False
        inline_input_active = False
        inline_digit = ""
        theme.StatsManager().increment("digits_recognized")

    def draw_toolbar_btn(r, label, active):
        mx, my = pygame.mouse.get_pos()
        hover = r.collidepoint(mx, my) and not confusion_modal_open
        bg = C(theme.COLORS["PURPLE_DIM"]) if active else C(theme.COLORS["BG"])
        border = C(theme.COLORS["PURPLE"]) if active else C(theme.COLORS["BORDER"])
        txt_c = C(theme.COLORS["PURPLE"]) if active else C(theme.COLORS["TEXT_DIM"])
        if hover and not active:
            txt_c = C(theme.COLORS["TEXT_PRIMARY"])
        pygame.draw.rect(screen, bg, r, border_radius=4)
        pygame.draw.rect(screen, border, r, 1, border_radius=4)
        f = theme.get_font(11)
        t = f.render(label, True, txt_c)
        screen.blit(t, t.get_rect(center=r.center))

    def draw_btn(r, label, bg_color, fg_color):
        mx, my = pygame.mouse.get_pos()
        hover = r.collidepoint(mx, my) and not confusion_modal_open
        color_bg = C(bg_color) if hover else C(theme.COLORS["SURFACE"])
        color_border = C(bg_color)
        color_txt = C(theme.COLORS["BG"]) if hover else C(fg_color)
        pygame.draw.rect(screen, color_bg, r, border_radius=6)
        pygame.draw.rect(screen, color_border, r, 1, border_radius=6)
        f = theme.get_font(12)
        t = f.render(label, True, color_txt)
        screen.blit(t, t.get_rect(center=r.center))

    def draw_model_card(card_y, model_name, acc_key, pred, proba, m_key, accent_color_key):
        card_rect = pygame.Rect(608, card_y, 575, 195)
        pygame.draw.rect(screen, C(theme.COLORS["SURFACE"]), card_rect)
        pygame.draw.rect(screen, C(theme.COLORS["BORDER"]), card_rect, 1)
        pygame.draw.rect(screen, C(theme.COLORS["PURPLE"]), pygame.Rect(608, card_y, 3, 195))

        f13 = theme.get_font(13)
        name_surf = f13.render(model_name, True, C(theme.COLORS["TEXT_PRIMARY"]))
        screen.blit(name_surf, (622, card_y + 12))

        pill_font = theme.get_font(10)
        pill_text = pill_font.render(accuracies[acc_key].upper(), True, C(theme.COLORS["PURPLE"]))
        pill_w = pill_text.get_width() + 16
        pill_x = 1183 - pill_w
        theme.draw_tag_pill(screen, pill_x, card_y + 12, accuracies[acc_key], C(theme.COLORS["PURPLE"]))

        f48 = theme.get_font(48)
        f20 = theme.get_font(20)
        f9 = theme.get_font(9)

        if has_prediction and pred is not None:
            digit_surf = f48.render(str(pred), True, C(theme.COLORS["PURPLE"]))
            screen.blit(digit_surf, (622, card_y + 32))

            conf_surf = f20.render(f"{proba[pred]*100:.1f}%", True, C(theme.COLORS["TEXT_PRIMARY"]))
            screen.blit(conf_surf, (690, card_y + 36))

            conf_label = f9.render("CONFIDENCE", True, C(theme.COLORS["TEXT_DIM"]))
            screen.blit(conf_label, (690, card_y + 62))

            for i in range(10):
                y_pos = card_y + 88 + i * 10
                d_label = f9.render(str(i), True, C(theme.COLORS["TEXT_DIM"]))
                d_rect = d_label.get_rect(right=632, centery=y_pos + 3)
                screen.blit(d_label, d_rect)

                bar_w = int(displayed_confidences[m_key][i] * 330)
                bar_color = C(theme.COLORS[accent_color_key]) if i == pred else C(theme.COLORS["TEXT_DIM"])
                if bar_w > 0:
                    pygame.draw.rect(screen, bar_color, pygame.Rect(637, y_pos, bar_w, 7))
                    edge_surf = pygame.Surface((2, 7), pygame.SRCALPHA)
                    edge_surf.fill((255, 255, 255, 200))
                    screen.blit(edge_surf, (637 + bar_w - 2, y_pos))

                pct_surf = f9.render(f"{displayed_confidences[m_key][i]*100:.0f}%", True, C(theme.COLORS["TEXT_DIM"]))
                screen.blit(pct_surf, (972, y_pos))
        else:
            digit_surf = f48.render("—", True, C(theme.COLORS["TEXT_DIM"]))
            screen.blit(digit_surf, (622, card_y + 32))

            for i in range(10):
                y_pos = card_y + 88 + i * 10
                d_label = f9.render(str(i), True, C(theme.COLORS["TEXT_DIM"]))
                d_rect = d_label.get_rect(right=632, centery=y_pos + 3)
                screen.blit(d_label, d_rect)

                pct_surf = f9.render("0%", True, C(theme.COLORS["TEXT_DIM"]))
                screen.blit(pct_surf, (972, y_pos))

    nb_fb_btn = pygame.Rect(623, 746, 110, 34)
    dt_fb_btn = pygame.Rect(743, 746, 110, 34)
    knn_fb_btn = pygame.Rect(863, 746, 110, 34)
    none_fb_btn = pygame.Rect(983, 746, 110, 34)
    input_fb_rect = pygame.Rect(1105, 746, 30, 34)
    confirm_fb_btn = pygame.Rect(1140, 746, 34, 34)
    conf_btn_rect = pygame.Rect(608, 698, 150, 24)

    while True:
        dt_ms = clock.tick(60)
        mx, my = pygame.mouse.get_pos()
        
        for m in ["nb", "dt", "knn"]:
            for i in range(10):
                target = target_confidences[m][i]
                current = displayed_confidences[m][i]
                displayed_confidences[m][i] += (target - current) * (dt_ms / 100.0)
                if abs(target - displayed_confidences[m][i]) < 0.005:
                    displayed_confidences[m][i] = target

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                sys.exit(0)
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if confusion_modal_open:
                        confusion_modal_open = False
                    else:
                        sys.exit(0)
                if inline_input_active and event.unicode.isdigit():
                    inline_digit = event.unicode
                    
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    if pygame.Rect(11, 8, 14, 14).collidepoint(mx, my):
                        sys.exit(0)
                        
                    if confusion_modal_open:
                        modal_rect = pygame.Rect(210, 120, 780, 560)
                        if not modal_rect.collidepoint(mx, my):
                            confusion_modal_open = False
                        else:
                            for i in range(3):
                                t_rect = pygame.Rect(210 + 390 - 245 + i * 165, 166, 160, 30)
                                if t_rect.collidepoint(mx, my):
                                    confusion_modal_tab = i
                                    compute_matrix(i)
                        continue

                    if len(feedback_buffer) >= 10 and conf_btn_rect.collidepoint(mx, my):
                        confusion_modal_open = True
                        confusion_modal_tab = 0
                        compute_matrix(0)
                        continue

                    with model_lock:
                        rip = retraining_in_progress
                        
                    if prediction_made and not feedback_given and not rip:
                        if nb_fb_btn.collidepoint(mx, my):
                            handle_feedback(nb_pred, "nb")
                        elif dt_fb_btn.collidepoint(mx, my):
                            handle_feedback(dt_pred, "dt")
                        elif knn_fb_btn.collidepoint(mx, my):
                            handle_feedback(knn_pred, "knn")
                        elif not inline_input_active and none_fb_btn.collidepoint(mx, my):
                            inline_input_active = True
                        elif inline_input_active and confirm_fb_btn.collidepoint(mx, my):
                            if inline_digit != "":
                                handle_feedback(int(inline_digit), "all")

                    if canvas_rect.collidepoint(mx, my):
                        stroke_history.append(canvas.copy())
                        if len(stroke_history) > 20:
                            stroke_history.pop(0)
                        is_drawing = True
                        last_draw_pos = draw_to_canvas(event.pos)
                    if btn_s.collidepoint(mx, my):
                        brush_radius = 8
                        eraser_active = False
                    elif btn_m.collidepoint(mx, my):
                        brush_radius = 14
                        eraser_active = False
                    elif btn_l.collidepoint(mx, my):
                        brush_radius = 22
                        eraser_active = False
                    elif btn_eraser.collidepoint(mx, my):
                        eraser_active = not eraser_active
                    elif btn_undo.collidepoint(mx, my):
                        if stroke_history:
                            canvas.blit(stroke_history.pop(), (0, 0))
                    elif btn_clear.collidepoint(mx, my):
                        canvas.fill((0, 0, 0))
                        stroke_history.clear()
                        has_prediction = False
                        prediction_made = False
                        feedback_given = False
                        inline_input_active = False
                        inline_digit = ""
                        for m in ["nb", "dt", "knn"]:
                            target_confidences[m] = [0.0]*10
                            displayed_confidences[m] = [0.0]*10
                        nb_pred = nb_proba = dt_pred = dt_proba = knn_pred = knn_proba = None
                        preview_surf = None
                    elif btn_back.collidepoint(mx, my):
                        sys.exit(0)
            if event.type == pygame.MOUSEMOTION:
                if is_drawing and not confusion_modal_open and canvas_rect.collidepoint(event.pos):
                    new_pos = draw_to_canvas(event.pos)
                    if last_draw_pos:
                        fill_between(last_draw_pos, new_pos)
                    last_draw_pos = new_pos
            if event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1 and is_drawing and not confusion_modal_open:
                    is_drawing = False
                    last_draw_pos = None
                    run_prediction()

        screen.fill(C(theme.COLORS["BG"]))
        theme.draw_window_bar(screen, 1200, "CRYPTO-GLYPH // DIGIT ORACLE")

        screen.blit(canvas, canvas_rect)
        hint_surf = theme.get_font(11).render("Draw large \u2014 fill the canvas", True, C(theme.COLORS["TEXT_DIM"]))
        screen.blit(hint_surf, (35, 534))
        pygame.draw.rect(screen, C(theme.COLORS["PURPLE"]), canvas_rect, 1)

        draw_toolbar_btn(btn_s, "S", brush_radius == 8 and not eraser_active)
        draw_toolbar_btn(btn_m, "M", brush_radius == 14 and not eraser_active)
        draw_toolbar_btn(btn_l, "L", brush_radius == 22 and not eraser_active)
        draw_toolbar_btn(btn_eraser, "ERASER", eraser_active)
        draw_toolbar_btn(btn_undo, "UNDO", False)
        draw_toolbar_btn(btn_clear, "CLEAR", False)

        f9 = theme.get_font(9)
        preview_label = f9.render("28×28 INPUT PREVIEW", True, C(theme.COLORS["TEXT_DIM"]))
        screen.blit(preview_label, (35, 590))

        preview_rect = pygame.Rect(35, 600, 112, 112)
        if has_prediction and preview_surf:
            screen.blit(preview_surf, preview_rect)
        else:
            pygame.draw.rect(screen, C(theme.COLORS["SURFACE"]), preview_rect)
        pygame.draw.rect(screen, C(theme.COLORS["BORDER"]), preview_rect, 1)

        pygame.draw.line(screen, C(theme.COLORS["BORDER"]), (590, 40), (590, 800), 1)

        f20 = theme.get_font(20)
        title_surf = f20.render("DIGIT ORACLE", True, C(theme.COLORS["PURPLE"]))
        screen.blit(title_surf, (612, 42))

        subtitle_surf = f9.render("NEURAL CLASSIFICATION RESULTS", True, C(theme.COLORS["TEXT_DIM"]))
        screen.blit(subtitle_surf, (612, 68))

        if load_error:
            err_font = theme.get_font(20)
            err_surf = err_font.render("MODELS NOT FOUND", True, C(theme.COLORS["MAC_RED"]))
            err_rect = err_surf.get_rect(center=(900, 380))
            screen.blit(err_surf, err_rect)
            hint_font = theme.get_font(13)
            hint_surf = hint_font.render("Run  train_models.py  first", True, C(theme.COLORS["TEXT_DIM"]))
            hint_rect = hint_surf.get_rect(center=(900, 415))
            screen.blit(hint_surf, hint_rect)
        else:
            draw_model_card(90, "NAIVE BAYES", "naive_bayes", nb_pred, nb_proba, "nb", "GREEN")
            draw_model_card(290, "DECISION TREE", "decision_tree", dt_pred, dt_proba, "dt", "BLUE")
            draw_model_card(490, "KNN (k=5)", "knn", knn_pred, knn_proba, "knn", "PURPLE")

        alpha = 255 if len(feedback_buffer) >= 10 else int(255 * 0.4)
        cbtn_surf = pygame.Surface((150, 24), pygame.SRCALPHA)
        pygame.draw.rect(cbtn_surf, (*C(theme.COLORS["BORDER"])[:3], alpha), (0, 0, 150, 24), 1, border_radius=4)
        c_font = theme.get_font(11)
        c_text = c_font.render("CONFUSION MATRIX", True, (*C(theme.COLORS["TEXT_DIM"])[:3], alpha))
        cbtn_surf.blit(c_text, c_text.get_rect(center=(75, 12)))
        screen.blit(cbtn_surf, conf_btn_rect.topleft)

        if len(feedback_buffer) < 10 and conf_btn_rect.collidepoint(mx, my) and not confusion_modal_open:
            tt_font = theme.get_font(10)
            tt_surf = tt_font.render("Need 10+ corrections to generate", True, C(theme.COLORS["TEXT_DIM"]))
            screen.blit(tt_surf, (mx + 10, my + 10))

        if prediction_made and not feedback_given:
            panel_rect = pygame.Rect(608, 728, 575, 68)
            pygame.draw.rect(screen, C(theme.COLORS["SURFACE"]), panel_rect)
            pygame.draw.rect(screen, C(theme.COLORS["BORDER"]), panel_rect, 1)

            lbl_font = theme.get_font(11)
            lbl_surf = lbl_font.render("WHICH MODEL WAS RIGHT?", True, C(theme.COLORS["TEXT_MONO"]))
            screen.blit(lbl_surf, (618, 732))

            def draw_fb_btn(rect, label, color_key, is_none=False):
                with model_lock:
                    rip = retraining_in_progress
                hover = rect.collidepoint(mx, my) and not confusion_modal_open and not rip
                btn_alpha = int(255 * 0.5) if rip else 255
                b_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
                b_color = (*C(theme.COLORS[color_key])[:3], btn_alpha)
                
                if hover and not is_none:
                    fill_color = (*C(theme.COLORS[color_key])[:3], int(255 * 0.6))
                    pygame.draw.rect(b_surf, fill_color, (0, 0, rect.width, rect.height), border_radius=6)
                
                pygame.draw.rect(b_surf, b_color, (0, 0, rect.width, rect.height), 1, border_radius=6)
                t_surf = theme.get_font(11).render(label, True, b_color)
                b_surf.blit(t_surf, t_surf.get_rect(center=(rect.width//2, rect.height//2)))
                screen.blit(b_surf, rect.topleft)

            draw_fb_btn(nb_fb_btn, "NB ✓", "GREEN")
            draw_fb_btn(dt_fb_btn, "DT ✓", "BLUE")
            draw_fb_btn(knn_fb_btn, "KNN ✓", "PURPLE")

            with model_lock:
                rip = retraining_in_progress

            if not inline_input_active:
                draw_fb_btn(none_fb_btn, "NONE", "TEXT_DIM")
            else:
                n_lbl = theme.get_font(11).render("None — correct is:", True, C(theme.COLORS["TEXT_DIM"]))
                if rip:
                    n_lbl.set_alpha(int(255 * 0.5))
                screen.blit(n_lbl, (none_fb_btn.x - 20, none_fb_btn.y + 10))
                
                i_surf = pygame.Surface((30, 34), pygame.SRCALPHA)
                i_color = (*C(theme.COLORS["TEXT_PRIMARY"])[:3], int(255 * 0.5) if rip else 255)
                pygame.draw.rect(i_surf, i_color, (0, 0, 30, 34), 1, border_radius=4)
                if inline_digit:
                    d_surf = theme.get_font(14).render(inline_digit, True, i_color)
                    i_surf.blit(d_surf, d_surf.get_rect(center=(15, 17)))
                screen.blit(i_surf, input_fb_rect.topleft)

                draw_fb_btn(confirm_fb_btn, "✓", "TEXT_PRIMARY", is_none=True)

        with model_lock:
            is_retraining = retraining_in_progress

        if is_retraining:
            pulse_alpha = int(abs(math.sin(pygame.time.get_ticks() / 400.0)) * 255)
            r_surf = theme.get_font(11).render("UPDATING MODELS...", True, C(theme.COLORS["TEXT_DIM"]))
            r_surf.set_alpha(pulse_alpha)
            screen.blit(r_surf, (608, 782))
        elif retraining_done_timer > 0:
            r_surf = theme.get_font(11).render("✓ Models updated", True, C(theme.COLORS["GREEN"]))
            screen.blit(r_surf, (608, 782))
            retraining_done_timer -= 1
            
        stats = theme.StatsManager().stats
        corr_n = stats.get("feedback_given", 0)
        corr_surf = theme.get_font(11).render(f"TOTAL CORRECTIONS: {corr_n}", True, C(theme.COLORS["TEXT_DIM"]))
        screen.blit(corr_surf, (1183 - corr_surf.get_width() - 5, 782))

        draw_btn(btn_back, "\u2190 BACK TO HUB", theme.COLORS["MAC_RED"], theme.COLORS["MAC_RED"])

        if confusion_modal_open:
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((*C(theme.COLORS["BG"])[:3], 160))
            screen.blit(overlay, (0, 0))

            m_rect = pygame.Rect(210, 120, 780, 560)
            pygame.draw.rect(screen, C(theme.COLORS["SURFACE"]), m_rect)
            pygame.draw.rect(screen, C(theme.COLORS["BORDER"]), m_rect, 1)
            pygame.draw.rect(screen, C(theme.COLORS["PURPLE"]), pygame.Rect(210, 120, 780, 3))

            t_font = theme.get_font(14)
            title = t_font.render("CONFUSION MATRIX VIEWER", True, C(theme.COLORS["TEXT_PRIMARY"]))
            screen.blit(title, title.get_rect(center=(600, 136 + 16)))

            tab_names = ["Naive Bayes", "Decision Tree", "KNN"]
            tab_colors = ["GREEN", "BLUE", "PURPLE"]

            for i in range(3):
                t_rect = pygame.Rect(210 + 390 - 245 + i * 165, 166, 160, 30)
                is_active = (i == confusion_modal_tab)
                t_col = C(theme.COLORS[tab_colors[i]])
                
                if is_active:
                    pygame.draw.rect(screen, (*t_col[:3], int(255 * 0.3)), t_rect, border_radius=4)
                    pygame.draw.rect(screen, t_col, t_rect, 1, border_radius=4)
                    t_text = theme.get_font(11).render(tab_names[i], True, t_col)
                else:
                    pygame.draw.rect(screen, C(theme.COLORS["BORDER"]), t_rect, 1, border_radius=4)
                    t_text = theme.get_font(11).render(tab_names[i], True, C(theme.COLORS["TEXT_DIM"]))
                    
                screen.blit(t_text, t_text.get_rect(center=t_rect.center))

            if len(feedback_buffer) < 10:
                e_font = theme.get_font(12)
                e_surf = e_font.render("Not enough data yet — make at least 10 corrections", True, C(theme.COLORS["TEXT_DIM"]))
                screen.blit(e_surf, e_surf.get_rect(center=(600, 360)))
            else:
                grid_y = 225
                grid_x = 380
                active_color = C(theme.COLORS[tab_colors[confusion_modal_tab]])
                bg_color = C(theme.COLORS["BG"])

                if cached_confusion_matrix is not None:
                    for row in range(10):
                        row_sum = max(1, sum(cached_confusion_matrix[row]))
                        for col in range(10):
                            val = cached_confusion_matrix[row][col]
                            intensity = val / row_sum
                            
                            c_x = grid_x + col * 44
                            c_y = grid_y + row * 44
                            
                            r = int(bg_color.r + (active_color.r - bg_color.r) * intensity)
                            g = int(bg_color.g + (active_color.g - bg_color.g) * intensity)
                            b = int(bg_color.b + (active_color.b - bg_color.b) * intensity)
                            
                            cell_rect = pygame.Rect(c_x, c_y, 44, 44)
                            pygame.draw.rect(screen, (r, g, b), cell_rect)
                            
                            if row == col:
                                pygame.draw.rect(screen, (255, 255, 255), cell_rect.inflate(-2, -2), 1)

                            if val > 0:
                                txt_c = bg_color if intensity > 0.3 else C(theme.COLORS["TEXT_PRIMARY"])
                                v_surf = theme.get_font(10).render(str(val), True, txt_c)
                                screen.blit(v_surf, v_surf.get_rect(center=cell_rect.center))
                                
                    for row in range(10):
                        l_surf = theme.get_font(11).render(str(row), True, C(theme.COLORS["TEXT_DIM"]))
                        screen.blit(l_surf, l_surf.get_rect(right=grid_x - 10, centery=grid_y + row * 44 + 22))
                    for col in range(10):
                        l_surf = theme.get_font(11).render(str(col), True, C(theme.COLORS["TEXT_DIM"]))
                        screen.blit(l_surf, l_surf.get_rect(centerx=grid_x + col * 44 + 22, bottom=grid_y - 10))
                        
                    true_surf = theme.get_font(11).render("True", True, C(theme.COLORS["TEXT_DIM"]))
                    true_surf = pygame.transform.rotate(true_surf, 90)
                    screen.blit(true_surf, true_surf.get_rect(right=grid_x - 30, centery=grid_y + 220))
                    
                    pred_surf = theme.get_font(11).render("Predicted", True, C(theme.COLORS["TEXT_DIM"]))
                    screen.blit(pred_surf, pred_surf.get_rect(centerx=grid_x + 220, top=grid_y + 450))

        pygame.display.flip()

if __name__ == "__main__":
    main()
