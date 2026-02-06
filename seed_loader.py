import json
import os

def load_seed_rows():
    seed_dir = os.path.join(os.path.dirname(__file__), "seed", "syllabus")
    rows = []

    for file in os.listdir(seed_dir):
        if file.endswith(".json"):
            with open(os.path.join(seed_dir, file), "r", encoding="utf-8") as f:
                data = json.load(f)
                rows.extend(data)

    return rows
