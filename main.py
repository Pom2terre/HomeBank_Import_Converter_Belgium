#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
import sys
from pathlib import Path
from typing import Callable

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts import config as app_config
from scripts import select_and_convert
from scripts.services import configure_logging, get_logger

logger = get_logger(__name__)


def afficher_menu_principal() -> str:
    subprocess.run("cls" if sys.platform == "win32" else "clear", shell=True)
    print("=" * 80)
    print("🏦 BANK TO HOMEBANK CONVERTER")
    print("=" * 80)
    print("1 - Start Converters in text mode")
    print("2 - Start Converters in GUI mode")
    print("3 - Exit")
    print("=" * 80)
    return input("Choisissez une option : ").strip()


def lancer_mode_texte() -> None:
    logger.info("Starting converters in text mode")
    select_and_convert.main()


def lancer_mode_gui() -> None:
    logger.info("Starting converters in GUI mode")
    from scripts import gui_poc

    gui_poc.main()


MODE_ACTIONS: dict[str, Callable[[], None]] = {
    "1": lancer_mode_texte,
    "2": lancer_mode_gui,
}


def main() -> None:
    while True:
        choix = afficher_menu_principal()

        if choix == "3":
            logger.info("User selected exit from launcher")
            print("👋 Au revoir !")
            break

        action = MODE_ACTIONS.get(choix)
        if action is None:
            logger.warning("Invalid launcher option received: %s", choix)
            print("❌ Option invalide, veuillez réessayer.")
            input("\nAppuyez sur Entrée pour continuer...")
            continue

        action()
        input("\nAppuyez sur Entrée pour continuer...")


if __name__ == "__main__":
    configure_logging()
    for message in app_config.validate_startup_settings():
        if message.startswith("Warning:"):
            logger.warning(message)
            print(f"[Config] {message}")
        elif message.startswith("Info:"):
            logger.info(message)
    if sys.platform == "win32":
        subprocess.run(
            "chcp 65001",
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    main()
