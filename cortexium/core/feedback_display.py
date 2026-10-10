import cv2
import numpy as np
import time
from PIL import Image, ImageDraw, ImageFont
import os

class EasedValue:
    def __init__(self, start_val, ease_factor=0.15):
        self.current = float(start_val)
        self.target = float(start_val)
        self.ease_factor = ease_factor

    def update(self, target_val):
        self.target = float(target_val)
        self.current += (self.target - self.current) * self.ease_factor
        return self.current

class FeedbackDisplay:
    def __init__(self):
        # Premium glassmorphic HUD colors (BGR format)
        self.ui_colors = {
            'safe': (200, 255, 100),        # Soft Teal/Neon Green
            'warning': (50, 200, 255),      # Soft Amber
            'danger': (123, 153, 240),      # Coral/Orange-Red (BGR format: R=240, G=153, B=123)
            'bg_glass': (255, 255, 255),    # Frosted white basis
            'bg_glass_dark': (20, 20, 20),  # Frosted dark basis
            'text_light': (250, 250, 250),  # Off-White
            'nav_neon': (200, 255, 50),     # Ray-Ban Meta Neon Green/Teal
        }
        
        # Load premium system font
        font_paths = [
            "C:\\Windows\\Fonts\\SegoeUI.ttf",
            "C:\\Windows\\Fonts\\segoeui.ttf",
            "C:\\Windows\\Fonts\\arial.ttf",
            "C:\\Windows\\Fonts\\Arial.ttf"
        ]
        
        selected_font = None
        for path in font_paths:
            if os.path.exists(path):
                selected_font = path
                break
                
        # Create a dummy PIL image/draw context to measure text sizes
        dummy_img = Image.new('RGB', (1, 1))
        self.font_draw = ImageDraw.Draw(dummy_img)
        
        try:
            if selected_font:
                self.font_large = ImageFont.truetype(selected_font, 22)
                self.font_hazard = ImageFont.truetype(selected_font, 20)  # Large hazard text (size 20)
                self.font_medium = ImageFont.truetype(selected_font, 13)
                self.font_small = ImageFont.truetype(selected_font, 10)
                print(f"🎨 FeedbackDisplay: Loaded premium system font: '{selected_font}'")
            else:
                self.font_large = ImageFont.load_default()
                self.font_hazard = ImageFont.load_default()
                self.font_medium = ImageFont.load_default()
                self.font_small = ImageFont.load_default()
                print("⚠️ FeedbackDisplay: Sans-serif font not found. Using default font.")
        except Exception as font_err:
            self.font_large = ImageFont.load_default()
            self.font_hazard = ImageFont.load_default()
            self.font_medium = ImageFont.load_default()
            self.font_small = ImageFont.load_default()
            print(f"⚠️ FeedbackDisplay Error loading TrueType font: {font_err}. Using default.")

        # Eased value objects for HUD telemetry
        self.score_ease = EasedValue(100.0, 0.15)
        self.steering_offset_ease = EasedValue(0.0, 0.15)
        
        # Hazard banner animation state
        self.active_hazard = None
        self.banner_alpha = EasedValue(0.0, 0.15)
        self.banner_scale = EasedValue(0.0, 0.15)
        
        # Path properties
        self.current_bend = 0.0
        self.target_bends = {
            'straight': 0.0,
            'curve_left': -60.0,
            'curve_right': 60.0,
            'turn_left': -180.0,
            'turn_right': 180.0,
            'u_turn': -260.0,
            'merge_left': 0.0,
            'merge_right': 0.0
        }
        self.current_shift = 0.0
        self.target_shifts = {
            'straight': 0.0,
            'curve_left': 0.0,
            'curve_right': 0.0,
            'turn_left': 0.0,
            'turn_right': 0.0,
            'u_turn': -50.0,
            'merge_left': -120.0,
            'merge_right': 120.0
        }
        self.smooth_vp_x = None

    def _draw_glass_panel(self, img, x, y, w, h, bg_color=(255, 255, 255), border_color=(255, 255, 255), alpha=0.18, border_alpha=0.6, corner_radius=12):
        """
        Draws a premium glassmorphic panel with blurred background,
        frosted fill, and a clean thin border.
        """
        ih, iw = img.shape[:2]
        x1, y1 = max(0, int(x)), max(0, int(y))
        x2, y2 = min(iw, int(x + w)), min(ih, int(y + h))
        if x2 <= x1 or y2 <= y1:
            return
            
        roi = img[y1:y2, x1:x2].copy()
        
        # Apply Gaussian Blur (only if ROI is big enough)
        if (x2 - x1) > 4 and (y2 - y1) > 4:
            blurred_roi = cv2.GaussianBlur(roi, (15, 15), 0)
        else:
            blurred_roi = roi
            
        # Draw translucent filled overlay
        overlay = blurred_roi.copy()
        color_fill = np.zeros_like(blurred_roi)
        color_fill[:] = bg_color
        cv2.addWeighted(color_fill, alpha, blurred_roi, 1.0 - alpha, 0, overlay)
        
        # Create rounded corner mask
        mask = np.zeros((y2 - y1, x2 - x1), dtype=np.uint8)
        r = min(corner_radius, (x2 - x1) // 2, (y2 - y1) // 2)
        r = max(0, r)
        
        if r > 0:
            cv2.rectangle(mask, (r, 0), (x2 - x1 - r, y2 - y1), 255, -1)
            cv2.rectangle(mask, (0, r), (x2 - x1, y2 - y1 - r), 255, -1)
            cv2.circle(mask, (r, r), r, 255, -1)
            cv2.circle(mask, (x2 - x1 - r, r), r, 255, -1)
            cv2.circle(mask, (r, y2 - y1 - r), r, 255, -1)
            cv2.circle(mask, (x2 - x1 - r, y2 - y1 - r), r, 255, -1)
        else:
            mask[:] = 255
            
        # Apply mask
        mask_inv = cv2.bitwise_not(mask)
        bg = cv2.bitwise_and(roi, roi, mask=mask_inv)
        fg = cv2.bitwise_and(overlay, overlay, mask=mask)
        img[y1:y2, x1:x2] = cv2.add(bg, fg)
        
        # Draw rounded border (clean outer lines with no inner grid intersections)
        border_overlay = img[y1:y2, x1:x2].copy()
        bh, bw = border_overlay.shape[:2]
        if r > 0:
            # Draw individual straight side lines
            cv2.line(border_overlay, (r, 0), (bw - r, 0), border_color, 1, cv2.LINE_AA)
            cv2.line(border_overlay, (r, bh - 1), (bw - r, bh - 1), border_color, 1, cv2.LINE_AA)
            cv2.line(border_overlay, (0, r), (0, bh - r), border_color, 1, cv2.LINE_AA)
            cv2.line(border_overlay, (bw - 1, r), (bw - 1, bh - r), border_color, 1, cv2.LINE_AA)
            # Draw corner arcs
            cv2.ellipse(border_overlay, (r, r), (r, r), 180, 0, 90, border_color, 1, cv2.LINE_AA)
            cv2.ellipse(border_overlay, (bw - r, r), (r, r), 270, 0, 90, border_color, 1, cv2.LINE_AA)
            cv2.ellipse(border_overlay, (r, bh - r), (r, r), 90, 0, 90, border_color, 1, cv2.LINE_AA)
            cv2.ellipse(border_overlay, (bw - r, bh - r), (r, r), 0, 0, 90, border_color, 1, cv2.LINE_AA)
        else:
            cv2.rectangle(border_overlay, (0, 0), (bw - 1, bh - 1), border_color, 1, cv2.LINE_AA)
            
        img[y1:y2, x1:x2] = cv2.addWeighted(border_overlay, border_alpha, img[y1:y2, x1:x2], 1.0 - border_alpha, 0)

    def _get_text_size(self, text, font):
        """Robust helper to get text width and height across Pillow versions."""
        try:
            bbox = self.font_draw.textbbox((0, 0), text, font=font)
            return bbox[2] - bbox[0], bbox[3] - bbox[1]
        except Exception:
            try:
                return font.getsize(text)
            except Exception:
                return len(text) * 7, 12

    def _draw_pil_text(self, img, text, x, y, font, color=(255, 255, 255), anchor="la"):
        """
        Draws high-quality anti-aliased text using PIL on a local ROI to maximize performance.
        """
        # Measure text size using robust cross-version helper
        tw, th = self._get_text_size(text, font)
        
        pad = 8  # Increased padding to prevent edge clipping on ascenders/descenders
        roi_w = tw + pad * 2
        roi_h = th + pad * 2
        
        # Adjust alignment coordinates for ROI crop
        if anchor == "la":
            tx, ty = x, y
        elif anchor == "mm":
            tx, ty = x - roi_w // 2, y - roi_h // 2
        elif anchor == "lm":
            tx, ty = x, y - roi_h // 2
        elif anchor == "ra":
            tx, ty = x - roi_w, y
        else:
            tx, ty = x, y
            
        ih, iw = img.shape[:2]
        rx1, ry1 = max(0, int(tx)), max(0, int(ty))
        rx2, ry2 = min(iw, int(tx + roi_w)), min(ih, int(ty + roi_h))
        if rx2 <= rx1 or ry2 <= ry1:
            return
            
        roi = img[ry1:ry2, rx1:rx2].copy()
        # BGR -> RGB
        pil_img = Image.fromarray(cv2.cvtColor(roi, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(pil_img)
        
        # Coordinates inside the local PIL image
        lx = x - rx1
        ly = y - ry1
        
        # Swap BGR to RGB for PIL ImageDraw
        rgb_color = (color[2], color[1], color[0]) if len(color) == 3 else color
        
        # Draw with native anchor to let PIL handle ascenders/descenders perfectly (fixes half-cut numbers)
        try:
            draw.text((lx, ly), text, font=font, fill=rgb_color, anchor=anchor)
        except Exception:
            # Fallback for older Pillow versions
            ox = pad - (rx1 - tx)
            oy = pad - (ry1 - ty)
            draw.text((ox, oy), text, font=font, fill=rgb_color)
        
        # RGB -> BGR
        img[ry1:ry2, rx1:rx2] = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

    def _draw_corner_brackets(self, img, x1, y1, x2, y2, color, thickness=3, arm_ratio=0.14):
        """Draws camera autofocus/AR style corner brackets with rounded joint caps."""
        w = x2 - x1
        h = y2 - y1
        arm_w = int(w * arm_ratio)
        arm_h = int(h * arm_ratio)
        
        arm_w = max(8, min(30, arm_w))
        arm_h = max(8, min(30, arm_h))
        
        # Draw joints (rounded caps)
        r = thickness // 2
        for pt in [(x1, y1), (x2, y1), (x1, y2), (x2, y2)]:
            cv2.circle(img, pt, r, color, -1, cv2.LINE_AA)
            
        # Top-Left corner
        cv2.line(img, (x1, y1), (x1 + arm_w, y1), color, thickness, cv2.LINE_AA)
        cv2.line(img, (x1, y1), (x1, y1 + arm_h), color, thickness, cv2.LINE_AA)
        
        # Top-Right corner
        cv2.line(img, (x2, y1), (x2 - arm_w, y1), color, thickness, cv2.LINE_AA)
        cv2.line(img, (x2, y1), (x2, y1 + arm_h), color, thickness, cv2.LINE_AA)
        
        # Bottom-Left corner
        cv2.line(img, (x1, y2), (x1 + arm_w, y2), color, thickness, cv2.LINE_AA)
        cv2.line(img, (x1, y2), (x1, y2 - arm_h), color, thickness, cv2.LINE_AA)
        
        # Bottom-Right corner
        cv2.line(img, (x2, y2), (x2 - arm_w, y2), color, thickness, cv2.LINE_AA)
        cv2.line(img, (x2, y2), (x2, y2 - arm_h), color, thickness, cv2.LINE_AA)

    def _draw_subdued_brackets(self, img, x1, y1, x2, y2, color, thickness=1, arm_ratio=0.1):
        """Draws thin, low-opacity background brackets for non-scored vehicles."""
        w = x2 - x1
        h = y2 - y1
        arm_w = max(5, min(15, int(w * arm_ratio)))
        arm_h = max(5, min(15, int(h * arm_ratio)))
        
        # Simple thin lines, no rounded joint circles
        # Top-Left
        cv2.line(img, (x1, y1), (x1 + arm_w, y1), color, thickness, cv2.LINE_AA)
        cv2.line(img, (x1, y1), (x1, y1 + arm_h), color, thickness, cv2.LINE_AA)
        # Top-Right
        cv2.line(img, (x2, y1), (x2 - arm_w, y1), color, thickness, cv2.LINE_AA)
        cv2.line(img, (x2, y1), (x2, y1 + arm_h), color, thickness, cv2.LINE_AA)
        # Bottom-Left
        cv2.line(img, (x1, y2), (x1 + arm_w, y2), color, thickness, cv2.LINE_AA)
        cv2.line(img, (x1, y2), (x1, y2 - arm_h), color, thickness, cv2.LINE_AA)
        # Bottom-Right
        cv2.line(img, (x2, y2), (x2 - arm_w, y2), color, thickness, cv2.LINE_AA)
        cv2.line(img, (x2, y2), (x2, y2 - arm_h), color, thickness, cv2.LINE_AA)

    def _draw_pill(self, img, text, cx, cy, color, font, opacity=0.18, border_opacity=0.6, pad_x=8, pad_y=4):
        """Draws a premium rounded pill chip labels above and below target brackets."""
        tw, th = self._get_text_size(text, font)
        
        pw = tw + pad_x * 2
        ph = th + pad_y * 2
        
        px1 = cx - pw // 2
        py1 = cy
        
        # Translucent glass panel fill
        self._draw_glass_panel(img, px1, py1, pw, ph, bg_color=color, border_color=color, alpha=opacity, border_alpha=border_opacity, corner_radius=ph//2)
        
        # Centered text in pill
        self._draw_pil_text(img, text, cx, py1 + ph // 2, font, color, anchor="mm")

    def _draw_safety_score_gauge(self, img, score):
        """Draws top-left circular safety score gauge on circular frosted backing."""
        eased_score = self.score_ease.update(score)
        
        cx, cy = 60, 60
        r = 44
        
        x1, y1 = cx - r - 8, cy - r - 8
        x2, y2 = cx + r + 8, cy + r + 8
        
        # 1. Circle crop Gaussian Blur
        roi = img[y1:y2, x1:x2].copy()
        if (x2 - x1) > 4 and (y2 - y1) > 4:
            blurred_roi = cv2.GaussianBlur(roi, (15, 15), 0)
        else:
            blurred_roi = roi
            
        mask = np.zeros(roi.shape[:2], dtype=np.uint8)
        cv2.circle(mask, (cx - x1, cy - y1), r + 4, 255, -1)
        mask_inv = cv2.bitwise_not(mask)
        
        overlay = blurred_roi.copy()
        cv2.circle(overlay, (cx - x1, cy - y1), r + 4, (255, 255, 255), -1, cv2.LINE_AA)
        cv2.addWeighted(overlay, 0.15, blurred_roi, 0.85, 0, overlay)
        
        bg = cv2.bitwise_and(roi, roi, mask=mask_inv)
        fg = cv2.bitwise_and(overlay, overlay, mask=mask)
        img[y1:y2, x1:x2] = cv2.add(bg, fg)
        
        # White circular thin border
        cv2.circle(img, (cx, cy), r + 4, (255, 255, 255), 1, cv2.LINE_AA)
        
        # Track circle
        cv2.circle(img, (cx, cy), r - 4, (60, 60, 60), 4, cv2.LINE_AA)
        
        # Score color mapping
        if eased_score >= 80:
            color = self.ui_colors['safe']
        elif eased_score >= 50:
            color = self.ui_colors['warning']
        else:
            color = self.ui_colors['danger']
            
        sweep_angle = int((eased_score / 100.0) * 360)
        cv2.ellipse(img, (cx, cy), (r - 4, r - 4), -90, 0, sweep_angle, color, 4, cv2.LINE_AA)
        
        # Arc caps rounding
        if sweep_angle > 0:
            cv2.circle(img, (cx, cy - r + 4), 2, color, -1, cv2.LINE_AA)
            rad = np.deg2rad(-90 + sweep_angle)
            end_x = int(cx + (r - 4) * np.cos(rad))
            end_y = int(cy + (r - 4) * np.sin(rad))
            cv2.circle(img, (end_x, end_y), 2, color, -1, cv2.LINE_AA)
            
        # Draw numeric score & label
        score_str = str(int(round(eased_score)))
        self._draw_pil_text(img, score_str, cx, cy - 2, self.font_large, (255, 255, 255), anchor="mm")
        self._draw_pil_text(img, "safety score", cx, cy + r + 15, self.font_small, (160, 160, 160), anchor="mm")

    def _draw_hazard_banner(self, img, cy=45):
        """Draws top-center warning pill with icon and scale animations."""
        if self.active_hazard is None:
            return
            
        text, severity = self.active_hazard
        color = self.ui_colors['danger'] if severity == "danger" else self.ui_colors['warning']
        
        h, w = img.shape[:2]
        
        alpha = self.banner_alpha.current
        
        if alpha < 0.01:
            return
            
        tw, th = self._get_text_size(text, self.font_hazard)
        
        pad_x = 18
        pad_y = 8
        icon_size = 18
        spacing = 10
        
        # Dimensions are constant to prevent size/text misalignment under rapid transitions
        pw = tw + icon_size + spacing + pad_x * 2
        ph = max(th, icon_size) + pad_y * 2
        
        cx = w // 2
        
        px1 = cx - pw // 2
        py1 = cy - ph // 2
        
        # We perform all overlay operations on a separate buffer to allow smooth alpha-blend fading
        overlay = img.copy()
        
        # Frosted glass banner - dark background (20, 20, 20) with 85% opacity for maximum legibility (Bug 2)
        self._draw_glass_panel(overlay, px1, py1, pw, ph, bg_color=(20, 20, 20), border_color=color, alpha=0.85, border_alpha=0.9, corner_radius=ph//2)
        
        # Exclamation triangle icon (filled with warning color, black exclamation mark)
        tx_center = px1 + pad_x + icon_size // 2
        ty_center = cy
        
        pts = np.array([
            [tx_center, ty_center - icon_size // 2],
            [tx_center - icon_size // 2, ty_center + icon_size // 2],
            [tx_center + icon_size // 2, ty_center + icon_size // 2]
        ], np.int32)
        
        # Draw warning triangle in severity color
        cv2.fillPoly(overlay, [pts], color)
        # Exclamation mark in black for contrast inside the triangle
        cv2.line(overlay, (tx_center, ty_center - 3), (tx_center, ty_center + 1), (0, 0, 0), 2, cv2.LINE_AA)
        cv2.circle(overlay, (tx_center, ty_center + 4), 2, (0, 0, 0), -1, cv2.LINE_AA)
        
        # Hazard label text - severity colored text on dark background provides excellent contrast and color coding (Bug 2)
        tx_pos = px1 + pad_x + icon_size + spacing
        self._draw_pil_text(overlay, text, tx_pos, cy, self.font_hazard, color, anchor="lm")
        
        # Alpha blend the entire completed banner onto the main frame
        cv2.addWeighted(overlay, alpha, img, 1.0 - alpha, 0, img)

    def _draw_shortcuts_panel(self, img, path_active, hud_active, audio_muted):
        """Draws top-right shortcuts key guide in a clean state-dependent table."""
        h, w = img.shape[:2]
        
        panel_w = 145
        panel_h = 92
        panel_x = w - panel_w - 16
        panel_y = 16
        
        # Shortcuts panel
        self._draw_glass_panel(img, panel_x, panel_y, panel_w, panel_h, bg_color=(20, 20, 20), border_color=(100, 100, 100), alpha=0.5, border_alpha=0.4, corner_radius=8)
        
        rows = [
            ("P nav", "on" if path_active else "off", self.ui_colors['safe'] if path_active else self.ui_colors['danger']),
            ("A overlay", "on" if hud_active else "off", self.ui_colors['safe'] if hud_active else self.ui_colors['danger']),
            ("M audio", "muted" if audio_muted else "on", self.ui_colors['danger'] if audio_muted else self.ui_colors['safe']),
            ("Q / esc", "exit", (200, 200, 200))
        ]
        
        current_y = panel_y + 12
        for label, state_str, state_color in rows:
            self._draw_pil_text(img, label, panel_x + 12, current_y, self.font_small, (220, 220, 220), anchor="lm")
            self._draw_pil_text(img, state_str, panel_x + panel_w - 12, current_y, self.font_small, state_color, anchor="ra")
            current_y += 20

    def _draw_steering_offset_bar(self, img, lane_offset):
        """Draws horizontal steering track and eased indicator marker."""
        h, w = img.shape[:2]
        cx = w // 2
        cy = h - 30
        track_w = 180
        track_h = 6
        
        # Track backing
        self._draw_glass_panel(img, cx - track_w // 2, cy - track_h // 2, track_w, track_h, bg_color=(200, 200, 200), border_color=(150, 150, 150), alpha=0.3, border_alpha=0.3, corner_radius=track_h // 2)
        
        # Center reference tick
        cv2.line(img, (cx, cy - 4), (cx, cy + 4), (200, 200, 200), 1, cv2.LINE_AA)
        
        # Marker slide positioning
        eased_val = self.steering_offset_ease.update(lane_offset)
        eased_val = max(-1.0, min(1.0, eased_val))
        slide_x = int(cx + eased_val * (track_w / 2))
        
        # Select color based on offset limits
        abs_val = abs(lane_offset)
        if abs_val <= 0.25:
            color = self.ui_colors['safe']
        elif abs_val <= 0.38:
            color = self.ui_colors['warning']
        else:
            color = self.ui_colors['danger']
            
        cv2.circle(img, (slide_x, cy), 6, color, -1, cv2.LINE_AA)
        cv2.circle(img, (slide_x, cy), 7, (255, 255, 255), 1, cv2.LINE_AA) # marker white outline
        
        # Offset label
        self._draw_pil_text(img, "steering offset", cx, cy + 12, self.font_small, (160, 160, 160), anchor="mm")

    def _draw_nav_banner(self, frame, nav_alert):
        """Draws navigation alert text inside frosted banner."""
        if not nav_alert:
            return
            
        h, w = frame.shape[:2]
        
        # Measure nav alert text width using robust helper (prevents text overflow)
        tw, th = self._get_text_size(nav_alert, self.font_medium)
        
        panel_w = tw + 40
        panel_h = 35
        panel_x = (w - panel_w) // 2
        panel_y = 20
        
        self._draw_glass_panel(frame, panel_x, panel_y, panel_w, panel_h, bg_color=(20, 20, 20), border_color=(100, 100, 100), alpha=0.75, border_alpha=0.4, corner_radius=10)
        
        # Green text inside the banner
        self._draw_pil_text(frame, nav_alert, w // 2, panel_y + panel_h // 2, self.font_medium, (100, 255, 100), anchor="mm")

    def estimate_vanishing_point(self, lane_lines, w, h):
        """
        Estimates the vanishing point (intersection of left and right lane boundaries).
        """
        left_pts = []
        right_pts = []
        for line in lane_lines:
            x1, y1, x2, y2 = line
            if x2 == x1:
                continue
            slope = (y2 - y1) / (x2 - x1)
            # Left lane has negative slope, right lane has positive slope
            if slope < -0.3:
                left_pts.append((x1, y1))
                left_pts.append((x2, y2))
            elif slope > 0.3:
                right_pts.append((x1, y1))
                right_pts.append((x2, y2))
                
        if len(left_pts) >= 2 and len(right_pts) >= 2:
            left_line = cv2.fitLine(np.array(left_pts, np.int32), cv2.DIST_L2, 0, 0.01, 0.01)
            right_line = cv2.fitLine(np.array(right_pts, np.int32), cv2.DIST_L2, 0, 0.01, 0.01)
            
            vx_l, vy_l, x0_l, y0_l = left_line.flatten()
            vx_r, vy_r, x0_r, y0_r = right_line.flatten()
            
            if abs(vy_l) > 1e-3 and abs(vy_r) > 1e-3:
                mL = vx_l / vy_l
                cL = x0_l - mL * y0_l
                
                mR = vx_r / vy_r
                cR = x0_r - mR * y0_r
                
                if abs(mL - mR) > 1e-3:
                    y_van = (cR - cL) / (mL - mR)
                    x_van = mL * y_van + cL
                    
                    if 0.3 * h < y_van < 0.7 * h and 0.2 * w < x_van < 0.8 * w:
                        return int(x_van), int(y_van)
        return None

    def draw_navigation_path(self, frame, lane_center, detections, nav_type, lane_lines):
        """
        Calculates and draws discrete, perspective-correct 3D chevrons flat on the asphalt,
        using a true 3D flat ground plane perspective projection and dynamic vanishing point tracking.
        Features strict hood avoidance, time-based flow animation, and YOLO occlusion.
        """
        h, w = frame.shape[:2]
        
        target_bend = self.target_bends.get(nav_type, 0.0)
        self.current_bend = self.current_bend * 0.85 + target_bend * 0.15
        
        target_shift = self.target_shifts.get(nav_type, 0.0)
        self.current_shift = self.current_shift * 0.85 + target_shift * 0.15
        
        if 0.1 * w <= lane_center <= 0.9 * w:
            start_x = lane_center
        else:
            start_x = w // 2
            
        hood_buffer_padding = 85
        start_y = h - hood_buffer_padding
        
        if self.smooth_vp_x is None:
            self.smooth_vp_x = w // 2
            
        vp_est = self.estimate_vanishing_point(lane_lines, w, h)
        if vp_est is not None:
            self.smooth_vp_x = self.smooth_vp_x * 0.9 + vp_est[0] * 0.1
            
        end_x = int(self.smooth_vp_x)
        end_y = int(h * 0.58)
        
        Z_start = 8.0
        Z_max = 50.0
        
        K_y = (start_y - end_y) * Z_start
        K_x = K_y
        
        def project_ground_to_screen(X, Z):
            if Z <= 0.1:
                return w // 2, end_y
            py = int(end_y + K_y / Z)
            px_baseline = end_x + (start_x - end_x) * (Z_start / Z)
            px = int(px_baseline + (K_x * X) / Z)
            return px, py
            
        def get_projected_vertex(x_local, z_local):
            x_curve = x_local + self.current_bend * (z_local ** 2) * 1e-5 + self.current_shift * z_local * 1e-2
            return project_ground_to_screen(x_curve, z_local)
            
        num_chevrons = 7
        flow_speed = 1.5
        phase = (time.time() * flow_speed) % 1.0
        
        W = 3.2
        H = 0.6
        T_forward = 0.3
        T_side = 0.5
        
        Z_spacing = 6.5
        
        for j in range(num_chevrons):
            Z = Z_start + (j + phase) * Z_spacing
            if Z > Z_max:
                continue
                
            cx, cy = get_projected_vertex(0.0, Z)
            
            occluded = False
            for det in detections:
                x1, y1, x2, y2, _, _ = det
                if (x1 - 10 <= cx <= x2 + 10) and (y1 <= cy <= y2 + 10):
                    occluded = True
                    break
            if occluded:
                break
                
            base_alpha = 0.45
            if Z < Z_start + 4.0:
                alpha = base_alpha * ((Z - Z_start) / 4.0)
            elif Z > Z_max - 8.0:
                alpha = base_alpha * (1.0 - (Z - (Z_max - 8.0)) / 8.0)
            else:
                alpha = base_alpha
                
            alpha = max(0.0, min(base_alpha, alpha))
            if alpha <= 0.01:
                continue
                
            pt_tip = get_projected_vertex(0.0, Z + H)
            pt_ro = get_projected_vertex(W / 2, Z)
            pt_ri = get_projected_vertex(W / 2 - T_side, Z - T_forward)
            pt_val = get_projected_vertex(0.0, Z + H - T_forward)
            pt_li = get_projected_vertex(-W / 2 + T_side, Z - T_forward)
            pt_lo = get_projected_vertex(-W / 2, Z)
            
            pts = np.array([pt_tip, pt_ro, pt_ri, pt_val, pt_li, pt_lo], np.int32)
            
            overlay = frame.copy()
            cv2.fillPoly(overlay, [pts], self.ui_colors['nav_neon'])
            cv2.addWeighted(overlay, alpha, frame, 1.0 - alpha, 0, frame)

    def draw_idle_screen(self, frame, audio_muted=False):
        """Draws clean video frame when idle."""
        return frame

    def draw_key_guide(self, frame, audio_muted=False):
        """No-op to prevent legacy key guide text from overlaying."""
        return frame

    def display(self, frame, detections, distances, collision_risk, lane_lines, lane_center, score, suggestions, nav_type="straight", nav_alert="", path_active=True, hud_alerts_active=True, audio_muted=False):
        """
        FeedbackDisplay: Dedicated exclusively to YOLO bounding boxes & lane line detection overlays.
        All HUD text, speedometers, status cards, and navigation overlays are handled by ARProjector.
        """
        img = frame.copy()
        h, w = img.shape[:2]

        if hud_alerts_active:
            # Find index of lead vehicle (closest tracking preceding vehicle used in scoring)
            lead_idx = -1
            if distances:
                valid_dists = [d for d in distances if d is not None and d < float('inf')]
                if valid_dists:
                    min_d = min(valid_dists)
                    for idx, dist in enumerate(distances):
                        if dist == min_d:
                            lead_idx = idx
                            break

            # Vehicle Markers (Corner Brackets + Distance Chips)
            for idx, (det, dist) in enumerate(zip(detections, distances)):
                if dist > 35:
                    continue
                    
                x1, y1, x2, y2, cls_id, conf = det
                is_lead = (idx == lead_idx)
                
                if is_lead:
                    if dist < 10:
                        box_color = self.ui_colors['danger']
                    elif dist < 20:
                        box_color = self.ui_colors['warning']
                    else:
                        box_color = self.ui_colors['safe']
                        
                    # Corner brackets for lead vehicle
                    self._draw_corner_brackets(img, x1, y1, x2, y2, box_color, thickness=3, arm_ratio=0.14)

                    # Setup labels
                    class_name = "vehicle"
                    if cls_id == 2: class_name = "car"
                    elif cls_id == 3: class_name = "bike"
                    elif cls_id == 5: class_name = "bus"
                    elif cls_id == 7: class_name = "truck"
                    
                    cx = x1 + (x2 - x1) // 2
                    
                    # Upper chip: "<class> · <confidence>%"
                    class_label = f"{class_name} · {int(conf * 100)}%"
                    chip_h = 16
                    self._draw_pill(img, class_label, cx, y1 - chip_h - 4, box_color, self.font_small, opacity=0.18, border_opacity=0.6)
                    
                    # Lower chip: "<distance>m"
                    dist_label = f"{int(round(dist))}m"
                    self._draw_pill(img, dist_label, cx, y2 + 4, box_color, self.font_small, opacity=0.18, border_opacity=0.6)
                else:
                    # Subdued style: thin, neutral low-opacity gray brackets
                    subdued_color = (120, 120, 120)
                    self._draw_subdued_brackets(img, x1, y1, x2, y2, subdued_color, thickness=1)

        return img
