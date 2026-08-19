#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fonctions utilitaires partagées entre les convertisseurs."""

from __future__ import annotations

import csv
import logging
import math
import sys
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import TYPE_CHECKING, Iterable, Literal, Sequence, cast, overload

if TYPE_CHECKING:
    from . import statistics as stats_module  # noqa: F401

logger = logging.getLogger(__name__)

FIELDS = ["date", "payment", "info", "payee", "memo", "amount", "category", "tags"]
FIELDS_FRENCH = [
    "date",
    "paiement",
    "info",
    "beneficiaire",
    "memo",
    "montant",
    "categorie",
    "tags",
]
DATE_FORMATS = ["%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y", "%Y-%m-%d", "%d/%m/%y", "%d-%m-%y"]

OUTPUT_LANGUAGE_FIELDNAMES = {
    "english": FIELDS,
    "french": FIELDS_FRENCH,
}


def folded(value) -> str:
    if value is None:
        return ""
    value = str(value)
    value = value.casefold().strip()
    return "".join(ch for ch in value if ch.isalnum() or ch.isspace())


def find_column(columns: Sequence[str], choices: Iterable[str]) -> str | None:
    columns_folded = [folded(c) for c in columns]
    for choice in choices:
        folded_choice = folded(choice)
        if folded_choice in columns_folded:
            return columns[columns_folded.index(folded_choice)]
    for choice in choices:
        folded_choice = folded(choice)
        for index, column in enumerate(columns_folded):
            if folded_choice in column or column in folded_choice:
                return columns[index]
    return None


def find_header_row(df):
    candidates = [
        "date",
        "operation",
        "opération",
        "montant",
        "amount",
        "libellé",
        "libelle",
        "référence",
        "reference",
        "ref",
        "memo",
        "communication",
        "payee",
        "bénéficiaire",
        "beneficiaire",
    ]
    for idx in range(min(10, len(df))):
        row = df.iloc[idx].fillna("").astype(str)
        normalized = [folded(str(v)) for v in row.tolist()]
        hits = sum(
            1 for val in normalized if any(choice in val for choice in candidates)
        )
        if hits >= 3:
            return idx
    return None


def guess_column(columns, df, kind):
    if kind == "date":
        candidates = [
            "date",
            "date opération",
            "date operation",
            "date valeur",
            "date comptable",
            "date transaction",
            "transaction",
        ]
    elif kind == "amount":
        candidates = [
            "montant",
            "amount",
            "valeur",
            "débit",
            "credit",
            "crédit",
            "somme",
        ]
    else:
        candidates = [
            "libellé",
            "libelle",
            "description",
            "opération",
            "intitulé",
            "transaction",
            "motif",
            "designation",
            "détails",
            "details",
            "pour",
            "payee",
            "bénéficiaire",
            "beneficiaire",
        ]

    for choice in candidates:
        column = find_column(columns, [choice])
        if column:
            return column

    if kind == "date":
        for column in columns:
            sample = df[column].dropna().astype(str).head(10)
            if any(parse_date(value) is not None for value in sample):
                return column
    elif kind == "amount":
        for column in columns:
            sample = df[column].dropna().astype(str).head(10)
            if any(parse_float(value) is not None for value in sample):
                return column
    else:
        for column in columns:
            if df[column].dropna().astype(str).apply(len).mean() > 5:
                return column

    return None


def parse_float(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and math.isnan(value):
            return None
        return float(value)
    raw = str(value).replace("€", "").replace("EUR", "").replace(" ", "")
    if "." in raw and "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    elif "," in raw:
        raw = raw.replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def parse_decimal(value) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, (int, float, Decimal)):
        try:
            return Decimal(str(value))
        except InvalidOperation:
            return None
    raw = str(value).replace("€", "").replace("EUR", "").replace(" ", "")
    if "," in raw and "." in raw:
        raw = (
            raw.replace(".", "")
            if raw.rfind(",") > raw.rfind(".")
            else raw.replace(",", "")
        )
    elif "," in raw:
        raw = raw.replace(",", ".")
    try:
        return Decimal(raw)
    except InvalidOperation:
        return None


