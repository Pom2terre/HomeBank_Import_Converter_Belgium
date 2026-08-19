#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Detection service for identifying converter modules from input files."""

from __future__ import annotations

import re
import zipfile
import zlib
from pathlib import Path

from scripts.converters.utils import get_localized_text
from scripts.services.logging_service import get_logger
from scripts.typing_contracts import DetectionPair

logger = get_logger(__name__)

HOME_BANK_CSV_PREFIXES = ("hb_", "homebank_")
AMEX_XLSX_MARKER = "xxxx-xxxxxx-13003"
KEYTRADE_IBAN_MARKER = "be10000000000000"
ARGENTA_IBAN_MARKER = "be10 0000 0000 0000"
MASTERCARD_REFERENCE_MARKERS = (
    "référence client 6208192499",
    "reference client 6208192499",
)
RAW_PDF_REFERENCE_MARKER = b"reference client 6208192499"
STREAM_REGEX = re.compile(rb"stream\r?\n(.*?)\r?\nendstream", re.S)
PDF_LITERAL_REGEX = re.compile(rb"\((?:\\.|[^\\])*?\)", re.S)


def read_text_content(path: Path) -> str:
    try:
        raw = path.read_bytes()
        return raw.decode("utf-8", errors="ignore")
    except Exception:
        try:
            with path.open("rb") as f:
                return f.read().decode("latin-1", errors="ignore")
        except Exception:
            logger.debug("Unable to decode text content for %s", path)
            return ""


def read_xlsx_content(path: Path) -> str:
    try:
        with zipfile.ZipFile(path, "r") as zf:
            pieces: list[str] = []
            names = zf.namelist()
            priority_names = [
                "xl/sharedStrings.xml",
                "xl/workbook.xml",
            ]
            worksheet_names = [
                n
                for n in names
                if n.startswith("xl/worksheets/") and n.endswith(".xml")
            ]
            candidate_names = [
                n for n in priority_names if n in names
            ] + worksheet_names

            for name in candidate_names:
                try:
                    text = zf.read(name).decode("utf-8", errors="ignore")
                except Exception:
                    continue
                pieces.append(text)

                lowered = text.lower()
                if (
                    KEYTRADE_IBAN_MARKER in lowered
                    or AMEX_XLSX_MARKER in lowered
                    or ARGENTA_IBAN_MARKER in lowered
                    or "compte" in lowered
                ):
                    return "\n".join(pieces)
            return "\n".join(pieces)
    except Exception:
        logger.debug("Unable to read xlsx content for %s", path)
        return ""


def read_pdf_content(path: Path) -> str:
    raw = path.read_bytes()
    try:
        return raw.decode("utf-8", errors="ignore")
    except Exception:
        return raw.decode("latin-1", errors="ignore")


def decode_pdf_literal_string(data: bytes) -> str:
    result = []
    i = 0
    while i < len(data):
        b = data[i]
        if b == 92:  # backslash
            i += 1
            if i >= len(data):
                break
            c = data[i]
            if c == 110:
                result.append("\n")
            elif c == 114:
                result.append("\r")
            elif c == 116:
                result.append("\t")
            elif c == 98:
                result.append("\b")
            elif c == 102:
                result.append("\f")
            elif c in (92, 40, 41):
                result.append(chr(c))
            elif 48 <= c <= 55:
                octal = bytes([c])
                j = i + 1
                while j < len(data) and len(octal) < 3 and 48 <= data[j] <= 55:
                    octal += bytes([data[j]])
                    j += 1
                try:
                    result.append(chr(int(octal, 8)))
                except Exception:
                    pass
                i = j - 1
            else:
                result.append(chr(c))
        else:
            result.append(chr(b))
        i += 1
    return "".join(result)


