u_r="akovalevsky"
p_d="Menlo0104#ak%1a"

import json

settings = {}

try:
    with open("settings.json") as f:
        settings = json.load(f)
except FileNotFoundError:
    settings = {
    }