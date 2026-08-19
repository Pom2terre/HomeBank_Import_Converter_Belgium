#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module de conversion Mastercard PDF vers HomeBank CSV
====================================================
"""

import logging
import re
import sys
from datetime import datetime
from pathlib import Path

try:
    from scripts.typing_contracts import PathLike
except ImportError:
    from typing_contracts import PathLike

try:
    import PyPDF2
except ImportError:
    PyPDF2 = None

from . import HOME_BANK_PAYMENT_CODES
from .utils import (
    display_conversion_stats,
    generate_conversion_statistics,
    parse_float,
    save_statistics_report,
    write_csv,
)

logger = logging.getLogger(__name__)

FIELDS = ["date", "payment", "info", "payee", "memo", "amount", "category", "tags"]
PAYMENT_CODE_CREDIT_CARD = HOME_BANK_PAYMENT_CODES["credit_card"]
PAYMENT_INFO_CREDIT_CARD = "credit card"
CARD_INFO_PATTERN = re.compile(r"Num\.car(?:te|d)?\s*[:\-]?\s*([0-9X\- ]{10,30})", re.I)
PERIOD_PATTERN = re.compile(
    r"Transactions du\s*(\d{1,2}/\d{1,2}/\d{4})\s*au\s*(\d{1,2}/\d{1,2}/\d{4})", re.I
)
TRANSACTION_LINE_PATTERN = re.compile(
    r"^(?P<date>\d{1,2}/\d{1,2}(?:/\d{2,4})?)\s+"
    r"(?P<posting>\d{1,2}/\d{1,2}(?:/\d{2,4})?)\s+"
    r"(?P<description>.+?)\s+"
    r"(?P<amount>[0-9]+(?:[\.,][0-9]{1,2})?)\s*(?P<sign>[+-])?$"
)
IGNORE_PHRASES = [
    "solde précédent au",
    "domiciliation aupres de votre banque",
    "nouveau solde",
    "paiement effectué par votre organisme financier",
    "attention!",
    "date",
    "transactiondate",
    "comptabilisationdescription",
    "montant (eur)",
]


def extract_pdf_text(source_path: Path) -> str:
    if PyPDF2 is None:
        raise ImportError("PyPDF2 is requis pour extraire le texte du PDF Mastercard.")

    text_parts = []
    with source_path.open("rb") as pdf_file:
        reader = PyPDF2.PdfReader(pdf_file)
        for page in reader.pages:
            page_text = page.extract_text() or ""
            text_parts.append(page_text)

    return "\n".join(text_parts)


def normalize_lines(raw_text: str) -> list[str]:
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    normalized = []
    for line in lines:
        if any(phrase in line.lower() for phrase in IGNORE_PHRASES):
            continue
        if line.lower().startswith("référence client"):
            continue
        if line.lower().startswith("limite d'utilisation"):
            continue
        normalized.append(line)
    return normalized


def parse_statement_period(lines: list[str]) -> tuple[datetime | None, datetime | None]:
    for line in lines:
        match = PERIOD_PATTERN.search(line)
        if match:
            try:
                start = datetime.strptime(match.group(1), "%d/%m/%Y")
                end = datetime.strptime(match.group(2), "%d/%m/%Y")
                return start, end
            except ValueError:
                continue
    return None, None


def infer_year(
    date_str: str, period_start: datetime | None, period_end: datetime | None
) -> datetime | None:
    try:
        if date_str.count("/") == 1:
            day, month = [int(x) for x in date_str.split("/")]
            if period_start and period_end:
                if month == period_start.month:
                    year = period_start.year
                elif month == period_end.month:
                    year = period_end.year
                elif period_start.year != period_end.year and month <= period_end.month:
                    year = period_end.year
                else:
                    year = period_start.year
            else:
                year = datetime.now().year
            return datetime(year, month, day)
        return datetime.strptime(date_str, "%d/%m/%Y")
    except ValueError:
        try:
            return datetime.strptime(date_str, "%m/%d/%Y")
        except ValueError:
            return None


def parse_amount(value: str, sign: str | None) -> float | None:
    if value is None:
        return None

    raw = value.replace(" ", "").replace("€", "").replace("EUR", "").replace(",", ".")
    try:
        amount = float(raw)
    except ValueError:
        return None

    if sign == "-":
        return -abs(amount)
    if sign == "+":
        return abs(amount)
    return -abs(amount) if amount >= 0 else amount


def convert(
    source: PathLike, output: PathLike | None = None, rules_path: PathLike | None = None
) -> Path:
    del rules_path  # Mastercard converter currently does not use payment rules.
    source_path = Path(source)
    if output is None:
        output = source_path.with_name(f"HB_Mastercard_{source_path.stem}").with_suffix(
            ".csv"
        )
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    raw_text = extract_pdf_text(source_path)
    lines = normalize_lines(raw_text)
    period_start, period_end = parse_statement_period(lines)

    card_info = ""
    for line in lines:
        match = CARD_INFO_PATTERN.search(line)
        if match:
            card_info = match.group(1).strip()
            break

    rows = []

    for line in lines:
        match = TRANSACTION_LINE_PATTERN.match(line)
        if not match:
            continue

        date_token = match.group("date")
        description = match.group("description").strip()
        amount_token = match.group("amount")
        sign_token = match.group("sign")

        date_obj = infer_year(date_token, period_start, period_end)
        if date_obj is None or not description:
            continue

        raw_amount = parse_float(amount_token)
        if raw_amount is None:
            continue
        num_amount = -abs(raw_amount) if sign_token == "-" else abs(raw_amount)

        payee = description

        rows.append(
            {
                "date": date_obj.strftime("%d-%m-%Y"),
                "payment": PAYMENT_CODE_CREDIT_CARD,
                "info": PAYMENT_INFO_CREDIT_CARD,
                "payee": payee,
                "memo": card_info,
                "amount": f"{num_amount:.2f}",
                "category": "",
                "tags": "",
            }
        )

    write_csv(rows, output_path)
    display_conversion_stats(rows, source_path, output_path, title="MASTERCARD")
    logger.info("Conversion MASTERCARD PDF terminee (%d transactions)", len(rows))
    logger.info("Sauvegarde dans: %s", output_path)

    # Generate and save statistics report
    try:
        stats = generate_conversion_statistics(
            rows=rows,
            input_path=source_path,
            output_path=output_path,
            title="MASTERCARD",
        )
        save_statistics_report(stats, output_path, format="both")
    except Exception as exc:
        logger.warning("Failed to generate statistics report: %s", exc)

    return output_path


if __name__ == "__main__":
    if len(sys.argv) > 1:
        convert(sys.argv[1])
