#!/usr/bin/env python3
"""GUI-only launcher used by double-click and packaged Windows builds."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _configure_packaged_env() -> None:
    """Set sane defaults for packaged runs when env vars are not provided."""
    if not getattr(sys, "frozen", False):
        return

    base_dir = Path(sys.executable).resolve().parent
    internal_dir = base_dir / "_internal"

    script_dir_candidates = [
        internal_dir / "scripts",
        base_dir / "scripts",
        internal_dir,
        base_dir,
    ]
    script_dir = next((p for p in script_dir_candidates if p.exists()), base_dir)

    rules_candidates = [
        script_dir / "payment_rules.json",
        internal_dir / "payment_rules.json",
        base_dir / "payment_rules.json",
    ]
    rules_file = next((p for p in rules_candidates if p.exists()), None)

    os.environ.setdefault("HBCONV_SOURCE_DIR", str(Path.home() / "Downloads"))
    os.environ.setdefault("HBCONV_SCRIPT_DIR", str(script_dir))
    os.environ.setdefault(
        "HBCONV_HOMEBANK_DIR", str(Path.home() / "Documents" / "HomeBank")
    )

    if rules_file is not None:
        os.environ.setdefault("HBCONV_PAYMENT_RULES", str(rules_file))


if __name__ == "__main__":
    _configure_packaged_env()
    from scripts import gui_poc

    gui_poc.main()
