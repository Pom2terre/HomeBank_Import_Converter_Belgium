#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module de conversion American Express (AMEX) XLSX vers HomeBank CSV
==================================================================
"""

import logging
import sys
from pathlib import Path

import pandas as pd

try:
    from scripts.typing_contracts import PathLike
except ImportError:
    from typing_contracts import PathLike

from . import HOME_BANK_PAYMENT_CODES
from .utils import (
    display_conversion_stats,
    find_column,
    find_header_row,
    generate_conversion_statistics,
    guess_column,
    parse_date,
    parse_float,
    save_statistics_report,
    write_csv,
)

PAYMENT_CODE_CREDIT_CARD = HOME_BANK_PAYMENT_CODES["credit_card"]
PAYMENT_INFO_CREDIT_CARD = "credit card"
logger = logging.getLogger(__name__)


def convert(
    source: PathLike, output: PathLike | None = None, rules_path: PathLike | None = None
) -> Path | None:
    del rules_path  # AMEX XLSX currently does not use payment rules.
    source_path = Path(source)
    if output is None:
        output = source_path.with_name(f"HB_Amex_ {source_path.name}").with_suffix(
            ".csv"
        )
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with pd.ExcelFile(source_path, engine="openpyxl") as excel_file:
            sheets = excel_file.sheet_names
            frames = []
            for sheet in sheets:
                try:
                    frame = excel_file.parse(sheet, header=None)
                except Exception:
                    continue
                if frame.empty:
                    continue
                frames.append(frame)
            if frames:
                raw_df = pd.concat(frames, ignore_index=True)
            else:
                raw_df = pd.DataFrame()
    except Exception as exc:
        logger.error("Impossible de lire le fichier XLSX AMEX %s: %s", source_path, exc)
        return None

    if raw_df.empty:
        write_csv([], output_path)
        logger.warning(
            "Fichier XLSX AMEX vide ou sans ligne exploitable : %s", source_path
        )
        return output_path

    header_row = find_header_row(raw_df)
    if header_row is not None:
        df = raw_df.iloc[header_row + 1 :].copy()
        if df.empty:
            df = raw_df.copy()
        columns = [str(value).strip() for value in raw_df.iloc[header_row].fillna("")]
        df.columns = columns
    else:
        df = raw_df.copy()
        df.columns = [str(c).strip() for c in df.columns]

    columns = list(df.columns)
    date_col = find_column(
        columns,
        [
            "date",
            "date opération",
            "date operation",
            "date valeur",
            "date comptable",
            "date transaction",
        ],
    )
    description_col = find_column(
        columns,
        [
            "libellé",
            "description",
            "opération",
            "intitulé",
            "transaction",
            "motif",
            "designation",
        ],
    )
    amount_col = find_column(
        columns, ["montant", "amount", "valeur", "débit", "credit", "crédit", "somme"]
    )
    reference_col = find_column(
        columns, ["référence", "reference", "ref", "réf", "numéro", "numero"]
    )
    memo_col = find_column(
        columns, ["memo", "mémos", "communication", "details", "détails", "notes"]
    )
    payee_col = find_column(
        columns,
        ["beneficiaire", "bénéficiaire", "payee", "titulaire", "nom du bénéficiaire"],
    )

    if date_col is None:
        date_col = guess_column(columns, df, "date")
    if amount_col is None:
        amount_col = guess_column(columns, df, "amount")
    if description_col is None:
        description_col = guess_column(columns, df, "text")
    if payee_col is None:
        payee_col = guess_column(columns, df, "text")

    rows = []
    for _, record in df.iterrows():
        date_val = record[date_col] if date_col else None
        description = (
            str(record[description_col]).strip()
            if description_col and pd.notna(record[description_col])
            else ""
        )
        montant = parse_float(record[amount_col]) if amount_col else None

        if not description and not pd.notna(date_val):
            continue

        if description and "règlement enregistré - merci" in description.lower():
            continue

        date_obj = parse_date(date_val)
        if date_obj is None or montant is None:
            continue

        memo = (
            str(record[memo_col]).strip()
            if memo_col and pd.notna(record[memo_col])
            else ""
        )
        payee = (
            str(record[payee_col]).strip()
            if payee_col and pd.notna(record[payee_col])
            else description
        )
        reference = (
            str(record[reference_col]).strip()
            if reference_col and pd.notna(record[reference_col])
            else ""
        )

        if montant > 0:
            amount_value = -montant
        else:
            amount_value = abs(montant)

        rows.append(
            {
                "date": date_obj.strftime("%d-%m-%y"),
                "payment": PAYMENT_CODE_CREDIT_CARD,
                "info": PAYMENT_INFO_CREDIT_CARD,
                "payee": payee,
                "memo": memo,
                "amount": f"{amount_value:.2f}".replace(".", ","),
                "category": "",
                "tags": reference,
            }
        )

    write_csv(rows, output_path)
    display_conversion_stats(rows, source_path, output_path, title="AMEX")
    logger.info("Conversion AMEX XLSX terminee (%d transactions)", len(rows))
    logger.info("Sauvegarde dans: %s", output_path)

    # Generate and save statistics report
    try:
        stats = generate_conversion_statistics(
            rows=rows,
            input_path=source_path,
            output_path=output_path,
            title="AMEX",
        )
        save_statistics_report(stats, output_path, format="both")
    except Exception as exc:
        logger.warning("Failed to generate statistics report: %s", exc)

    return output_path


if __name__ == "__main__":
    import pandas as pd

    if len(sys.argv) > 1:
        convert(sys.argv[1])
