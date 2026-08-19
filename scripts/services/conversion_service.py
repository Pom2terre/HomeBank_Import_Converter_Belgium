from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    from scripts.converters.statistics import ConversionStatistics

from scripts import config
from scripts.converters import (
    amex_csv,
    amex_xlsx,
    argenta_xlsx,
    keytrade_csv,
    mastercard_pdf,
)
from scripts.converters.utils import get_localized_text
from scripts.services.detection_service import DetectionService
from scripts.services.logging_service import get_logger
from scripts.typing_contracts import (
    ConversionStatus,
    ConverterHandler,
    ConverterModuleName,
    ConverterName,
)

logger = get_logger(__name__)

OUTPUT_DIR_ATTRS: dict[ConverterName, str] = {
    "keytrade": "DOSSIER_SORTIE_KEYTRADE",
    "amex": "DOSSIER_SORTIE_AMEX",
    "argenta": "DOSSIER_SORTIE_ARGENTA",
    "mastercard": "DOSSIER_SORTIE_MASTERCARD",
}

CONVERTER_HANDLERS: dict[ConverterModuleName, ConverterHandler] = {
    "keytrade_csv": keytrade_csv.convert,
    "amex_csv": amex_csv.convert,
    "amex_xlsx": amex_xlsx.convert,
    "argenta_xlsx": argenta_xlsx.convert,
    "mastercard_pdf": mastercard_pdf.convert,
}


@dataclass
class DetectionResult:
    file_path: Path
    converter: ConverterName | None
    module_name: ConverterModuleName | None


@dataclass
class ConversionResult:
    """Result of a file conversion attempt, including optional statistics."""

    file_path: Path
    """Path to the input file that was converted."""

    converter: ConverterName | None
    """Detected converter name (e.g., 'keytrade', 'amex')."""

    module_name: ConverterModuleName | None
    """Converter module name (e.g., 'keytrade_csv', 'amex_xlsx')."""

    status: ConversionStatus
    """Conversion result: 'OK', 'FAILED', or 'SKIPPED'."""

    output_path: Path | None = None
    """Path to generated output CSV file (if status='OK')."""

    error: str | None = None
    """Error message if status='FAILED'."""

    report_path: Path | None = None
    """Path to statistics report file (JSON or TXT) if available."""

    statistics: ConversionStatistics | None = None
    """Loaded ConversionStatistics object if report was successfully parsed."""

    previous_statistics: ConversionStatistics | None = None
    """Summary from the previous execution trace for this converter, if available."""


