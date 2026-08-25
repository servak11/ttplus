"""Application settings, loaded from settings.json.

Replaces the settings half of the old config.py; the credentials half now
lives in tiso_credentials.py, backed by ~/.tisobridge.conf. Nothing secret
belongs in this file or in settings.json -- both are in the repository.

    from app_settings import settings
    url = settings.get("issue_url")
"""

import json
from pathlib import Path

SETTINGS_FILE = "settings.json"

# The old config.py opened settings.json relative to the working directory,
# so launching from anywhere but the repo root silently produced {}. Try the
# working directory first (unchanged behaviour when launched from the root),
# then fall back to the copy next to this module.
_CANDIDATES = (
    Path(SETTINGS_FILE),
    Path(__file__).resolve().parent / SETTINGS_FILE,
)


def load_settings():
    """Return the settings dict, or {} when no readable file is found."""
    for path in _CANDIDATES:
        try:
            with open(path) as f:
                return json.load(f)
        except FileNotFoundError:
            continue
        except (json.JSONDecodeError, OSError) as exc:
            print(f"app_settings: cannot read {path}: {exc}")
            return {}
    return {}


settings = load_settings()
