import os
import math
import re
import html
import time
import threading
from config import DATA_DIR
from core.GoogleRouteEngine import GoogleRouteEngine

class NavDirector:
    def __init__(self, telemetry_file=None):
        """
        Initialize the navigation director utilizing the Google Maps routing engine.
        Tracks active route steps, current step index, heading completion hysteresis,
        aggressive lookahead pruning, and background thread-safe rerouting.
        """
        if telemetry_file is None:
            telemetry_file = os.path.join(DATA_DIR, 'telemetry.csv')
        self.telemetry_file = telemetry_file
        
        print("🗺️ Initializing Google Route Engine from telemetry coordinates...")
        self.route_engine = GoogleRouteEngine(telemetry_csv=self.telemetry_file)
        
        self.route_lock = threading.Lock()
        self.current_step_idx = 0
        self.prev_dist_to_turn = 9999.0
        self.prev_heading = None
        self._is_rerouting = False
        self._last_reroute_time = 0.0
        
        self._init_route_steps()

    def _init_route_steps(self):
        """Pre-processes Google route engine steps into structured navigation steps with target headings."""
        raw_steps = self.route_engine.get_maneuver_steps()
        steps = []
        
        if not raw_steps:
            with self.route_lock:
                self.route_steps = []
            return

        for idx, step in enumerate(raw_steps):
            html_raw = step.get("instruction", "")
            
            # 1. Extract bold tags <b>...</b>
            b_tags = re.findall(r'<b>(.*?)</b>', html_raw, flags=re.IGNORECASE | re.DOTALL)
            b_tags = [re.sub(r'<[^<]+?>', '', b).strip() for b in b_tags if b.strip()]
            
            # 2. Clean subsidiary notes inside <div>...</div>
            clean_html = re.sub(r'<div[^>]*>.*?</div>', '', html_raw, flags=re.IGNORECASE | re.DOTALL)
            clean_inst = re.sub(r'<[^<]+?>', '', clean_html)
            clean_inst = html.unescape(clean_inst).strip()
            clean_inst = re.sub(r'\s+', ' ', clean_inst)

            # 3. Resolve target street name
            street_name = ""
            if len(b_tags) >= 2 and any(k in b_tags[0].lower() for k in ["turn", "left", "right", "head", "continue"]):
                street_name = b_tags[1]
            elif len(b_tags) == 1 and not any(k in b_tags[0].lower() for k in ["left", "right", "head", "continue"]):
                street_name = b_tags[0]
            else:
                match = re.search(r'(?:onto|on)\s+([^,\.\<]+)', clean_inst, re.IGNORECASE)
                if match:
                    street_name = match.group(1).strip()

            for noise in ["Destination", "Pass by", "will be on", "toward", "Restricted"]:
                if noise.lower() in street_name.lower():
                    street_name = re.split(noise, street_name, flags=re.IGNORECASE)[0].strip()

            if not street_name:
                street_name = "MAIN CORRIDOR"

            maneuver = step.get("maneuver", "straight").lower()
            nav_type = "straight"
            if "flyover" in clean_inst.lower() or "flyover" in street_name.lower():
                nav_type = "flyover"
            elif "ramp" in maneuver or "ramp" in clean_inst.lower():
                nav_type = "ramp"
            elif "fork" in maneuver or "fork" in clean_inst.lower():
                nav_type = "fork"
            elif "left" in maneuver or "left" in clean_inst.lower():
                nav_type = "turn-left"
            elif "right" in maneuver or "right" in clean_inst.lower():
                nav_type = "turn-right"
            elif "u-turn" in maneuver or "uturn" in maneuver or "u-turn" in clean_inst.lower():
                nav_type = "u_turn"

            start_lat, start_lon = step["start_location"]
            end_lat, end_lon = step["end_location"]
            
            # Compute target exit heading
            target_heading = self._calculate_bearing(start_lat, start_lon, end_lat, end_lon)

            steps.append({
                'lat': end_lat,
                'lon': end_lon,
                'start_lat': start_lat,
                'start_lon': start_lon,
                'distance_m': step.get('distance', 0),
                'type': nav_type,
                'instruction': clean_inst,
                'clean_instruction': clean_inst,
                'street_name': street_name.upper(),
                'target_heading': target_heading
            })

        # --- ROUTE CONSOLIDATION & CLEANUP ---
        consolidated = []
        for s in steps:
            # Filter zero/micro steps generated from intermediate waypoint stopping points
            if s['distance_m'] < 20 and "turn" not in s['type'] and "flyover" not in s['type']:
                continue
            if consolidated and consolidated[-1]['street_name'] == s['street_name'] and consolidated[-1]['type'] == s['type'] and s['type'] == 'straight':
                consolidated[-1]['distance_m'] += s['distance_m']
                consolidated[-1]['lat'] = s['lat']
                consolidated[-1]['lon'] = s['lon']
            else:
                consolidated.append(s)

        with self.route_lock:
            self.route_steps = consolidated

    def _calculate_bearing(self, lat1, lon1, lat2, lon2):
        """Calculates initial bearing from point 1 to point 2 in degrees (0 - 360)."""
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dlambda = math.radians(lon2 - lon1)
        y = math.sin(dlambda) * math.cos(phi2)
        x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlambda)
        bearing = math.degrees(math.atan2(y, x))
        return (bearing + 360) % 360

    def _haversine(self, lat1, lon1, lat2, lon2):
        """Great-circle distance between two points in meters."""
        R = 6371000.0
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0)**2
        return R * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    def _point_to_line_segment_dist(self, p_lat, p_lon, a_lat, a_lon, b_lat, b_lon):
        """Calculates minimum distance from a point to a line segment in meters."""
        # Flat earth approximation for short segment distances
        mid_lat = math.radians((a_lat + b_lat) / 2.0)
        deg_to_m_lat = 111132.954
        deg_to_m_lon = 111412.84 * math.cos(mid_lat)

        px = (p_lon - a_lon) * deg_to_m_lon
        py = (p_lat - a_lat) * deg_to_m_lat
        bx = (b_lon - a_lon) * deg_to_m_lon
        by = (b_lat - a_lat) * deg_to_m_lat

        seg_len_sq = bx * bx + by * by
        if seg_len_sq < 1e-6:
            return math.sqrt(px * px + py * py)

        t = max(0.0, min(1.0, (px * bx + py * by) / seg_len_sq))
        proj_x = t * bx
        proj_y = t * by
        dx = px - proj_x
        dy = py - proj_y
        return math.sqrt(dx * dx + dy * dy)

    def _calculate_cross_track_distance(self, curr_lat, curr_lon):
        """Computes minimum cross-track distance from current GPS position to active route polyline."""
        polyline_coords = self.route_engine.get_route_polyline()
        if not polyline_coords or len(polyline_coords) < 2:
            return 0.0

        min_dist = float('inf')
        # Evaluate segments surrounding current step
        for i in range(len(polyline_coords) - 1):
            p1 = polyline_coords[i]
            p2 = polyline_coords[i + 1]
            dist = self._point_to_line_segment_dist(curr_lat, curr_lon, p1[0], p1[1], p2[0], p2[1])
            if dist < min_dist:
                min_dist = dist
        return min_dist

    def _trigger_background_reroute(self, curr_lat, curr_lon):
        """Spawns non-blocking background daemon thread to recalculate route without stalling OpenCV."""
        if self._is_rerouting:
            return
        now = time.time()
        if now - self._last_reroute_time < 20.0:
            return

        self._is_rerouting = True
        self._last_reroute_time = now

        def _worker():
            try:
                print(f"🛰️ [BACKGROUND REROUTE] Recalculating path from ({curr_lat:.4f}, {curr_lon:.4f})...")
                success = self.route_engine.reroute_from_current_location(curr_lat, curr_lon)
                if success:
                    raw_steps = self.route_engine.get_maneuver_steps()
                    if raw_steps:
                        self._init_route_steps()
                        with self.route_lock:
                            self.current_step_idx = 0
                        print("✅ [BACKGROUND REROUTE] Route hot-swapped safely!")
            except Exception as e:
                print(f"⚠️ [BACKGROUND REROUTE] Failed: {e}")
            finally:
                self._is_rerouting = False

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()

    def get_current_nav_state(self, curr_lat, curr_lon, curr_heading=None, curr_speed=0.0, is_moving=True, frame_idx=0):
        with self.route_lock:
            if not hasattr(self, 'route_steps') or not self.route_steps:
                return "straight", "", "", 999
            steps_copy = list(self.route_steps)
            curr_idx = self.current_step_idx

        if curr_idx >= len(steps_copy):
            curr_idx = len(steps_copy) - 1

        current_step = steps_copy[curr_idx]

        if curr_lat is not None and curr_lon is not None:
            dist_to_step = self._haversine(curr_lat, curr_lon, current_step['lat'], current_step['lon'])
        else:
            dist_to_step = current_step.get('distance_m', 999)

        if is_moving and curr_lat is not None and curr_lon is not None:
            # -----------------------------------------------------------------
            # 1. AGGRESSIVE LOOKAHEAD PRUNING (The Desync Fix)
            # -----------------------------------------------------------------
            # Check the next 3 steps. If vehicle is closer to N+2/N+3 than N, instantly jump/skip
            for lookahead_offset in [3, 2, 1]:
                target_idx = curr_idx + lookahead_offset
                if target_idx < len(steps_copy):
                    target_step = steps_copy[target_idx]
                    dist_to_future = self._haversine(curr_lat, curr_lon, target_step['lat'], target_step['lon'])
                    # If vehicle is significantly closer to downstream step (or passed upstream)
                    if dist_to_future < dist_to_step and dist_to_future < 160.0:
                        curr_idx = target_idx
                        current_step = steps_copy[curr_idx]
                        dist_to_step = dist_to_future
                        with self.route_lock:
                            self.current_step_idx = curr_idx
                        break

            # -----------------------------------------------------------------
            # 2. HEADING-BASED TURN VERIFICATION
            # -----------------------------------------------------------------
            heading_completed = False
            if curr_heading is not None:
                # Absolute heading check against target road heading
                if 'target_heading' in current_step:
                    diff = abs((curr_heading - current_step['target_heading'] + 180) % 360 - 180)
                    if diff < 45:
                        heading_completed = True

                # Relative delta shift check (~90 deg turn verification)
                if self.prev_heading is not None:
                    heading_delta = (curr_heading - self.prev_heading + 180) % 360 - 180
                    # If left turn expected and turned ~60-120 deg counter-clockwise (-ve delta)
                    if "left" in current_step.get('type', '') and -120 <= heading_delta <= -45:
                        heading_completed = True
                    # If right turn expected and turned ~60-120 deg clockwise (+ve delta)
                    elif "right" in current_step.get('type', '') and 45 <= heading_delta <= 120:
                        heading_completed = True

            # Advance when close to waypoint OR when aligned into new road OR when moving away after turn
            can_advance = (
                (dist_to_step <= 25.0) or
                (curr_idx == 0 and dist_to_step <= 30.0) or
                (dist_to_step <= 90.0 and heading_completed) or
                (dist_to_step <= 120.0 and dist_to_step > (self.prev_dist_to_turn + 0.8))
            )

            if can_advance and curr_idx < len(steps_copy) - 1:
                curr_idx += 1
                with self.route_lock:
                    self.current_step_idx = curr_idx
                current_step = steps_copy[curr_idx]
                dist_to_step = self._haversine(curr_lat, curr_lon, current_step['lat'], current_step['lon'])

            # -----------------------------------------------------------------
            # 3. BACKGROUND FAIL-SAFE OFF-ROUTE RECALCULATION
            # -----------------------------------------------------------------
            # Check cross-track distance to polyline
            if curr_speed > 4.0:
                cross_track_m = self._calculate_cross_track_distance(curr_lat, curr_lon)
                if cross_track_m > 35.0:
                    self._trigger_background_reroute(curr_lat, curr_lon)

        if curr_heading is not None:
            self.prev_heading = curr_heading

        nav_type = current_step.get('type', 'straight')
        maneuver_text = current_step.get('instruction', 'Continue straight')
        clean_alert = current_step.get('clean_instruction', maneuver_text)

        # Lookahead only if within 40m of a very short step
        if nav_type == "straight" and dist_to_step <= 40.0 and current_step.get('distance_m', 0) <= 50.0 and curr_idx + 1 < len(steps_copy):
            next_step = steps_copy[curr_idx + 1]
            next_type = next_step.get('type', 'straight')
            if next_type in ["flyover", "ramp", "fork", "turn-left", "turn-right", "u_turn"]:
                nav_type = next_type
                maneuver_text = next_step.get('instruction', maneuver_text)
                clean_alert = next_step.get('clean_instruction', clean_alert)

        self.prev_dist_to_turn = dist_to_step
        return nav_type, clean_alert, maneuver_text, dist_to_step

    def print_route_summary(self):
        """Prints a clean, formatted debug table of all steps in the active Google Maps route."""
        with self.route_lock:
            if not hasattr(self, 'route_steps') or not self.route_steps:
                print("⚠️ No route steps available to summarize.")
                return
            steps = list(self.route_steps)

        print("\n" + "=" * 90)
        print("🗺️  GOOGLE MAPS API ROUTE PIPELINE")
        print("=" * 90)
        print(f"{'STEP':<6} | {'DISTANCE':<10} | {'MANEUVER':<12} | {'INSTRUCTION'}")
        print("-" * 90)
        
        for idx, step in enumerate(steps):
            dist_str = f"{int(step.get('distance_m', 0))}m"
            maneuver_str = step.get('type', 'straight')
            instruction_str = step.get('clean_instruction', step.get('instruction', ''))
            print(f"{idx:<6} | {dist_str:<10} | {maneuver_str:<12} | {instruction_str}")
            
        print("=" * 90 + "\n")
