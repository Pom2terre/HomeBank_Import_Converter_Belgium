#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module de conversion Keytrade Bank CSV vers HomeBank CSV
=========================================================
"""

import csv
import logging
import sys
from pathlib import Path

try:
    from scripts.typing_contracts import PathLike
except ImportError:
    from typing_contracts import PathLike

try:
    from . import determine_payment_mode, load_payment_rules
    from .utils import (
        display_conversion_stats,
        generate_conversion_statistics,
        parse_date,
        parse_float,
        save_statistics_report,
        write_csv,
    )
except ImportError:
    try:
        from converters import determine_payment_mode, load_payment_rules
        from converters.utils import (
            display_conversion_stats,
            generate_conversion_statistics,
            parse_date,
            parse_float,
            save_statistics_report,
            write_csv,
        )
    except ImportError:
        from scripts.converters import determine_payment_mode, load_payment_rules
        from scripts.converters.utils import (
            display_conversion_stats,
            generate_conversion_statistics,
            parse_date,
            parse_float,
            save_statistics_report,
            write_csv,
        )

import config

logger = logging.getLogger(__name__)


def extract_payee(description: str) -> str:
    """Extrait le nom du tiers/payeur depuis la description Keytrade."""
    if not description:
        return ""
    parts = description.split()
    payee_parts = []
    for part in parts:
        if part.startswith("BE") and len(part) == 16 and part[2:].isdigit():
            break
        if part.upper() in [
            "PERMANENT",
            "ORDER",
            "INTERNAL",
            "TRANSFER",
            "KEYPLAN",
            "5",
            "CENTS",
        ]:
            break
        payee_parts.append(part)
    payee = " ".join(payee_parts).strip()
    return payee if payee else description[:30].strip()


def convert_keytrade_csv(
    input_csv: PathLike, output_csv: PathLike, rules_path: PathLike | None = None
) -> list[dict[str, str]]:
    """Lit le fichier CSV Keytrade et génère le fichier CSV compatible HomeBank."""
    input_path = Path(input_csv)
    output_path = Path(output_csv)

    if not input_path.exists():
        logger.error("Fichier introuvable: %s", input_path)
        return []

    rules_data = load_payment_rules(rules_path)

    content = None
    for enc in ["utf-8-sig", "cp1252", "latin-1"]:
        try:
            with open(input_path, "r", encoding=enc) as f:
                content = f.readlines()
            break
        except UnicodeDecodeError:
            continue

    if not content:
        logger.error(
            "Impossible de lire le fichier CSV (probleme d'encodage): %s", input_path
        )
        return []

    sample_line = next((line for line in content if ";" in line or "," in line), "")
    delimiter = ";" if ";" in sample_line else ","

    reader = csv.DictReader(content, delimiter=delimiter)
    rows_to_write = []

    for row in reader:
        cleaned_row = {k.strip(): v.strip() if v else "" for k, v in row.items() if k}
        date_str = cleaned_row.get("Date", "")
        if not date_str or date_str.lower() in ["date", "extrait"]:
            continue

        dt = parse_date(date_str)
        formatted_date = dt.strftime("%d/%m/%Y") if dt else date_str

        description = cleaned_row.get("Description", "")
        amount_raw = cleaned_row.get("Montant", "0")
        num_amount = parse_float(amount_raw) or 0.0
        tags_value = cleaned_row.get("Extrait", cleaned_row.get("extrait", ""))

        payment_code, info_str = determine_payment_mode(
            description, num_amount, rules_data
        )
        payee = extract_payee(description)

        rows_to_write.append(
            {
                "date": formatted_date,
                "payment": str(payment_code),
                "info": info_str,
                "payee": payee,
                "memo": description,
                "amount": f"{num_amount:.2f}".replace(".", ","),
                "category": "",
                "tags": tags_value,
            }
        )

    write_csv(rows_to_write, output_path)
    display_conversion_stats(rows_to_write, input_path, output_path, title="KEYTRADE")

    # Generate and save statistics report
    try:
        stats = generate_conversion_statistics(
            rows=rows_to_write,
            input_path=input_path,
            output_path=output_path,
            title="KEYTRADE",
        )
        save_statistics_report(stats, output_path, format="both")
    except Exception as exc:
        logger.warning("Failed to generate statistics report: %s", exc)

    return rows_to_write


def convert(
    source: PathLike, output: PathLike | None = None, rules_path: PathLike | None = None
) -> Path:
    """Unified converter contract: convert(source, output=None, rules_path=None) -> Path."""
    source_path = Path(source)
    if output is None:
        out_dir = Path(
            getattr(
                config,
                "DOSSIER_SORTIE_KEYTRADE",
                r"C:\Users\username\Downloads\Import_Keytrade",
            )
        )
        output_path = out_dir / f"HB_{source_path.stem}.csv"
    else:
        output_path = Path(output)
        if not output_path.suffix:
            output_path = output_path.with_suffix(".csv")

    resolved_rules = rules_path or Path(
        getattr(config, "PAYMENT_RULES", "payment_rules.json")
    )
    convert_keytrade_csv(source_path, output_path, resolved_rules)
    return output_path


# Aliases pour la compatibilité
convert_keytrade = convert_keytrade_csv
convertir = convert_keytrade_csv


if __name__ == "__main__":
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("Transactions.csv")
    out_dir = Path(
        getattr(
            config,
            "DOSSIER_SORTIE_KEYTRADE",
            r"C:\Users\username\Downloads\Import_Keytrade",
        )
    )
    dst = out_dir / "HB_Transactions.csv"
    rules = Path(getattr(config, "PAYMENT_RULES", "payment_rules.json"))

    convert_keytrade_csv(src, dst, rules)
