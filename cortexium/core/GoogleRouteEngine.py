import os
import requests
try:
    import polyline
except ImportError:
    class _PolylineFallback:
        @staticmethod
        def decode(encoded):
            return []
    polyline = _PolylineFallback()

import math
import re
import numpy as np
import pandas as pd
from dotenv import load_dotenv

# Load env variables
load_dotenv()

class GoogleRouteEngine:
    def __init__(self, telemetry_csv="data/telemetry.csv"):
        self.api_key = os.getenv("GOOGLE_MAPS_API_KEY")
        self.telemetry_csv = telemetry_csv
        self.polyline_coords = []
        self.steps = []
        
        if not self.api_key:
            print("⚠️ Warning: GOOGLE_MAPS_API_KEY not found in environment.")
            
        self.load_route_from_telemetry()
        
    def load_route_from_telemetry(self):
        """
        Read coordinates from CSV, query Google Maps Directions API,
        and prepare route polyline & maneuver steps.
        """
        if not os.path.exists(self.telemetry_csv):
            print(f"⚠️ Warning: Telemetry file {self.telemetry_csv} not found. Cannot fetch Google route.")
            return

        try:
            df = pd.read_csv(self.telemetry_csv)
            # Filter rows with valid coordinates
            valid_df = df.dropna(subset=['latitude', 'longitude'])
            if len(valid_df) < 2:
                print("⚠️ Telemetry data needs at least 2 coordinate points.")
                return
                
            start_coord = (valid_df.iloc[0]['latitude'], valid_df.iloc[0]['longitude'])
            self.destination_coord = (valid_df.iloc[-1]['latitude'], valid_df.iloc[-1]['longitude'])
            
            # Sample intermediate waypoints from the telemetry trajectory to anchor Google Maps to the actual driven route
            num_rows = len(valid_df)
            waypoints = []
            if num_rows > 30:
                # Sample 5 evenly spaced intermediate track points
                sample_indices = np.linspace(num_rows // 6, num_rows - (num_rows // 6), 5, dtype=int)
                for s_idx in sample_indices:
                    pt_lat = valid_df.iloc[s_idx]['latitude']
                    pt_lon = valid_df.iloc[s_idx]['longitude']
                    waypoints.append(f"{pt_lat},{pt_lon}")

            self.fetch_directions(start_coord, self.destination_coord, waypoints=waypoints)
        except Exception as e:
            print(f"❌ Error loading route from telemetry: {e}")

    def reroute_from_current_location(self, current_lat, current_lon):
        """
        Dynamically calls Google Maps Directions API to compute a new route polyline
        from the driver's current position to the final destination if they go off-route.
        """
        if not hasattr(self, 'destination_coord') or not self.destination_coord:
            return False
            
        print(f"🔄 [DYNAMIC REROUTE] Calculating new path to destination from ({current_lat:.4f}, {current_lon:.4f})...")
        self.fetch_directions((current_lat, current_lon), self.destination_coord)
        return len(self.steps) > 0

    def fetch_directions(self, start_coord, end_coord, waypoints=None):
        """
        Queries the official Google Directions API.
        """
        if not self.api_key:
            # Fallback mock polyline
            print("⚠️ API Key missing. Generating mock linear route polyline.")
            self.polyline_coords = self.generate_mock_polyline(start_coord, end_coord)
            self.steps = [{
                "instruction": "Drive straight on mock path",
                "distance": 500,
                "start_location": start_coord,
                "end_location": end_coord,
                "maneuver": "straight"
            }]
            return

        url = f"https://maps.googleapis.com/maps/api/directions/json"
        params = {
            "origin": f"{start_coord[0]},{start_coord[1]}",
            "destination": f"{end_coord[0]},{end_coord[1]}",
            "mode": "driving",
            "key": self.api_key
        }
        if waypoints:
            params["waypoints"] = "|".join(waypoints)
        
        try:
            response = requests.get(url, params=params)
            data = response.json()
            
            if data.get("status") == "OK":
                route = data["routes"][0]
                # Decode overview_polyline
                encoded_poly = route["overview_polyline"]["points"]
                self.polyline_coords = polyline.decode(encoded_poly)
                
                # Parse all steps across all legs
                self.steps = []
                for leg in route.get("legs", []):
                    for step in leg.get("steps", []):
                        self.steps.append({
                            "instruction": step.get("html_instructions", ""),
                            "distance": step.get("distance", {}).get("value", 0),
                            "start_location": (step["start_location"]["lat"], step["start_location"]["lng"]),
                            "end_location": (step["end_location"]["lat"], step["end_location"]["lng"]),
                            "maneuver": step.get("maneuver", "straight")
                        })
                print(f"✅ Route successfully fetched. Loaded {len(self.polyline_coords)} polyline nodes across {len(route.get('legs', []))} legs.")
            else:
                print(f"❌ Google Directions API Error: {data.get('status')}")
                self.polyline_coords = self.generate_mock_polyline(start_coord, end_coord)
        except Exception as e:
            print(f"❌ Error fetching directions from Google API: {e}")
            self.polyline_coords = self.generate_mock_polyline(start_coord, end_coord)

    def generate_mock_polyline(self, start, end, steps=50):
        """Helper fallback polyline interpolation"""
        lats = np.linspace(start[0], end[0], steps)
        lons = np.linspace(start[1], end[1], steps)
        return list(zip(lats, lons))

    def get_route_polyline(self):
        """Returns List of (lat, lon) representing the path"""
        return self.polyline_coords

    def get_maneuver_steps(self):
        """Returns List of step dictionaries"""
        return self.steps

    def find_upcoming_maneuver(self, curr_lat, curr_lon, lookahead_meters=120):
        """
        Calculates distance and bearing difference to upcoming step within lookahead_meters limit.
        """
        if not self.steps:
            return "straight", 0.0, 0.0

        closest_step = None
        min_distance = float('inf')

        for step in self.steps:
            step_lat, step_lon = step["start_location"]
            dist = self.haversine(curr_lat, curr_lon, step_lat, step_lon)
            if dist < min_distance:
                min_distance = dist
                closest_step = step

        if closest_step and min_distance <= lookahead_meters:
            # Strip HTML tags from instruction if present
            clean_instruction = re.sub('<[^<]+?>', '', closest_step["instruction"])
            
            # Simple bearing difference simulation based on maneuver string
            maneuver = closest_step.get("maneuver", "").lower()
            bearing_diff = 0.0
            if "left" in maneuver:
                bearing_diff = -90.0
            elif "right" in maneuver:
                bearing_diff = 90.0
                
            return clean_instruction, min_distance, bearing_diff

        return "Route Active. Follow navigation line.", 0.0, 0.0

    @staticmethod
    def haversine(lat1, lon1, lat2, lon2):
        """
        Calculate the great circle distance between two points on the earth in meters
        """
        R = 6371000.0  # radius of earth in meters
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        
        a = math.sin(dphi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0)**2
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        return R * c
