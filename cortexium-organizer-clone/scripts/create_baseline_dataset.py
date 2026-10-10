import ijson
import csv
import os

INPUT = r"data/visual_genome/relationships.json"
OUTPUT = r"data/baseline_relationships.csv"

# Cortexium-relevant objects
OBJECTS = {
    "bottle", "cup", "mug", "book", "laptop", "keyboard", "mouse",
    "phone", "cell phone", "remote", "bag", "backpack", "handbag",
    "pencil", "pen", "scissors", "plate", "bowl", "glass",
    "computer", "monitor", "tablet", "box", "toy", "camera"
}

# Cortexium-relevant placement surfaces
SURFACES = {
    "table", "dining table", "desk", "counter", "countertop",
    "shelf", "bench", "chair", "couch", "sofa", "bed",
    "floor", "ground", "cabinet", "drawer", "rack"
}

# Predicates indicating spatial/placement relationships
PLACEMENT_PREDICATES = {
    "on", "ON", "in", "inside", "under", "below",
    "above", "over", "beside", "next to"
}

os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)

rows = []
seen = set()

print("Reading Visual Genome...")
print("This may take several minutes because the dataset is ~710 MB.")

with open(INPUT, "rb") as f:
    records = ijson.items(f, "item")

    for record in records:
        image_id = record.get("image_id")

        for rel in record.get("relationships", []):
            subject = rel.get("subject", {})
            obj = rel.get("object", {})
            predicate = str(rel.get("predicate", "")).strip()

            subject_name = str(subject.get("name", "")).lower().strip()
            object_name = str(obj.get("name", "")).lower().strip()

            # We want:
            # object -> surface
            if subject_name not in OBJECTS:
                continue

            if object_name not in SURFACES:
                continue

            if predicate not in PLACEMENT_PREDICATES:
                continue

            key = (
                subject_name,
                object_name,
                predicate
            )

            if key in seen:
                continue

            seen.add(key)

            # Bounding-box features
            sx = subject.get("x", 0)
            sy = subject.get("y", 0)
            sw = subject.get("w", 0)
            sh = subject.get("h", 0)

            ox = obj.get("x", 0)
            oy = obj.get("y", 0)
            ow = obj.get("w", 0)
            oh = obj.get("h", 0)

            # Geometric relationship between object and surface
            subject_center_x = sx + sw / 2
            subject_center_y = sy + sh / 2

            object_center_x = ox + ow / 2
            object_center_y = oy + oh / 2

            rows.append({
                "image_id": image_id,
                "object": subject_name,
                "surface": object_name,
                "predicate": predicate,
                "object_x": sx,
                "object_y": sy,
                "object_w": sw,
                "object_h": sh,
                "surface_x": ox,
                "surface_y": oy,
                "surface_w": ow,
                "surface_h": oh,
                "center_distance_x": abs(subject_center_x - object_center_x),
                "center_distance_y": abs(subject_center_y - object_center_y)
            })

print(f"\nExtracted {len(rows)} baseline relationships.")

with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=rows[0].keys() if rows else [
        "image_id", "object", "surface", "predicate",
        "object_x", "object_y", "object_w", "object_h",
        "surface_x", "surface_y", "surface_w", "surface_h",
        "center_distance_x", "center_distance_y"
    ])

    writer.writeheader()
    writer.writerows(rows)

print(f"Saved baseline dataset to: {OUTPUT}")

print("\nObject → Surface distribution:")
distribution = {}

for row in rows:
    key = f"{row['object']} -> {row['surface']}"
    distribution[key] = distribution.get(key, 0) + 1

for key, count in sorted(distribution.items(), key=lambda x: -x[1])[:30]:
    print(f"{key}: {count}")