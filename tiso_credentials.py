"""Single source of Tisoware credentials.

Credentials live in ~/.tisobridge.conf, the same file tisobridge and
mod_buchungskorrektur.py read:

    [default]
    user = your_username
    password = your_tisoware_password

They used to sit in config.py as u_r/p_d with three junk characters appended.
That file was tracked, so the password it held is in git history from commit
6a474c0 and must be treated as compromised even though the file is now gone.
Nothing here falls back to the source tree: a missing conf file is an error,
not a reason to read a secret out of the repository.
"""

from configparser import ConfigParser
from pathlib import Path

CONF_PATH = Path.home() / ".tisobridge.conf"


def load_credentials(conf_path=None):
    """Return (user, password) from the conf file.

    Raises RuntimeError when the file is missing, unreadable or incomplete,
    so a run fails loudly here rather than typing empty strings into the
    login form and reporting a confusing Tisoware error.
    """
    user = password = None

    conf_path = Path(conf_path) if conf_path else CONF_PATH
    if not conf_path.exists():
        raise RuntimeError(
            f"no Tisoware credentials: create {conf_path} with a [default]"
            f" section containing user and password"
        )

    config = ConfigParser()
    try:
        config.read(conf_path)
    except Exception as exc:
        raise RuntimeError(f"cannot parse {conf_path}: {exc}") from None

    if config.has_section("default"):
        section = config["default"]
        # Values are used verbatim; the old config.py appended three junk
        # characters that had to be trimmed, this file does not.
        user = section.get("user") or None
        password = section.get("password") or None

    if not (user and password):
        missing = ", ".join(
            name for name, value in (("user", user), ("password", password))
            if not value
        )
        raise RuntimeError(
            f"{conf_path} is missing {missing} in its [default] section"
        )

    print(f"tiso_credentials: using {conf_path} (user {user!r})")
    return user, password
