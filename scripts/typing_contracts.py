from __future__ import annotations

from pathlib import Path
from typing import Callable, Literal, TypeAlias

PathLike: TypeAlias = str | Path

ConverterName: TypeAlias = Literal["keytrade", "amex", "argenta", "mastercard"]
ConverterModuleName: TypeAlias = Literal[
    "keytrade_csv",
    "amex_csv",
    "amex_xlsx",
    "argenta_xlsx",
    "mastercard_pdf",
]
ConversionStatus: TypeAlias = Literal["OK", "FAILED", "SKIPPED"]

DetectionPair: TypeAlias = tuple[ConverterName | None, ConverterModuleName | None]
ConvertResultPath: TypeAlias = Path | None
ConverterHandler: TypeAlias = Callable[
    [PathLike, PathLike | None, PathLike | None],
    ConvertResultPath,
]
