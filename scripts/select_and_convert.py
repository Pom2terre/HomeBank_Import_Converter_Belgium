#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Select a file from Downloads, detect converter, then rename/backup/convert."""

import os
import shutil
from pathlib import Path

try:
    from scripts.typing_contracts import ConverterModuleName, ConverterName
except Exception:
    from typing_contracts import ConverterModuleName, ConverterName

try:
    from scripts import config as app_config
except Exception:
    import config as app_config
try:
    from scripts.services import ConversionService, get_logger
except Exception:
    from services.conversion_service import ConversionService
    from services.logging_service import get_logger

try:
    from scripts.converters.utils import get_cli_text
except Exception:
    from converters.utils import get_cli_text


DOWNLOADS = Path.home() / "Downloads"
ALLOWED_EXT = {".pdf", ".csv", ".xlsx"}
HOME_BANK_CSV_PREFIXES = ("hb_", "homebank_")
conversion_service = ConversionService()
logger = get_logger(__name__)


def list_download_files() -> list[Path]:
    if not DOWNLOADS.exists():
        logger.warning("Downloads folder not found: %s", DOWNLOADS)
        print(get_cli_text("downloads_missing", path=DOWNLOADS))
        return []

    entries: list[tuple[float, Path]] = []
    with os.scandir(DOWNLOADS) as scan_iter:
        for entry in scan_iter:
            if not entry.is_file():
                continue

            suffix = Path(entry.name).suffix.lower()
            if suffix not in ALLOWED_EXT:
                continue

            lowered_name = entry.name.lower()
            if lowered_name.startswith(HOME_BANK_CSV_PREFIXES) and suffix == ".csv":
                continue

            try:
                mtime = entry.stat().st_mtime
            except OSError:
                continue
            entries.append((mtime, Path(entry.path)))

    files = [p for _, p in sorted(entries, key=lambda item: item[0], reverse=True)]
    logger.info("Found %d candidate file(s) in Downloads", len(files))
    return files


def ensure_backup_dir():
    b = DOWNLOADS / "backup"
    b.mkdir(exist_ok=True)
    return b


def do_rename(path: Path):
    new_name = input(f"{get_cli_text('rename_input')} ").strip()
    if not new_name:
        print(get_cli_text("rename_cancelled"))
        return
    if not Path(new_name).suffix:
        new_name = new_name + path.suffix
    dst = path.with_name(new_name)
    try:
        path.replace(dst)
        logger.info("Renamed %s to %s", path, dst)
        print(get_cli_text("renamed", path=dst))
    except Exception as e:
        logger.exception("Rename failed for %s", path)
        print(get_cli_text("rename_failed", error=e))


def do_backup(path: Path):
    bdir = ensure_backup_dir()
    dst = bdir / path.name
    if dst.exists():
        dst = bdir / f"{path.stem}_{int(path.stat().st_mtime)}{path.suffix}"
    try:
        shutil.copy2(path, dst)
        logger.info("Backed up %s to %s", path, dst)
        print(get_cli_text("backed_up", path=dst))
    except Exception as e:
        logger.exception("Backup failed for %s", path)
        print(get_cli_text("backup_failed", error=e))


def do_convert(path: Path, detected: ConverterName, module_name: ConverterModuleName):
    logger.info("Launching conversion for %s with %s", path, module_name)
    print(
        get_cli_text("launching_converter", detected=detected, module_name=module_name)
    )
    result = conversion_service.convert(path, detected, module_name)
    if result.status != "OK":
        logger.error("Conversion failed for %s: %s", path, result.error)
        print(get_cli_text("conversion_failed", error=result.error))


def main():
    for message in app_config.validate_startup_settings():
        if message.startswith("Warning:"):
            logger.warning(message)
            print(f"[Config] {message}")

    while True:
        files = list_download_files()
        if not files:
            print(get_cli_text("no_matching_files"))
            return

        print()
        print("=" * 72)
        print(f"🏦 {get_cli_text('header_title')}")
        print("=" * 72)
        print(get_cli_text("select_file_prompt"))
        for i, f in enumerate(files, start=1):
            print(f"  {i:2d}. {f.name:<35} [{f.suffix.upper()}]")
        print(f"  0. {get_cli_text('quit')}")
        print("=" * 72)

        sel = input(f"👉 {get_cli_text('select_file_number')} ").strip()
        if sel == "0":
            logger.info("User cancelled text-mode selection")
            print(f"\n{get_cli_text('confirm_exit')}")
            return
        if not sel.isdigit():
            print(f"\n{get_cli_text('invalid_choice')}")
            continue
        idx = int(sel) - 1
        if idx < 0 or idx >= len(files):
            print(f"\n{get_cli_text('out_of_range')}")
            continue

        path = files[idx]
        detection = conversion_service.detect(path)
        detected, module_name = detection.converter, detection.module_name
        if not detected or not module_name:
            logger.info("No converter detected for %s", path)
            print(f"\n{get_cli_text('no_converter_detected')}")
            continue

        print()
        print("=" * 72)
        print(
            f"✅ {get_cli_text('file_detected', detected=detected.upper(), module_name=module_name)}"
        )
        print("=" * 72)
        print(get_cli_text("action_prompt"))
        print(f"  1) {get_cli_text('rename_file')}")
        print(f"  2) {get_cli_text('backup_copy')}")
        print(f"  3) {get_cli_text('convert_file')}")
        print(f"  4) {get_cli_text('cancel_action')}")
        print("=" * 72)

        act = input(f"👉 {get_cli_text('action_choice')} ").strip()
        if act == "1":
            do_rename(path)
        elif act == "2":
            do_backup(path)
        elif act == "3":
            do_convert(path, detected, module_name)
        else:
            print(f"\n{get_cli_text('operation_cancelled')}")

        again = input(f"\n{get_cli_text('another_file_prompt')} ").strip().lower()
        if again not in {"", "o", "y", "yes"}:
            logger.info("User exited text-mode workflow")
            print(f"\n{get_cli_text('thank_you')}")
            return


if __name__ == "__main__":
    main()
