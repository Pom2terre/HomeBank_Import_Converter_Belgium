#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module de conversion Argenta XLSX vers HomeBank CSV
===================================================
"""

import logging
import sys
from pathlib import Path

import pandas as pd

try:
    from scripts.typing_contracts import PathLike
except ImportError:
    from typing_contracts import PathLike

try:
    from . import determine_payment_mode, load_payment_rules
    from .utils import (
        display_conversion_stats,
        find_column,
        folded,
        generate_conversion_statistics,
        parse_date,
        parse_decimal,
        save_statistics_report,
        write_csv,
    )
except ImportError:
    try:
        from converters import determine_payment_mode, load_payment_rules
        from converters.utils import (
            display_conversion_stats,
            find_column,
            folded,
            generate_conversion_statistics,
            parse_date,
            parse_decimal,
            save_statistics_report,
            write_csv,
        )
    except ImportError:
        from scripts.converters import determine_payment_mode, load_payment_rules
        from scripts.converters.utils import (
            display_conversion_stats,
            find_column,
            folded,
            generate_conversion_statistics,
            parse_date,
            parse_decimal,
            save_statistics_report,
            write_csv,
        )

import config

logger = logging.getLogger(__name__)


def convertir(
    source: PathLike, output: PathLike | None = None, rules_path: PathLike | None = None
) -> Path:
    """Convertit un fichier XLSX Argenta au format CSV HomeBank."""
    source = Path(source)
    out_dir = Path(getattr(config, "DOSSIER_SORTIE_ARGENTA", "."))

    if output is None:
        output_path = out_dir / f"HB_{source.stem}.csv"
    else:
        output_path = Path(output)
        if not output_path.suffix:
            output_path = output_path.with_suffix(".csv")

    try:
        df = pd.read_excel(source, sheet_name="Transactions")
    except Exception:
        df = pd.read_excel(source)

    date_col = next(
        (
            c
            for c in df.columns
            if folded(c) in ["date comptable", "date valeur", "date"]
        ),
        None,
    )
    amount_col = next(
        (c for c in df.columns if folded(c) in ["montant", "amount"]), None
    )
    description_col = next(
        (
            c
            for c in df.columns
            if folded(c) in ["description", "transaction type", "type"]
        ),
        None,
    )
    payee_col = next(
        (
            c
            for c in df.columns
            if folded(c) in ["nom de la contrepartie", "counterparty name", "payee"]
        ),
        None,
    )
    communication_col = next(
        (c for c in df.columns if folded(c) in ["communication", "details", "memo"]),
        None,
    )
    reference_col = find_column(
        df.columns, ["référence", "reference", "réf", "ref", "numéro", "numero"]
    )

    rows = []
    payment_rules = load_payment_rules(rules_path)

    for _, record in df.iterrows():
        dt = parse_date(record[date_col]) if date_col else None
        amount = parse_decimal(record[amount_col]) if amount_col else None
        if dt is None or amount is None:
            continue

        description = (
            str(record[description_col]).strip()
            if description_col and pd.notna(record[description_col])
            else ""
        )
        payee = (
            str(record[payee_col]).strip()
            if payee_col and pd.notna(record[payee_col])
            else ""
        )
        communication = (
            str(record[communication_col]).strip()
            if communication_col and pd.notna(record[communication_col])
            else ""
        )
        tags = (
            str(record[reference_col]).strip()
            if reference_col and pd.notna(record[reference_col])
            else ""
        )

        best_description = description or payee or communication
        payment_code, info = determine_payment_mode(
            best_description, float(amount), payment_rules
        )

        # Traitement spécial du mémo pour Argenta
        memo = "Nihil" if "|" in communication else communication

        rows.append(
            {
                "date": dt.strftime("%d/%m/%Y"),
                "payment": payment_code,
                "info": info,
                "payee": payee,
                "memo": memo,
                "amount": f"{amount:.2f}".replace(".", ","),
                "category": "",
                "tags": tags,
            }
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_csv(rows, output_path)
    display_conversion_stats(rows, source, output_path, title="ARGENTA")

    # Generate and save statistics report
    try:
        stats = generate_conversion_statistics(
            rows=rows,
            input_path=source,
            output_path=output_path,
            title="ARGENTA",
        )
        save_statistics_report(stats, output_path, format="both")
    except Exception as exc:
        logger.warning("Failed to generate statistics report: %s", exc)

    return output_path


# Aliases pour la compatibilité
convert_argenta = convertir
convert = convertir


if __name__ == "__main__":
    if len(sys.argv) > 1:
        src = sys.argv[1]
        convertir(src)
