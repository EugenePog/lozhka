#!/usr/bin/env python
"""Django management entry point. Run from services/api/src (see Makefile targets)."""
import os
import sys
from pathlib import Path

# Workspace packages are normally importable through the editable installs in .venv. Add their source
# folders as a fallback so a broken or hidden .pth file (seen on macOS) cannot stop the project.
_ROOT = Path(__file__).resolve().parents[3]
for _src in [*(_ROOT / "services").glob("*/src"), *(_ROOT / "libs").glob("*/src")]:
    if str(_src) not in sys.path:
        sys.path.append(str(_src))


def main() -> None:
    # The staff-side settings are the default for management commands: migrations, seeding and the
    # sweeps need every installed app, and both settings modules install the same apps.
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.backoffice")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