def parse_date(
    value, formats: Iterable[str] | None = None, dayfirst: bool = True
) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if hasattr(value, "to_pydatetime"):
        try:
            return cast(datetime, value.to_pydatetime())
        except Exception:
            pass
    value_str = str(value).strip()
    if not value_str:
        return None
    formats = formats or DATE_FORMATS
    for fmt in formats:
        try:
            return datetime.strptime(value_str, fmt)
        except ValueError:
            continue
    return None


def resolve_output_language(language: str | None = None) -> str:
    """Return the selected output CSV language."""
    if language:
        normalized = str(language).strip().lower()
        if normalized in {"fr", "france", "french", "français", "fra"}:
            return "french"
        return "english"

    try:
        from scripts import config as app_config
    except Exception:
        try:
            import config as app_config
        except Exception:
            return "english"

    value = (
        str(getattr(app_config, "OUTPUT_LANGUAGE", "english") or "english")
        .strip()
        .lower()
    )
    if value in {"fr", "france", "french", "français", "fra"}:
        return "french"
    return "english"


CLI_TEXT = {
    "downloads_missing": {
        "english": "Downloads folder not found: {path}",
        "french": "Dossier Downloads introuvable : {path}",
    },
    "header_title": {
        "english": "HOMEBANK CONVERTER - FILE TO PROCESS",
        "french": "HOMEBANK CONVERTER - FICHIER À TRAITER",
    },
    "select_file_prompt": {
        "english": "Select a file from your Downloads folder:",
        "french": "Sélectionnez un fichier dans votre dossier Downloads :",
    },
    "select_file_number": {
        "english": "Enter the number of your choice:",
        "french": "Entrez le numéro de votre choix :",
    },
    "confirm_exit": {
        "english": "Goodbye. Thank you for using HomeBank Converter.",
        "french": "Au revoir. Merci d'avoir utilisé HomeBank Converter.",
    },
    "invalid_choice": {
        "english": "Error: invalid input. Please choose a valid number.",
        "french": "Erreur : saisie invalide. Veuillez choisir un nombre valide.",
    },
    "out_of_range": {
        "english": "Error: selection out of range. Please try again.",
        "french": "Erreur : sélection hors de portée. Réessayez.",
    },
    "no_converter_detected": {
        "english": "No compatible converter detected for this file.\nPlease choose another file from the list.",
        "french": "Aucun convertisseur compatible détecté pour ce fichier.\nVeuillez choisir un autre fichier dans la liste.",
    },
    "file_detected": {
        "english": "Detected file: {detected}  |  Module: {module_name}",
        "french": "Fichier détecté : {detected}  |  Module : {module_name}",
    },
    "action_prompt": {
        "english": "What would you like to do?",
        "french": "Que souhaitez-vous faire ?",
    },
    "rename_file": {
        "english": "Rename the file",
        "french": "Renommer le fichier",
    },
    "backup_copy": {
        "english": "Save a backup copy",
        "french": "Sauvegarder une copie de sécurité",
    },
    "convert_file": {
        "english": "Convert the file",
        "french": "Convertir le fichier",
    },
    "cancel_action": {
        "english": "Cancel",
        "french": "Annuler",
    },
    "action_choice": {
        "english": "Choice:",
        "french": "Choix :",
    },
    "rename_input": {
        "english": "Enter new file name (no path, extension will be preserved):",
        "french": "Entrez le nouveau nom du fichier (sans chemin, l'extension sera conservée) :",
    },
    "rename_cancelled": {
        "english": "Rename cancelled.",
        "french": "Renommage annulé.",
    },
    "renamed": {
        "english": "Renamed: {path}",
        "french": "Renommé : {path}",
    },
    "rename_failed": {
        "english": "Rename failed: {error}",
        "french": "Échec du renommage : {error}",
    },
    "backed_up": {
        "english": "Backed up to: {path}",
        "french": "Sauvegardé dans : {path}",
    },
    "backup_failed": {
        "english": "Backup failed: {error}",
        "french": "Échec de la sauvegarde : {error}",
    },
    "launching_converter": {
        "english": "Launching converter: {detected} (module {module_name})",
        "french": "Lancement du convertisseur : {detected} (module {module_name})",
    },
    "conversion_failed": {
        "english": "Conversion failed: {error}",
        "french": "Échec de la conversion : {error}",
    },
    "no_matching_files": {
        "english": "No matching files in Downloads.",
        "french": "Aucun fichier compatible dans le dossier Downloads.",
    },
    "another_file_prompt": {
        "english": "Would you like to process another file? (y/N):",
        "french": "Souhaitez-vous traiter un autre fichier ? (O/n) :",
    },
    "thank_you": {
        "english": "Thank you and see you soon.",
        "french": "Merci et à bientôt.",
    },
    "operation_cancelled": {
        "english": "Operation cancelled.",
        "french": "Opération annulée.",
    },
    "quit": {
        "english": "Quit",
        "french": "Quitter",
    },
    "option_separator": {
        "english": "=" * 72,
        "french": "=" * 72,
    },
    "gui_title": {
        "english": "HomeBank Inport File Maker",
        "french": "HomeBank Inport File Maker",
    },
    "menu_files": {"english": "Files", "french": "Fichiers"},
    "menu_add_files": {"english": "Add Files", "french": "Ajouter des fichiers"},
    "menu_add_folder": {"english": "Add Folder", "french": "Ajouter un dossier"},
    "menu_exit": {"english": "Exit", "french": "Quitter"},
    "menu_options": {"english": "Options", "french": "Options"},
    "menu_language": {"english": "Language", "french": "Langue"},
    "menu_display_mode": {"english": "Display Mode", "french": "Mode d'affichage"},
    "menu_clear": {"english": "Clear", "french": "Effacer"},
    "menu_actions": {"english": "Actions", "french": "Actions"},
    "menu_convert_selected": {
        "english": "Convert Selected",
        "french": "Convertir la sélection",
    },
    "menu_convert_all": {"english": "Convert All", "french": "Tout convertir"},
    "menu_remove_selected": {
        "english": "Remove Selected",
        "french": "Supprimer la sélection",
    },
    "menu_retry_failed": {"english": "Retry Failed", "french": "Réessayer les échecs"},
    "menu_reports": {"english": "Reports", "french": "Rapports"},
    "menu_open_output_folder": {
        "english": "Open Output Folder",
        "french": "Ouvrir le dossier de sortie",
    },
    "menu_view_reports": {"english": "View Reports", "french": "Voir les rapports"},
    "csv_language_label": {
        "english": "CSV language:",
        "french": "Langue CSV :",
    },
    "english_label": {
        "english": "English",
        "french": "Anglais",
    },
    "light_label": {
        "english": "Light",
        "french": "Clair",
    },
    "dark_label": {
        "english": "Dark",
        "french": "Sombre",
    },
    "french_label": {
        "english": "Français",
        "french": "Français",
    },
    "add_files": {
        "english": "➕ Add Files",
        "french": "➕ Ajouter des fichiers",
    },
    "add_folder": {
        "english": "📂 Add Folder",
        "french": "📂 Ajouter un dossier",
    },
    "remove_selected": {
        "english": "🗑️ Remove Selected",
        "french": "🗑️ Supprimer la sélection",
    },
    "convert_selected": {
        "english": "🔄 Convert Selected",
        "french": "🔄 Convertir la sélection",
    },
    "convert_all": {
        "english": "🚀 Convert All",
        "french": "🚀 Tout convertir",
    },
    "retry_failed": {
        "english": "🔁 Retry Failed",
        "french": "🔁 Réessayer les échecs",
    },
    "open_output_folder": {
        "english": "📁 Open Output Folder",
        "french": "📁 Ouvrir le dossier de sortie",
    },
    "view_report": {
        "english": "📊 View Report",
        "french": "📊 Voir le rapport",
    },
    "open_report": {
        "english": "Open Report",
        "french": "Ouvrir le rapport",
    },
    "convert": {
        "english": "Convert",
        "french": "Convertir",
    },
    "clear": {
        "english": "🧹 Clear",
        "french": "🧹 Effacer",
    },
    "exit": {
        "english": "🚪 Exit",
        "french": "🚪 Quitter",
    },
    "column_file": {"english": "File", "french": "Fichier"},
    "column_detected": {"english": "Detected", "french": "Détecté"},
    "column_module": {"english": "Module", "french": "Module"},
    "column_status": {"english": "Status", "french": "Statut"},
    "column_output": {"english": "Output", "french": "Sortie"},
    "column_report": {"english": "Report", "french": "Rapport"},
    "column_error": {"english": "Error", "french": "Erreur"},
    "output_language_status": {
        "english": "Output CSV language: {selected}",
        "french": "Langue CSV de sortie : {selected}",
    },
    "display_mode_status": {
        "english": "Display mode: {selected}",
        "french": "Mode d'affichage : {selected}",
    },
    "status_no_files_loaded": {
        "english": "No files loaded",
        "french": "Aucun fichier chargé",
    },
    "status_loaded_summary": {
        "english": "Loaded {count} file(s), added {added}",
        "french": "{count} fichier(s) chargé(s), {added} ajouté(s)",
    },
    "status_loaded_folder_summary": {
        "english": "Loaded {count} file(s), added {added} from folder",
        "french": "{count} fichier(s) chargé(s), {added} ajouté(s) depuis le dossier",
    },
    "status_loaded_count": {
        "english": "Loaded {count} file(s)",
        "french": "{count} fichier(s) chargé(s)",
    },
    "status_done_summary": {
        "english": "Done - OK: {ok}, Failed: {failed}, Skipped: {skipped}",
        "french": "Terminé - OK : {ok}, Échec : {failed}, Ignorés : {skipped}",
    },
    "summary_ok_report": {
        "english": "OK",
        "french": "OK",
    },
    "select_bank_files": {
        "english": "Select bank files",
        "french": "Sélectionner les fichiers bancaires",
    },
    "select_folder_bank_files": {
        "english": "Select folder with bank files",
        "french": "Sélectionner le dossier contenant les fichiers bancaires",
    },
    "supported_files": {"english": "Supported", "french": "Pris en charge"},
    "all_files": {"english": "All files", "french": "Tous les fichiers"},
    "no_converter_detected_row": {
        "english": "No converter detected",
        "french": "Aucun convertisseur détecté",
    },
    "please_select_rows": {
        "english": "Please select one or more rows first.",
        "french": "Veuillez sélectionner au moins une ligne.",
    },
    "no_files_to_convert": {
        "english": "No files to convert.",
        "french": "Aucun fichier à convertir.",
    },
    "no_failed_rows": {
        "english": "No failed or skipped rows to retry.",
        "french": "Aucune ligne en échec ou ignorée à réessayer.",
    },
    "please_select_one_row": {
        "english": "Please select one row first.",
        "french": "Veuillez sélectionner une ligne.",
    },
    "remove": {
        "english": "Remove",
        "french": "Retirer",
    },
    "row_no_output_path": {
        "english": "Selected row has no output path yet.",
        "french": "La ligne sélectionnée n'a pas encore de chemin de sortie.",
    },
    "select_output_folder": {
        "english": "Select output folder",
        "french": "Sélectionner le dossier de sortie",
    },
    "no_import_output_folders": {
        "english": "No Import_* output folders were found in {folder}.",
        "french": "Aucun dossier de sortie Import_* n'a été trouvé dans {folder}.",
    },
    "folder_missing": {
        "english": "Folder does not exist: {folder}",
        "french": "Le dossier n'existe pas : {folder}",
    },
    "row_no_report": {
        "english": "Selected row has no report file yet. Run conversion first.",
        "french": "La ligne sélectionnée n'a pas encore de rapport. Lancez d'abord la conversion.",
    },
    "please_select_successful_row": {
        "english": "Please select a successfully converted row first.",
        "french": "Veuillez d'abord sélectionner une ligne convertie avec succès.",
    },
    "report_missing": {
        "english": "Report file does not exist: {report_path}",
        "french": "Le fichier de rapport n'existe pas : {report_path}",
    },
    "financial_dashboard": {
        "english": "💼 Financial Dashboard",
        "french": "💼 Tableau de bord financier",
    },
    "payment_mix": {
        "english": "💳 Payment mix",
        "french": "💳 Répartition des paiements",
    },
    "payment_breakdown": {
        "english": "💳 Payment Type Breakdown",
        "french": "💳 Répartition par type de paiement",
    },
    "detailed_report": {
        "english": "📝 Detailed report",
        "french": "📝 Rapport détaillé",
    },
    "open_raw_report": {
        "english": "📂 Open Raw Report",
        "french": "📂 Ouvrir le rapport brut",
    },
    "close": {"english": "❌ Close", "french": "❌ Fermer"},
    "summary_card": {"english": "💡 Summary card", "french": "💡 Fiche synthèse"},
    "status_result": {
        "english": "OK: {ok}\nFailed: {failed}\nSkipped: {skipped}",
        "french": "OK : {ok}\nÉchec : {failed}\nIgnorés : {skipped}",
    },
    "selected_conversion_finished": {
        "english": "Selected conversion finished",
        "french": "Conversion de la sélection terminée",
    },
    "full_conversion_finished": {
        "english": "Full conversion finished",
        "french": "Conversion complète terminée",
    },
    "retry_finished": {
        "english": "Retry finished",
        "french": "Nouvelle tentative terminée",
    },
    "open_report_error": {
        "english": "Unable to open report: {exc}",
        "french": "Impossible d'ouvrir le rapport : {exc}",
    },
    "status_row_removed": {
        "english": "Removed {name} from the list",
        "french": "{name} a été retiré de la liste",
    },
    "configuration_warnings": {
        "english": "Configuration warnings",
        "french": "Alertes de configuration",
    },
    "config_recovered": {
        "english": "Some configuration paths were recovered automatically:\n\n{messages}",
        "french": "Certains chemins de configuration ont été restaurés automatiquement :\n\n{messages}",
    },
    "service_unsupported_module": {
        "english": "Unsupported converter module requested: {module_name}",
        "french": "Module de convertisseur non pris en charge demandé : {module_name}",
    },
    "service_skipping_no_converter": {
        "english": "Skipping {file}: no converter detected",
        "french": "Ignoré : {file} ; aucun convertisseur détecté",
    },
    "service_batch_start": {
        "english": "Starting batch conversion for {count} file(s)",
        "french": "Début de la conversion par lots pour {count} fichier(s)",
    },
    "service_batch_finished": {
        "english": "Batch conversion finished",
        "french": "Conversion par lots terminée",
    },
    "service_conversion_failed": {
        "english": "Conversion failed for {file} with module {module_name}",
        "french": "Échec de la conversion pour {file} avec le module {module_name}",
    },
    "service_loaded_statistics": {
        "english": "Loaded statistics: {count} transactions, {net:+.2f} {currency}",
        "french": "Statistiques chargées : {count} transaction(s), {net:+.2f} {currency}",
    },
    "service_no_converter_detected": {
        "english": "No converter detected for {file}",
        "french": "Aucun convertisseur détecté pour {file}",
    },
    "service_invalid_report_json": {
        "english": "Invalid JSON in report {report}: {error}",
        "french": "JSON invalide dans le rapport {report} : {error}",
    },
    "service_report_load_failed": {
        "english": "Failed to load statistics from {report}: {error}",
        "french": "Impossible de charger les statistiques depuis {report} : {error}",
    },
    "service_conversion_completed": {
        "english": "Conversion completed for {file}",
        "french": "Conversion terminée pour {file}",
    },
    "report_window_title": {
        "english": "📊 Statistics Report - {name}",
        "french": "📊 Rapport de statistiques - {name}",
    },
    "report_label_mastercard": {
        "english": "Mastercard report",
        "french": "Rapport Mastercard",
    },
    "report_label_amex": {
        "english": "American Express report",
        "french": "Rapport American Express",
    },
    "report_label_argenta": {
        "english": "Argenta report",
        "french": "Rapport Argenta",
    },
    "report_label_keytrade": {
        "english": "Keytrade report",
        "french": "Rapport Keytrade",
    },
    "report_label_generic": {
        "english": "{name} report",
        "french": "Rapport {name}",
    },
    "currency_eur": {"english": "EUR", "french": "EUR"},
    "transaction_short": {"english": "Txns", "french": "Opérations"},
    "revenues": {"english": "💰 Revenues", "french": "💰 Revenus"},
    "expenses": {"english": "💸 Expenses", "french": "💸 Dépenses"},
    "net": {"english": "📉 Net", "french": "📉 Net"},
    "skipped": {"english": "⚠️ Skipped", "french": "⚠️ Ignorés"},
    "report_title": {"english": "Report", "french": "Rapport"},
    "payment": {"english": "Payment", "french": "Paiement"},
    "transactions": {"english": "Transactions", "french": "Transactions"},
    "amount": {"english": "Amount", "french": "Montant"},
    "details": {"english": "Details", "french": "Détails"},
    "stat_up": {"english": "📈 Up", "french": "📈 Hausse"},
    "stat_down": {"english": "📉 Down", "french": "📉 Baisse"},
    "stat_unchanged": {"english": "➖ Unchanged", "french": "➖ Inchangé"},
}