def extract_pdf_text(path: Path, raw: bytes | None = None) -> str:
    raw = raw if raw is not None else path.read_bytes()
    text = raw.decode("latin-1", errors="ignore")
    lower = text.lower()
    if "reference client" in lower or "référence client" in lower:
        return text

    pieces = [text]
    for stream_match in STREAM_REGEX.finditer(raw):
        stream = stream_match.group(1)
        try:
            decoded = zlib.decompress(stream)
            decoded_text = decoded.decode("latin-1", errors="ignore")
            pieces.append(decoded_text)
            pieces.append(decoded_text.lower())
            for text_match in PDF_LITERAL_REGEX.finditer(decoded):
                inner = text_match.group(0)[1:-1]
                pieces.append(decode_pdf_literal_string(inner))
        except Exception:
            pass

    for chunk in PDF_LITERAL_REGEX.finditer(raw):
        inner = chunk.group(0)[1:-1]
        pieces.append(decode_pdf_literal_string(inner))

    return "\n".join(pieces)


def detect_converter(path: Path) -> DetectionPair:
    try:
        path = Path(path)
    except Exception:
        logger.debug("Invalid path supplied for detection: %r", path)
        return None, None

    try:
        if not path.exists() or not path.is_file() or path.stat().st_size <= 0:
            logger.debug("Skipping detection for empty or missing file: %s", path)
            return None, None
    except OSError:
        logger.debug("Unable to stat file for detection: %s", path)
        return None, None

    name = path.name.lower()
    ext = path.suffix.lower()

    if ext == ".csv" and name.startswith(HOME_BANK_CSV_PREFIXES):
        logger.debug("Ignoring already-converted HomeBank CSV: %s", path)
        return None, None

    raw_pdf_lower = None
    try:
        if ext == ".xlsx":
            if not zipfile.is_zipfile(path):
                logger.debug("Skipping malformed XLSX file: %s", path)
                return None, None
            txt = read_xlsx_content(path).lower()
        elif ext == ".pdf":
            raw_pdf = path.read_bytes()
            if len(raw_pdf) < 4 or b"%pdf" not in raw_pdf[:1024].lower():
                logger.debug("Skipping malformed PDF file: %s", path)
                return None, None
            raw_pdf_lower = raw_pdf.lower()
            if RAW_PDF_REFERENCE_MARKER in raw_pdf_lower:
                logger.debug(
                    "Detected Mastercard converter from raw PDF bytes for %s", path
                )
                return "mastercard", "mastercard_pdf"
            txt = extract_pdf_text(path, raw_pdf).lower()
        else:
            txt = read_text_content(path).lower()
    except OSError:
        logger.debug("Unable to read file for detection: %s", path)
        return None, None
    except Exception:
        logger.debug("Unexpected error while reading file for detection: %s", path)
        return None, None

    if not txt.strip():
        logger.debug("Skipping detection for file with no readable content: %s", path)
        return None, None

    if KEYTRADE_IBAN_MARKER in txt:
        logger.debug("Detected keytrade converter for %s", path)
        return "keytrade", "keytrade_csv"

    if AMEX_XLSX_MARKER in txt:
        logger.debug("Detected AMEX converter for %s", path)
        return ("amex", "amex_xlsx") if ext == ".xlsx" else ("amex", "amex_csv")

    if ext == ".csv":
        if re.search(r"^date[;,]description[;,]montant", txt, re.M):
            logger.debug("Detected AMEX CSV by header for %s", path)
            return "amex", "amex_csv"
        if "règlement enregistré" in txt or "5 cents bonus" in txt:
            logger.debug("Detected AMEX CSV by textual marker for %s", path)
            return "amex", "amex_csv"

    if ARGENTA_IBAN_MARKER in txt and "compte" in txt:
        logger.debug("Detected Argenta converter for %s", path)
        return "argenta", "argenta_xlsx"

    if any(marker in txt for marker in MASTERCARD_REFERENCE_MARKERS):
        logger.debug("Detected Mastercard converter for %s", path)
        return "mastercard", "mastercard_pdf"

    logger.debug(get_localized_text("service_no_converter_detected", file=path))
    return None, None


class DetectionService:
    """Service wrapper around converter detection helpers."""

    def detect(self, file_path: Path) -> DetectionPair:
        return detect_converter(file_path)

    def extract_pdf_text(self, file_path: Path) -> str:
        return extract_pdf_text(file_path)
