u_r="servak11"
p_d="TestPwd2104#ak%1a"

APP_TITLE = "Work Tasks Plus"


import json

settings = {}

try:
    with open("settings.json") as f:
        settings = json.load(f)
except FileNotFoundError:
    settings = {
    }


THEMES = {
    "dark": {
        "bg_main": "#1e1e1e",       # Deep background
        "bg_card": "#252526",       # Sidebar / Card background
        "bg_input": "#2d2d2d",      # Entry / Treeview row background
        "fg_main": "#ffffff",       # Main text
        "fg_muted": "#aaaaaa",      # Secondary text labels
        "accent": "#1f538d",        # Active button/highlight
        "accent_hover": "#14375e",  # Hover state
        "tree_header": "#3a3a3a",   # Table header back
        "link": "#4a90e2",          # Hyperlink / ticket reference text
    },
    "bright": {
        "bg_main": "#f5f5f5",       # Crisp light background
        "bg_card": "#ffffff",       # Pure white sidebar / cards
        "bg_input": "#ffffff",      # Input elements background
        "fg_main": "#222222",       # Sharp dark text
        "fg_muted": "#666666",      # Soft gray labels
        "accent": "#007acc",        # Vibrant blue interactive elements
        "accent_hover": "#005999",  # Active blue hover
        "tree_header": "#e1e1e1",   # Light table header back
        "link": "#106ba3",          # Hyperlink / ticket reference text
    }
}