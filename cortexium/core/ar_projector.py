import cv2
import numpy as np
import time

class ARProjector:
    def __init__(self):
        self.start_time = time.time()
        
        # Futuristic Cyberpunk / Concept EV Palette (BGR)
        self.neon_cyan = (255, 230, 0)
        self.electric_mint = (150, 255, 80)
        self.laser_green = (80, 255, 120)
        self.deep_teal = (120, 180, 20)
        self.warning_amber = (0, 180, 255)
        self.critical_red = (40, 40, 255)
        self.white_glow = (255, 255, 255)
        self.glass_tint = (16, 18, 22)
        self.border_accent = (90, 110, 120)

    def _draw_tactical_card(self, frame, x, y, w, h, bg_tint=(18, 22, 28), border_col=(80, 100, 120), alpha=0.78):
        """Draws a semi-transparent dark glass panel with corner brackets."""
        overlay = frame.copy()
        cv2.rectangle(overlay, (x, y), (x + w, y + h), bg_tint, -1)
        cv2.addWeighted(overlay, alpha, frame, 1.0 - alpha, 0, frame)
        
        # Subtle perimeter border
        cv2.rectangle(frame, (x, y), (x + w, y + h), (40, 50, 60), 1, cv2.LINE_AA)
        
        # Sci-Fi corner brackets
        bracket_len = min(12, w // 6, h // 4)
        t = 2
        # Top-Left
        cv2.line(frame, (x, y), (x + bracket_len, y), border_col, t, cv2.LINE_AA)
        cv2.line(frame, (x, y), (x, y + bracket_len), border_col, t, cv2.LINE_AA)
        # Top-Right
        cv2.line(frame, (x + w, y), (x + w - bracket_len, y), border_col, t, cv2.LINE_AA)
        cv2.line(frame, (x + w, y), (x + w, y + bracket_len), border_col, t, cv2.LINE_AA)
        # Bottom-Left
        cv2.line(frame, (x, y + h), (x + bracket_len, y + h), border_col, t, cv2.LINE_AA)
        cv2.line(frame, (x, y + h), (x, y + h - bracket_len), border_col, t, cv2.LINE_AA)
        # Bottom-Right
        cv2.line(frame, (x + w, y + h), (x + w - bracket_len, y + h), border_col, t, cv2.LINE_AA)
        cv2.line(frame, (x + w, y + h), (x + w, y + h - bracket_len), border_col, t, cv2.LINE_AA)

    def render_ui(self, frame, telemetry):
        h, w = frame.shape[:2]
        is_portrait = h > w
        scale = w / 1280.0 if not is_portrait else w / 720.0
        elapsed = time.time() - self.start_time

        font_tech = cv2.FONT_HERSHEY_DUPLEX
        font_mono = cv2.FONT_HERSHEY_SIMPLEX

        # -------------------------------------------------------------
        # 1. TOP TACTICAL TELEMETRY RAIL (Problem & Coaching Module)
        # -------------------------------------------------------------
        bar_w = int(w * 0.94) if is_portrait else int(w * 0.62)
        bar_h = int(54 * scale)
        bar_x = int(w * 0.03) if is_portrait else (w - bar_w) // 2
        bar_y = int(h * 0.035)

        self._draw_tactical_card(frame, bar_x, bar_y, bar_w, bar_h, self.glass_tint, self.electric_mint)

        # Problem Status / Alert Color
        problem_txt = str(telemetry.get('problem', 'OPTIMAL')).upper()
        suggestion_txt = str(telemetry.get('suggestion', 'MAINTAIN PACE')).upper()

        if any(w in problem_txt for w in ["COLLISION", "CRITICAL"]):
            p_col = self.critical_red
        elif any(w in problem_txt for w in ["TAILGATING", "DEVIATION", "UNSTABLE", "ADVISORY"]):
            p_col = self.warning_amber
        else:
            p_col = self.electric_mint

        # Module A: Active Problem & Actionable Fix (Expanded width)
        cv2.circle(frame, (bar_x + int(18 * scale), bar_y + int(bar_h * 0.5)), int(4 * scale), p_col, -1, cv2.LINE_AA)
        cv2.putText(frame, f"STATUS // {problem_txt}", (bar_x + int(30 * scale), bar_y + int(18 * scale)),
                    font_mono, 0.32 * scale, p_col, 1, cv2.LINE_AA)
        cv2.putText(frame, suggestion_txt[:30], (bar_x + int(30 * scale), bar_y + int(40 * scale)),
                    font_tech, 0.44 * scale, self.white_glow, 1, cv2.LINE_AA)

        # Vertical Divider
        div1_x = bar_x + int(bar_w * 0.56)
        cv2.line(frame, (div1_x, bar_y + int(8 * scale)), (div1_x, bar_y + bar_h - int(8 * scale)), (45, 55, 65), 1, cv2.LINE_AA)

        # Module B: Dynamic Speed Limit Sign (Glowing Ring)
        limit_val = str(telemetry.get('speed_limit', 40))
        cur_speed = telemetry.get('speed', 0)
        speeding = cur_speed > int(limit_val)

        ring_x = div1_x + int(42 * scale)
        ring_y = bar_y + int(bar_h * 0.50)
        ring_r = int(18 * scale)
        ring_col = self.critical_red if speeding else self.neon_cyan

        cv2.circle(frame, (ring_x, ring_y), ring_r, (25, 30, 35), -1, cv2.LINE_AA)
        cv2.circle(frame, (ring_x, ring_y), ring_r, ring_col, max(2, int(2.5 * scale)), cv2.LINE_AA)
        txt_off = int(9 * scale) if len(limit_val) == 2 else int(13 * scale)
        cv2.putText(frame, limit_val, (ring_x - txt_off, ring_y + int(6 * scale)), font_tech, 0.52 * scale, self.white_glow, 1, cv2.LINE_AA)

        # Vertical Divider
        div2_x = div1_x + int(84 * scale)
        cv2.line(frame, (div2_x, bar_y + int(8 * scale)), (div2_x, bar_y + bar_h - int(8 * scale)), (45, 55, 65), 1, cv2.LINE_AA)

        # Module C: Safety Index / Score
        safety_status = str(telemetry.get('safety', 'LOW RISK')).upper()
        s_col = self.critical_red if "CRITICAL" in safety_status else (self.warning_amber if "MODERATE" in safety_status else self.electric_mint)
        
        cv2.circle(frame, (div2_x + int(18 * scale), bar_y + int(bar_h * 0.5)), int(4 * scale), s_col, -1, cv2.LINE_AA)
        cv2.putText(frame, "SAFETY", (div2_x + int(30 * scale), bar_y + int(18 * scale)), font_mono, 0.30 * scale, (140, 160, 170), 1, cv2.LINE_AA)
        cv2.putText(frame, safety_status, (div2_x + int(30 * scale), bar_y + int(40 * scale)), font_tech, 0.44 * scale, self.white_glow, 1, cv2.LINE_AA)

        # -------------------------------------------------------------
        # 2. HOLOGRAPHIC 3D GROUND TRACK & CHEVRON HEAD
        # -------------------------------------------------------------
        # 3D ROAD-PROJECTED ARROW (Active on diversions: flyovers, ramps, forks, and turns)
        # -------------------------------------------------------------
        maneuver = telemetry.get('maneuver', '').lower()
        dist_m = telemetry.get('distance', 999)
        is_diversion = any(k in maneuver for k in ["flyover", "ramp", "fork", "turn", "left", "right", "u_turn", "u-turn"])
        if is_diversion and dist_m <= 300:
            self._draw_hybrid_turn_arrow(frame, maneuver, dist_m, elapsed, scale, w, h)

        # -------------------------------------------------------------
        # 3. ENLARGED DIVERSION BANNER (WAYPOINT & TARGET STREET + ICON)
        # -------------------------------------------------------------
        street_name = telemetry.get('street_name', '')
        if maneuver:
            is_right = "right" in maneuver
            is_left = "left" in maneuver
            action_tag = "TURN RIGHT" if is_right else ("TURN LEFT" if is_left else "CONTINUE")
            
            # Substantially increased dimensions: taller box with breathing room
            inst_card_w = int(w * 0.92) if is_portrait else min(int(w * 0.70), int(520 * scale))
            inst_card_h = int(64 * scale)  # Increased from 38 to 64
            inst_x = (w - inst_card_w) // 2
            inst_y = bar_y + bar_h + int(12 * scale)

            # Deep glassmorphic card with bright cyan perimeter brackets
            self._draw_tactical_card(
                frame, inst_x, inst_y, inst_card_w, inst_card_h,
                bg_tint=(14, 18, 24),
                border_col=self.neon_cyan,
                alpha=0.82
            )

            # Left Action Metric: Large Distance Readout
            dist_str = f"{int(dist_m)}M"
            cv2.putText(frame, dist_str, (inst_x + int(14 * scale), inst_y + int(44 * scale)),
                        font_tech, 0.95 * scale, self.neon_cyan, max(2, int(2.2 * scale)), cv2.LINE_AA)
            cv2.putText(frame, "DISTANCE", (inst_x + int(18 * scale), inst_y + int(56 * scale)),
                        font_mono, 0.28 * scale, (140, 160, 170), 1, cv2.LINE_AA)

            # Vertical divider separating distance from street name
            div_dist_x = inst_x + int(96 * scale) if len(dist_str) <= 3 else inst_x + int(112 * scale)
            cv2.line(frame, (div_dist_x, inst_y + int(10 * scale)), (div_dist_x, inst_y + inst_card_h - int(10 * scale)),
                     (50, 65, 80), 1, cv2.LINE_AA)

            # Middle Panel: Two-tier Action and Target Street Name
            # Tier 1: Maneuver directive
            action_header = f"// {action_tag} ONTO"
            cv2.putText(frame, action_header, (div_dist_x + int(16 * scale), inst_y + int(24 * scale)),
                        font_mono, 0.36 * scale, self.electric_mint, 1, cv2.LINE_AA)

            # Tier 2: Large Target Street Name
            display_street = street_name[:24].upper()
            cv2.putText(frame, display_street, (div_dist_x + int(16 * scale), inst_y + int(50 * scale)),
                        font_tech, 0.65 * scale, self.white_glow, max(1, int(1.8 * scale)), cv2.LINE_AA)

            # Right Panel: Directional Vector Icon (Chevron)
            icon_cx = inst_x + inst_card_w - int(32 * scale)
            icon_cy = inst_y + int(inst_card_h / 2)
            s = int(10 * scale)

            if is_right:
                pts = np.array([[icon_cx - s, icon_cy - s], [icon_cx + s, icon_cy], [icon_cx - s, icon_cy + s]], np.int32)
                cv2.polylines(frame, [pts], isClosed=False, color=self.neon_cyan, thickness=max(2, int(3 * scale)), lineType=cv2.LINE_AA)
            elif is_left:
                pts = np.array([[icon_cx + s, icon_cy - s], [icon_cx - s, icon_cy], [icon_cx + s, icon_cy + s]], np.int32)
                cv2.polylines(frame, [pts], isClosed=False, color=self.neon_cyan, thickness=max(2, int(3 * scale)), lineType=cv2.LINE_AA)
            else:
                pts = np.array([[icon_cx - s, icon_cy + s], [icon_cx, icon_cy - s], [icon_cx + s, icon_cy + s]], np.int32)
                cv2.polylines(frame, [pts], isClosed=False, color=self.electric_mint, thickness=max(2, int(3 * scale)), lineType=cv2.LINE_AA)

        # -------------------------------------------------------------
        # 4. DIGITAL COCKPIT VELOCITY DISPLAY (Bottom Left)
        # -------------------------------------------------------------
        sp_x = int(w * 0.05)
        sp_y = int(h * 0.90) if not is_portrait else int(h * 0.86)
        spd_val = f"{telemetry.get('speed', 0):02d}"

        bracket_w = int(140 * scale)
        bracket_h = int(60 * scale)
        self._draw_tactical_card(frame, sp_x - int(8 * scale), sp_y - bracket_h + int(12 * scale), bracket_w, bracket_h, (12, 14, 18), (50, 60, 70), alpha=0.60)

        cv2.putText(frame, spd_val, (sp_x, sp_y), font_tech, 1.4 * scale, self.white_glow, max(2, int(2.5 * scale)), cv2.LINE_AA)
        cv2.putText(frame, "KM/H", (sp_x + int(len(spd_val) * 32 * scale) + int(6 * scale), sp_y - int(4 * scale)), font_mono, 0.42 * scale, self.neon_cyan, 1, cv2.LINE_AA)

        return frame

    def _draw_hybrid_turn_arrow(self, frame, maneuver, dist_m, elapsed, scale, w, h):
        is_turn = ("turn" in maneuver.lower() or "left" in maneuver.lower() or "right" in maneuver.lower() or "u_turn" in maneuver.lower() or "u-turn" in maneuver.lower())
        is_left = "left" in maneuver.lower()
        curve_dir = (-1.0 if is_left else 1.0) if is_turn else 0.0
        is_portrait = h > w

        # --- Visual progression mapped across countdown (visible up to 300m) ---
        visual_dist = min(float(dist_m), 250.0)
        prog = float(np.clip((250.0 - visual_dist) / 250.0, 0.0, 1.0))

        # Ground metric depth bounds (from 28m ahead down to 3.0m bumper)
        z_start = (1.0 - prog) * 26.0 + prog * 3.0
        z_end = (1.0 - prog) * 34.0 + prog * 13.0

        num_pts = 24
        z_vals = np.linspace(z_start, z_end, num_pts)

        # Starts with small scale stem width, expanding as it approaches
        stem_half_w = 0.22 + 0.38 * prog
        
        # Position distinctly toward the turn side or center lane for straight/flyover
        if is_turn:
            lane_origin_bias = curve_dir * (1.60 + 0.40 * prog)
            max_lateral_sweep = 2.5 + (4.5 * (prog ** 1.3))
        else:
            lane_origin_bias = 0.0
            max_lateral_sweep = 0.0

        stem_3d_left = []
        stem_3d_right = []
        y_ground = 1.25

        for z in z_vals:
            t = (z - z_start) / max(0.01, (z_end - z_start))
            curve_exp = (1.0 - prog) * 1.8 + prog * 1.1
            lateral_sweep = lane_origin_bias + curve_dir * (max_lateral_sweep * (t ** curve_exp))
            w_metric = stem_half_w * (1.0 - 0.15 * t)

            stem_3d_left.append([lateral_sweep - w_metric, y_ground, z])
            stem_3d_right.append([lateral_sweep + w_metric, y_ground, z])

        t_left = stem_3d_left[-1]
        t_right = stem_3d_right[-1]
        stem_end_center = np.array([
            (t_left[0] + t_right[0]) / 2.0,
            y_ground,
            (t_left[2] + t_right[2]) / 2.0
        ], dtype=np.float32)

        prev_left = stem_3d_left[-3]
        prev_right = stem_3d_right[-3]
        stem_prev_center = np.array([
            (prev_left[0] + prev_right[0]) / 2.0,
            y_ground,
            (prev_left[2] + prev_right[2]) / 2.0
        ], dtype=np.float32)

        dir_vec = stem_end_center - stem_prev_center
        dir_norm = np.linalg.norm(dir_vec) + 1e-6
        dir_unit = dir_vec / dir_norm

        if is_turn:
            # Rotate heading dynamically toward perpendicular as distance drops to 0m
            lateral_weight = 0.4 + 0.6 * prog
            dir_unit[0] = dir_unit[0] * (1.0 - lateral_weight) + (curve_dir * 1.0) * lateral_weight
            dir_unit[2] = dir_unit[2] * (1.0 - lateral_weight) + (0.15) * lateral_weight
            dir_unit = dir_unit / (np.linalg.norm(dir_unit) + 1e-6)

        perp_unit = np.array([-dir_unit[2], 0.0, dir_unit[0]], dtype=np.float32)

        head_length = 2.4 + 1.2 * prog
        head_wing_span = (stem_half_w * 2.4) + 0.5 * prog

        arrow_tip_3d = stem_end_center + (dir_unit * head_length)
        arrow_tip_3d[1] = y_ground

        wing_left_3d = stem_end_center - (perp_unit * head_wing_span)
        wing_right_3d = stem_end_center + (perp_unit * head_wing_span)

        contour_3d = (
            stem_3d_left +
            [wing_left_3d.tolist(), arrow_tip_3d.tolist(), wing_right_3d.tolist()] +
            stem_3d_right[::-1]
        )
        obj_pts = np.array(contour_3d, dtype=np.float32)

        # Camera Intrinsics
        focal_length = w * 1.05 if is_portrait else w * 0.95
        cx = w / 2.0
        cy = h * 0.52 if is_portrait else h * 0.56
        camera_matrix = np.array([[focal_length, 0, cx], [0, focal_length, cy], [0, 0, 1]], dtype=np.float32)
        dist_coeffs = np.zeros((4, 1), dtype=np.float32)

        pitch_angle = np.radians(7.0 if is_portrait else 6.0)
        rvec = np.array([pitch_angle, 0.0, 0.0], dtype=np.float32)
        tvec = np.array([0.0, 0.0, 0.0], dtype=np.float32)

        img_pts, _ = cv2.projectPoints(obj_pts, rvec, tvec, camera_matrix, dist_coeffs)
        poly_2d = img_pts.reshape(-1, 2).astype(np.int32)

        # Render Solid Ground Arrow
        overlay = frame.copy()
        solid_mint = (120, 235, 110)
        bright_rim = (210, 255, 200)
        cv2.fillPoly(overlay, [poly_2d], solid_mint)
        cv2.addWeighted(overlay, 0.78, frame, 0.22, 0, frame)
        cv2.polylines(frame, [poly_2d], isClosed=True, color=bright_rim,
                      thickness=max(1, int(2.5 * scale)), lineType=cv2.LINE_AA)