def get_localized_text(key: str, language: str | None = None, **kwargs) -> str:
    """Return localized UI/CLI strings using the configured output language."""
    resolved = resolve_output_language(language)
    mapping = CLI_TEXT.get(key) or {}
    template = mapping.get(resolved) or mapping.get("english") or str(key)
    if kwargs:
        return template.format(**kwargs)
    return template


def get_cli_text(key: str, language: str | None = None, **kwargs) -> str:
    """Return localized CLI labels using the configured output language."""
    return get_localized_text(key, language=language, **kwargs)


def translate_rows_for_output(rows, language: str | None = None):
    """Translate row keys and human-readable payment labels to the selected CSV language."""
    resolved = resolve_output_language(language)
    fieldnames = OUTPUT_LANGUAGE_FIELDNAMES[resolved]
    key_mapping = {
        "date": "date",
        "payment": "paiement" if resolved == "french" else "payment",
        "info": "info",
        "payee": "beneficiaire" if resolved == "french" else "payee",
        "memo": "memo",
        "amount": "montant" if resolved == "french" else "amount",
        "category": "categorie" if resolved == "french" else "category",
        "tags": "tags",
    }
    info_translations = {
        "credit card": "Carte de crédit",
        "carte de crédit": "Carte de crédit",
        "debit card": "Carte de débit",
        "carte de débit": "Carte de débit",
        "bank transfer": "Virement bancaire",
        "virement bancaire": "Virement bancaire",
        "outgoing transfer": "Virement sortant",
        "virement sortant": "Virement sortant",
        "incoming transfer": "Virement entrant",
        "virement entrant": "Virement entrant",
        "sepa direct debit": "Prélèvement SEPA",
        "prélèvement sepa": "Prélèvement SEPA",
        "direct debit": "Prélèvement",
        "prélèvement": "Prélèvement",
        "cash": "Espèces",
        "espèces": "Espèces",
        "cheque": "Chèque",
        "chèque": "Chèque",
        "standing order": "Virement permanent",
        "virement permanent": "Virement permanent",
        "ordre permanent": "Virement permanent",
        "mobile phone": "Téléphone portable",
        "téléphone portable": "Téléphone portable",
        "e-commerce payment card": "Carte de paiement e-commerce",
        "carte de paiement e-commerce": "Carte de paiement e-commerce",
        "outgoing instant transfer": "Virement instantané sortant",
        "virement instantané sortant": "Virement instantané sortant",
        "instant transfer": "Virement instantané",
        "virement instantané": "Virement instantané",
        "online purchase": "Achat en ligne",
        "internet purchase": "Achat en ligne",
        "card not present": "Carte non présente",
        "carte non présente": "Carte non présente",
        "bancontact": "Bancontact",
        "maestro": "Maestro",
        "payment card": "Carte de paiement",
        "carte de paiement": "Carte de paiement",
    }

    translated_rows = []
    for row in rows:
        new_row = {}
        for key, value in row.items():
            target_key = key_mapping.get(str(key), str(key))
            target_value = value
            if (
                resolved == "french"
                and str(key).lower() == "info"
                and value is not None
            ):
                normalized = str(value).strip()
                target_value = info_translations.get(normalized.lower(), normalized)
            new_row[target_key] = target_value
        translated_rows.append(new_row)
    return translated_rows, fieldnames


