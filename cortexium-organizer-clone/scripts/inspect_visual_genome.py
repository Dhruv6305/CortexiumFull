import json

PATH = r"E:\Afreen\SEM VII\cortexium-organizer\data\visual_genome\relationships.json"

with open(PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

print("Total images/records:", len(data))

if data:
    first = data[0]

    print("\nTop-level keys:")
    print(first.keys())

    print("\nFirst record:")
    print(json.dumps(first, indent=2)[:5000])

    if "relationships" in first and first["relationships"]:
        rel = first["relationships"][0]

        print("\nRelationship keys:")
        print(rel.keys())

        print("\nFirst relationship:")
        print(json.dumps(rel, indent=2)[:3000])