class ConversionService:
    """Thin application service that can be called from CLI or a future GUI."""

    def __init__(self) -> None:
        self._module_handlers: dict[ConverterModuleName, ConverterHandler] = (
            CONVERTER_HANDLERS
        )
        self._detection_service = DetectionService()

    def detect(self, file_path: Path) -> DetectionResult:
        converter, module_name = self._detection_service.detect(file_path)
        logger.debug(
            "Detection result for %s -> converter=%s module=%s",
            file_path,
            converter,
            module_name,
        )
        return DetectionResult(
            file_path=file_path, converter=converter, module_name=module_name
        )

    def _output_dir(self, converter: ConverterName | None) -> Path | None:
        if converter is None:
            return None
        attr = OUTPUT_DIR_ATTRS.get(converter)
        if attr:
            return Path(getattr(config, attr, ""))
        return None

    def _validate_source_file(self, file_path: Path) -> None:
        if not file_path.exists() or not file_path.is_file():
            raise FileNotFoundError(f"Input file not found: {file_path}")

        try:
            size = file_path.stat().st_size
        except OSError as exc:
            raise ValueError(
                f"Unable to read input file metadata: {file_path}"
            ) from exc

        if size <= 0:
            raise ValueError(f"Input file is empty: {file_path}")

        suffix = file_path.suffix.lower()
        try:
            if suffix == ".xlsx":
                if not zipfile.is_zipfile(file_path):
                    raise ValueError(f"Malformed XLSX file: {file_path}")
            elif suffix == ".pdf":
                header = file_path.read_bytes()[:1024].lower()
                if b"%pdf" not in header:
                    raise ValueError(f"Malformed PDF file: {file_path}")
            elif suffix in {".csv", ".txt"}:
                with file_path.open("rb") as handle:
                    header = handle.read(4096)
                if not header.strip():
                    raise ValueError(f"Input file is empty: {file_path}")
        except (OSError, ValueError):
            raise
        except Exception as exc:  # pragma: no cover - defensive validation guard
            raise ValueError(f"Unable to validate input file: {file_path}") from exc

    def _build_output_path(
        self,
        file_path: Path,
        converter: ConverterName,
        module_name: ConverterModuleName,
    ) -> Path:
        out_dir = self._output_dir(converter)
        if out_dir:
            out_dir.mkdir(parents=True, exist_ok=True)
            if module_name == "amex_csv":
                return out_dir / f"HB_Amex_ {file_path.name}"
            return out_dir / f"HB_{file_path.stem}.csv"
        return file_path.with_name(f"HB_{file_path.stem}.csv")

    def _find_report_for_output(self, csv_path: Path) -> Path | None:
        """
        Look for a statistics report file next to the output CSV.

        Searches for both JSON and TXT formats with '_report' suffix.
        Returns the first one found (JSON takes precedence if both exist).

        Args:
            csv_path: Path to the output CSV file.

        Returns:
            Path to report file if found, otherwise None.
        """
        base_path = csv_path.with_suffix("")  # Remove .csv extension
        json_report = base_path.with_stem(f"{base_path.stem}_report").with_suffix(
            ".json"
        )
        txt_report = base_path.with_stem(f"{base_path.stem}_report").with_suffix(".txt")

        if json_report.exists():
            logger.debug("Found statistics report: %s", json_report)
            return json_report
        if txt_report.exists():
            logger.debug("Found statistics report: %s", txt_report)
            return txt_report
        return None

    def _load_statistics_from_report(
        self, report_path: Path
    ) -> ConversionStatistics | None:
        """
        Load statistics from a JSON report file.

        Args:
            report_path: Path to the statistics report file.

        Returns:
            ConversionStatistics object if JSON file is valid, otherwise None.
        """
        if report_path.suffix != ".json":
            logger.debug("Skipping non-JSON report: %s", report_path)
            return None

        try:
            from scripts.converters.statistics import ConversionStatistics

            with report_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            stats = ConversionStatistics.from_dict(data)
            logger.debug("Loaded statistics from %s", report_path)
            return stats
        except json.JSONDecodeError as exc:
            logger.warning(
                get_localized_text(
                    "service_invalid_report_json",
                    report=report_path,
                    error=exc,
                )
            )
        except Exception as exc:
            logger.warning(
                get_localized_text(
                    "service_report_load_failed",
                    report=report_path,
                    error=exc,
                )
            )
        return None

    def _execution_trace_file(self) -> Path:
        return Path(getattr(config, "DEFAULT_EXECUTION_TRACE_FILE"))

    def _load_execution_trace(self) -> dict[str, dict[str, object]]:
        trace_file = self._execution_trace_file()
        if not trace_file.exists():
            return {}

        try:
            with trace_file.open("r", encoding="utf-8") as handle:
                raw = json.load(handle)
        except json.JSONDecodeError as exc:
            logger.warning("Invalid execution trace JSON in %s: %s", trace_file, exc)
            return {}
        except OSError as exc:
            logger.warning(
                "Unable to read execution trace file %s: %s", trace_file, exc
            )
            return {}

        if not isinstance(raw, dict):
            logger.warning("Execution trace file %s has invalid structure", trace_file)
            return {}
        return {
            str(key): value for key, value in raw.items() if isinstance(value, dict)
        }

    def _save_execution_trace(self, trace: dict[str, dict[str, object]]) -> None:
        trace_file = self._execution_trace_file()
        trace_file.parent.mkdir(parents=True, exist_ok=True)
        with trace_file.open("w", encoding="utf-8") as handle:
            json.dump(trace, handle, indent=2, ensure_ascii=False)

    def _trace_key(
        self,
        converter: ConverterName | None,
        statistics: ConversionStatistics | None,
    ) -> str:
        if statistics is not None and statistics.converter_name:
            return str(statistics.converter_name).strip().casefold()
        return str(converter or "unknown").strip().casefold()

    def _load_previous_statistics(
        self,
        converter: ConverterName | None,
        statistics: ConversionStatistics | None,
    ) -> ConversionStatistics | None:
        if statistics is None:
            return None

        trace = self._load_execution_trace()
        previous_raw = trace.get(self._trace_key(converter, statistics))
        if previous_raw is None:
            return None

        try:
            from scripts.converters.statistics import ConversionStatistics

            return ConversionStatistics.from_dict(previous_raw)
        except (TypeError, ValueError, KeyError) as exc:
            logger.warning("Unable to parse previous execution trace: %s", exc)
            return None

    def _store_execution_trace(
        self,
        converter: ConverterName | None,
        statistics: ConversionStatistics | None,
    ) -> None:
        if statistics is None:
            return

        trace = self._load_execution_trace()
        trace[self._trace_key(converter, statistics)] = statistics.to_dict()
        self._save_execution_trace(trace)

    def convert(
        self,
        file_path: Path,
        converter: ConverterName,
        module_name: ConverterModuleName,
    ) -> ConversionResult:
        """
        Convert a file to HomeBank CSV format.

        Delegates to the appropriate converter module, then attempts to locate
        and load any generated statistics reports.

        Args:
            file_path: Path to input file.
            converter: Converter name (e.g., 'keytrade', 'amex').
            module_name: Converter module name (e.g., 'keytrade_csv').

        Returns:
            ConversionResult with conversion status, output path, and optional statistics.
        """
        try:
            source_path = Path(file_path)
            self._validate_source_file(source_path)

            handler = self._module_handlers.get(module_name)
            if handler is None:
                message = get_localized_text(
                    "service_unsupported_module", module_name=module_name
                )
                logger.warning(message)
                return ConversionResult(
                    file_path=source_path,
                    converter=converter,
                    module_name=module_name,
                    status="FAILED",
                    error=f"Unsupported converter module: {module_name}",
                )

            out_path = self._build_output_path(source_path, converter, module_name)
            logger.info(
                "Converting %s with %s -> %s", source_path.name, module_name, out_path
            )
            resolved = handler(
                str(source_path),
                str(out_path),
                str(getattr(config, "PAYMENT_RULES", "payment_rules.json")),
            )
            if resolved is None:
                raise RuntimeError(
                    f"Converter {module_name} returned no output path for {file_path.name}"
                )
            out_path = Path(resolved)
            if not out_path.exists():
                raise FileNotFoundError(
                    f"Converter {module_name} did not generate {out_path}"
                )
            logger.info(
                get_localized_text(
                    "service_conversion_completed",
                    file=file_path.name,
                )
            )

            # Attempt to locate and load statistics report
            report_path = self._find_report_for_output(out_path)
            statistics = None
            previous_statistics = None
            if report_path:
                statistics = self._load_statistics_from_report(report_path)
                if statistics:
                    previous_statistics = self._load_previous_statistics(
                        converter, statistics
                    )
                    self._store_execution_trace(converter, statistics)
                    logger.info(
                        get_localized_text(
                            "service_loaded_statistics",
                            count=statistics.total_transactions,
                            net=statistics.total_net_movement,
                            currency=statistics.currency,
                        )
                    )

            return ConversionResult(
                file_path=file_path,
                converter=converter,
                module_name=module_name,
                status="OK",
                output_path=out_path,
                report_path=report_path,
                statistics=statistics,
                previous_statistics=previous_statistics,
            )
        except Exception as exc:
            logger.exception(
                get_localized_text(
                    "service_conversion_failed",
                    file=file_path,
                    module_name=module_name,
                )
            )
            return ConversionResult(
                file_path=Path(file_path),
                converter=converter,
                module_name=module_name,
                status="FAILED",
                error=str(exc),
            )

    def batch_convert(self, files: Iterable[Path]) -> list[ConversionResult]:
        results: list[ConversionResult] = []
        files_list = list(files)
        logger.info(get_localized_text("service_batch_start", count=len(files_list)))
        for file_path in files_list:
            detection = self.detect(file_path)
            if not detection.converter or not detection.module_name:
                logger.warning(
                    get_localized_text(
                        "service_skipping_no_converter",
                        file=file_path,
                    )
                )
                results.append(
                    ConversionResult(
                        file_path=file_path,
                        converter=None,
                        module_name=None,
                        status="SKIPPED",
                        error="No converter detected",
                    )
                )
                continue
            results.append(
                self.convert(file_path, detection.converter, detection.module_name)
            )
        logger.info(get_localized_text("service_batch_finished"))
        return results