def write_csv(
    rows,
    output_path,
    fieldnames: Iterable[str] | None = None,
    delimiter=";",
    language: str | None = None,
):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_language = resolve_output_language(language)
    if fieldnames is None:
        fieldnames = OUTPUT_LANGUAGE_FIELDNAMES[resolved_language]
    translated_rows, fieldnames = translate_rows_for_output(rows, resolved_language)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(fieldnames), delimiter=delimiter
        )
        writer.writeheader()
        writer.writerows(translated_rows)
    return output_path


def display_conversion_stats(
    rows,
    input_file,
    output_file,
    title="CONVERSION",
    skipped_count: int = 0,
    language: str | None = None,
):
    """Print a readable CLI summary of the converted output.

    The layout is intentionally user-friendly and mirrors the dashboard-style
    report expected in the CLI workflow. It remains compatible with existing
    converter calls while allowing an optional skipped_count value for final
    completion messages.
    """
    if language is None:
        language = "french"

    # In windowed (GUI/frozen) mode sys.stdout is None — skip console output.
    if sys.stdout is None:
        return

    input_path = Path(input_file)
    output_path = Path(output_file)
    language = resolve_output_language(language)

    if language == "french":
        title_label = "STATISTIQUES DE CONVERSION"
        source_label = "📄 Fichier source"
        output_label = "📁 Fichier généré"
        operations_label = "🔢 Total opérations"
        net_label = "💰 Mouvement net total"
        detail_label = "Détail par type de paiement :"
        summary_suffix = "EUR"
        done_label = "✅ Conversion terminée."
        exported_label = "📥 {count} transaction(s) exportée(s)."
        skipped_label = "🚫 {count} règlement(s) ignoré(s)."
        saved_label = "💾 Sauvegardé dans : {path}"
        type_label = "Type"
    else:
        title_label = "CONVERSION STATISTICS"
        source_label = "📄 Source file"
        output_label = "📁 Generated file"
        operations_label = "🔢 Total operations"
        net_label = "💰 Net movement total"
        detail_label = "Payment breakdown:"
        summary_suffix = "EUR"
        done_label = "✅ Conversion complete."
        exported_label = "📥 {count} transaction(s) exported."
        skipped_label = "🚫 {count} skipped settlement(s)."
        saved_label = "💾 Saved to: {path}"
        type_label = "Type"

    def safe_amount(value):
        try:
            return float(str(value).replace(",", "."))
        except (TypeError, ValueError):
            return 0.0

    def safe_console_text(value: str) -> str:
        stdout = sys.stdout
        encoding = (getattr(stdout, "encoding", None) or "utf-8").lower()
        try:
            value.encode(encoding)
            return value
        except (LookupError, UnicodeEncodeError):
            return value.encode("ascii", errors="replace").decode("ascii")

    total_net = sum(safe_amount(r.get("amount")) for r in rows if r.get("amount"))
    stats_by_info: dict[tuple[str, str], dict[str, float | int]] = {}
    for r in rows:
        key = (r.get("payment", ""), r.get("info", ""))
        amt = safe_amount(r.get("amount"))
        stats_by_info.setdefault(key, {"count": 0, "sum": 0.0})
        stats_by_info[key]["count"] += 1
        stats_by_info[key]["sum"] += amt

    border = "=" * 60
    print()
    print(safe_console_text(border))
    print(safe_console_text(f"📊 {title_label} {title}"))
    print(safe_console_text(border))
    print(safe_console_text(f"{source_label:<22} : {input_path.name}"))
    print(safe_console_text(f"{output_label:<22} : {output_path.name}"))
    print(safe_console_text(f"{operations_label:<22} : {len(rows)}"))
    print(safe_console_text(f"{net_label:<22} : {total_net:.2f} {summary_suffix}"))
    print()

    if stats_by_info:
        print(safe_console_text(detail_label))
        for (p_code, p_info), data in stats_by_info.items():
            payment_name = p_info or "-"
            spacing = " " * max(0, 22 - len(payment_name))
            print(
                safe_console_text(
                    f"  • {type_label} {p_code:<2}  ({payment_name}{spacing}) : "
                    f"{data['count']} transaction(s) [Total: {data['sum']:.2f} {summary_suffix}]"
                )
            )
    print(safe_console_text(border))
    print()
    print(safe_console_text(done_label))
    print(safe_console_text(f"   {exported_label.format(count=len(rows))}"))
    print(safe_console_text(f"   {skipped_label.format(count=skipped_count)}"))
    print(safe_console_text(f"   {saved_label.format(path=output_path)}"))
    print()

    logger.info("%s", border)
    logger.info("%s %s", title_label, title)
    logger.info("%s", border)
    logger.info("%s : %s", source_label.replace("📄 ", ""), input_path.name)
    logger.info("%s : %s", output_label.replace("📁 ", ""), output_path.name)
    logger.info("%s : %d", operations_label.replace("🔢 ", ""), len(rows))
    logger.info("%s : %.2f %s", net_label.replace("💰 ", ""), total_net, summary_suffix)


