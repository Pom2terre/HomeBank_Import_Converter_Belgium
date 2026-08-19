"""Configuration with defaults, user overrides, env overrides, and startup validation."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT_DIR = ROOT / "scripts"

SETTING_KEYS = [
    "DOSSIER_SOURCE",
    "DOSSIER_SCRIPT",
    "DOSSIER_HOMEBANK",
    "PAYMENT_RULES",
    "OUTPUT_LANGUAGE",
    "DOSSIER_SORTIE_AMEX",
    "DOSSIER_SORTIE_KEYTRADE",
    "DOSSIER_SORTIE_ARGENTA",
    "DOSSIER_SORTIE_MASTERCARD",
]

ENV_KEYS = {
    "DOSSIER_SOURCE": "HBCONV_SOURCE_DIR",
    "DOSSIER_SCRIPT": "HBCONV_SCRIPT_DIR",
    "DOSSIER_HOMEBANK": "HBCONV_HOMEBANK_DIR",
    "PAYMENT_RULES": "HBCONV_PAYMENT_RULES",
    "OUTPUT_LANGUAGE": "HBCONV_OUTPUT_LANGUAGE",
    "DOSSIER_SORTIE_AMEX": "HBCONV_OUTPUT_AMEX_DIR",
    "DOSSIER_SORTIE_KEYTRADE": "HBCONV_OUTPUT_KEYTRADE_DIR",
    "DOSSIER_SORTIE_ARGENTA": "HBCONV_OUTPUT_ARGENTA_DIR",
    "DOSSIER_SORTIE_MASTERCARD": "HBCONV_OUTPUT_MASTERCARD_DIR",
}

CONFIG_FILE_ENV = "HBCONV_CONFIG_FILE"
DEFAULT_REPO_CONFIG_FILE = ROOT / "user_config.json"
DEFAULT_HOME_CONFIG_FILE = Path.home() / ".homebank_converter.json"
DEFAULT_EXECUTION_TRACE_FILE = Path.home() / ".homebank_converter_last_reports.json"

_STARTUP_VALIDATION_DONE = False
_STARTUP_MESSAGES: list[str] = []

# Declared defaults for static analyzers; values are replaced at runtime.
DOSSIER_SOURCE = ""
DOSSIER_SCRIPT = ""
DOSSIER_HOMEBANK = ""
PAYMENT_RULES = ""
OUTPUT_LANGUAGE = "english"
DOSSIER_SORTIE_AMEX = ""
DOSSIER_SORTIE_KEYTRADE = ""
DOSSIER_SORTIE_ARGENTA = ""
DOSSIER_SORTIE_MASTERCARD = ""


def _normalize_path(value: str) -> str:
    return str(Path(os.path.expandvars(os.path.expanduser(str(value)))))


def normalize_output_language_value(value: str | None) -> str:
    """Normalize GUI/CLI language names to the canonical values used by the app."""
    if value is None:
        return "english"
    normalized = str(value).strip().casefold()
    if normalized in {"fr", "fra", "france", "french", "français"}:
        return "french"
    return "english"


def _defaults() -> dict[str, str]:
    if sys.platform == "win32":
        downloads = Path.home() / "Downloads"
        docs = Path.home() / "OneDrive" / "Documents" / "HomeBank"
        return {
            "DOSSIER_SOURCE": str(downloads),
            "DOSSIER_SCRIPT": str(SCRIPT_DIR),
            "DOSSIER_HOMEBANK": str(docs),
            "PAYMENT_RULES": str(SCRIPT_DIR / "payment_rules.json"),
            "OUTPUT_LANGUAGE": "english",
            "DOSSIER_SORTIE_AMEX": str(downloads / "Import_Amex"),
            "DOSSIER_SORTIE_KEYTRADE": str(downloads / "Import_Keytrade"),
            "DOSSIER_SORTIE_ARGENTA": str(downloads / "Import_Argenta"),
            "DOSSIER_SORTIE_MASTERCARD": str(downloads / "Import_Mastercard"),
        }

    return {
        "DOSSIER_SOURCE": str(ROOT / "Input_file_examples"),
        "DOSSIER_SCRIPT": str(SCRIPT_DIR),
        "DOSSIER_HOMEBANK": str(ROOT / "homebank"),
        "PAYMENT_RULES": str(SCRIPT_DIR / "payment_rules.json"),
        "OUTPUT_LANGUAGE": "english",
        "DOSSIER_SORTIE_AMEX": str(ROOT / "tests" / "ci_output" / "Import_Amex"),
        "DOSSIER_SORTIE_KEYTRADE": str(
            ROOT / "tests" / "ci_output" / "Import_Keytrade"
        ),
        "DOSSIER_SORTIE_ARGENTA": str(ROOT / "tests" / "ci_output" / "Import_Argenta"),
        "DOSSIER_SORTIE_MASTERCARD": str(
            ROOT / "tests" / "ci_output" / "Import_Mastercard"
        ),
    }


def _candidate_config_files() -> list[Path]:
    explicit = os.getenv(CONFIG_FILE_ENV)
    files = []
    if explicit:
        files.append(Path(explicit))
    files.extend([DEFAULT_REPO_CONFIG_FILE, DEFAULT_HOME_CONFIG_FILE])
    return files


def _load_user_overrides() -> tuple[dict[str, str], list[str]]:
    messages: list[str] = []
    merged: dict[str, str] = {}

    for candidate in _candidate_config_files():
        if not candidate.exists():
            continue
        try:
            content = json.loads(candidate.read_text(encoding="utf-8"))
        except Exception as exc:
            messages.append(
                f"Warning: unable to parse user config file '{candidate}': {exc}"
            )
            continue

        raw_settings = (
            content.get("paths", content) if isinstance(content, dict) else {}
        )
        if not isinstance(raw_settings, dict):
            messages.append(
                f"Warning: user config file '{candidate}' has invalid structure. Expected JSON object."
            )
            continue

        for key in SETTING_KEYS:
            value = raw_settings.get(key)
            if isinstance(value, str) and value.strip():
                if key == "OUTPUT_LANGUAGE":
                    merged[key] = normalize_output_language_value(value)
                else:
                    merged[key] = _normalize_path(value)
        messages.append(f"Info: loaded user config overrides from '{candidate}'.")

    return merged, messages


def _load_settings() -> tuple[dict[str, str], list[str]]:
    messages: list[str] = []
    settings = {k: _normalize_path(v) for k, v in _defaults().items()}

    file_overrides, file_messages = _load_user_overrides()
    settings.update(file_overrides)
    messages.extend(file_messages)

    for setting_key, env_key in ENV_KEYS.items():
        env_value = os.getenv(env_key)
        if env_value and env_value.strip():
            if setting_key == "OUTPUT_LANGUAGE":
                settings[setting_key] = normalize_output_language_value(env_value)
            else:
                settings[setting_key] = _normalize_path(env_value)
            messages.append(
                f"Info: environment override applied for {setting_key} from {env_key}."
            )

    return settings, messages


def _set_globals(settings: dict[str, str]) -> None:
    for key in SETTING_KEYS:
        globals()[key] = settings[key]


def _ensure_dir(
    path_value: str, label: str, fallback: Path, messages: list[str]
) -> str:
    path = Path(path_value)
    try:
        path.mkdir(parents=True, exist_ok=True)
        return str(path)
    except Exception as exc:
        messages.append(
            f"Warning: '{label}' path '{path}' is not usable ({exc}). "
            f"Falling back to '{fallback}'."
        )
        fallback.mkdir(parents=True, exist_ok=True)
        return str(fallback)


def validate_startup_settings() -> list[str]:
    """Validate configured folders/files and apply friendly fallback recovery when needed."""
    global _STARTUP_VALIDATION_DONE, _STARTUP_MESSAGES

    if _STARTUP_VALIDATION_DONE:
        return list(_STARTUP_MESSAGES)

    messages = list(_STARTUP_MESSAGES)

    runtime_base = ROOT / "runtime_recovery"
    runtime_base.mkdir(parents=True, exist_ok=True)

    source_fallback = (
        Path.home() / "Downloads"
        if sys.platform == "win32"
        else ROOT / "Input_file_examples"
    )
    homebank_fallback = runtime_base / "homebank"

    globals()["DOSSIER_SOURCE"] = _ensure_dir(
        DOSSIER_SOURCE, "DOSSIER_SOURCE", source_fallback, messages
    )
    globals()["DOSSIER_HOMEBANK"] = _ensure_dir(
        DOSSIER_HOMEBANK, "DOSSIER_HOMEBANK", homebank_fallback, messages
    )

    output_keys = [
        "DOSSIER_SORTIE_AMEX",
        "DOSSIER_SORTIE_KEYTRADE",
        "DOSSIER_SORTIE_ARGENTA",
        "DOSSIER_SORTIE_MASTERCARD",
    ]
    for key in output_keys:
        fallback = runtime_base / key.casefold()
        globals()[key] = _ensure_dir(globals()[key], key, fallback, messages)

    rules_path = Path(PAYMENT_RULES)
    if not rules_path.exists():
        fallback_candidates = [
            Path(DOSSIER_SCRIPT) / "payment_rules.json",
            ROOT / "payment_rules.json",
            ROOT / "scripts" / "payment_rules.json",
        ]
        fallback_rules = next((p for p in fallback_candidates if p.exists()), None)
        if fallback_rules is not None:
            globals()["PAYMENT_RULES"] = str(fallback_rules)
            messages.append(
                f"Warning: PAYMENT_RULES file '{rules_path}' not found. "
                f"Using fallback '{fallback_rules}'."
            )
        else:
            messages.append(
                f"Warning: PAYMENT_RULES file '{rules_path}' not found and fallback is missing too. "
                "Conversions will continue with built-in defaults where possible."
            )

    _STARTUP_MESSAGES = messages
    _STARTUP_VALIDATION_DONE = True
    return list(_STARTUP_MESSAGES)


# Build runtime settings once at import time (without noisy prints).
_SETTINGS, _LOAD_MESSAGES = _load_settings()
_set_globals(_SETTINGS)
_STARTUP_MESSAGES.extend(_LOAD_MESSAGES)