def generate_conversion_statistics(
    rows: list[dict[str, str]],
    input_path: Path,
    output_path: Path,
    title: str = "CONVERSION",
    skipped_count: int = 0,
    warnings: list[str] | None = None,
) -> "stats_module.ConversionStatistics":
    """
    Generate structured statistics from converted transactions.

    This function generates a ConversionStatistics object containing detailed
    breakdown of converted transactions by payment type, totals, and optional
    warnings. It's designed to work with data already converted to HomeBank format.

    Args:
        rows: List of transaction dictionaries with 'amount', 'payment', 'info' fields.
        input_path: Path to the original input file.
        output_path: Path to the generated output CSV file.
        title: Converter name or title (e.g., 'KEYTRADE', 'AMEX').
        skipped_count: Number of rows that were skipped during conversion.
        warnings: Optional list of conversion warnings or issues encountered.

    Returns:
        ConversionStatistics object with complete breakdown and metadata.

    Note:
        This function uses the 'from' pattern: it delegates to create_statistics()
        in the statistics module for the actual calculations and returns a structured
        result that can be persisted to disk.
    """
    try:
        from . import statistics as stats_module
    except ImportError:
        from scripts.converters import statistics as stats_module

    return stats_module.create_statistics(
        rows=rows,
        input_file_name=input_path.name,
        output_file_name=output_path.name,
        converter_name=title.lower(),
        skipped_count=skipped_count,
        warnings=warnings,
    )


@overload
def save_statistics_report(
    stats: "stats_module.ConversionStatistics",
    output_csv_path: Path,
    format: Literal["json"],
) -> Path: ...


@overload
def save_statistics_report(
    stats: "stats_module.ConversionStatistics",
    output_csv_path: Path,
    format: Literal["txt"],
) -> Path: ...


@overload
def save_statistics_report(
    stats: "stats_module.ConversionStatistics",
    output_csv_path: Path,
    format: Literal["both"] = "both",
) -> tuple[Path, Path]: ...


def save_statistics_report(
    stats: "stats_module.ConversionStatistics",
    output_csv_path: Path,
    format: str = "both",
) -> Path | tuple[Path, Path]:
    """
    Save statistics report to file(s) beside the output CSV.

    Generates either JSON, text, or both formats of the statistics report
    and saves them alongside the output CSV file. Files are named with
    '_report' suffix (e.g., HB_statement_report.json, HB_statement_report.txt).

    Args:
        stats: ConversionStatistics object to serialize.
        output_csv_path: Path to the generated CSV output file.
        format: Output format - 'json', 'txt', or 'both' (default: 'both').

    Returns:
        Path to single report file, or tuple of (json_path, txt_path) if format='both'.

    Raises:
        ValueError: If format is not one of 'json', 'txt', or 'both'.
        IOError: If unable to write files to disk.

    Example:
        >>> stats = generate_conversion_statistics(rows, Path("input.csv"), Path("HB_output.csv"))
        >>> json_report, txt_report = save_statistics_report(stats, Path("HB_output.csv"), format="both")
        >>> logger.info("Reports saved to %s and %s", json_report, txt_report)
    """
    if format not in ("json", "txt", "both"):
        raise ValueError(f"format must be 'json', 'txt', or 'both', got {format!r}")

    output_csv_path = Path(output_csv_path)
    base_path = output_csv_path.with_suffix("")  # Remove .csv extension

    json_path = None
    txt_path = None

    if format in ("json", "both"):
        json_path = base_path.with_stem(f"{base_path.stem}_report").with_suffix(".json")
        try:
            stats.save_to_file(json_path, mode="w")
            logger.info("Statistics JSON report saved: %s", json_path)
        except Exception:
            logger.exception("Failed to save JSON statistics report to %s", json_path)
            raise

    if format in ("txt", "both"):
        txt_path = base_path.with_stem(f"{base_path.stem}_report").with_suffix(".txt")
        try:
            stats.save_text_to_file(txt_path, mode="w")
            logger.info("Statistics text report saved: %s", txt_path)
        except Exception:
            logger.exception("Failed to save text statistics report to %s", txt_path)
            raise

    # Return appropriately based on format
    if format == "both":
        assert json_path is not None and txt_path is not None
        return (json_path, txt_path)
    elif format == "json":
        assert json_path is not None
        return json_path
    else:  # format == "txt"
        assert txt_path is not None
        return txt_path
