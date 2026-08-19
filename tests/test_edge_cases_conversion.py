import tempfile
import unittest
from pathlib import Path

import pandas as pd

from scripts.converters import amex_csv as amex_csv_mod
from scripts.converters import amex_xlsx as amex_xlsx_mod
from scripts.services.conversion_service import ConversionService

ROOT = Path(__file__).resolve().parent.parent
EDGE_FIXTURES_DIR = ROOT / "tests" / "fixtures" / "edge_cases"


class EdgeCaseConversionTests(unittest.TestCase):
    def test_amex_csv_missing_columns_exports_header_only(self):
        fixture = EDGE_FIXTURES_DIR / "missing_columns_amex.csv"
        self.assertTrue(fixture.exists(), f"Missing fixture: {fixture}")

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "HB_missing_columns.csv"
            result = amex_csv_mod.convert(str(fixture), str(output_path))

            self.assertEqual(Path(result), output_path)
            self.assertTrue(
                output_path.exists(), f"Expected output file: {output_path}"
            )

            lines = output_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)
            self.assertEqual(
                lines[0], "date;payment;info;payee;memo;amount;category;tags"
            )

    def test_amex_xlsx_empty_workbook_exports_header_only(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source_path = Path(tmpdir) / "empty_amex.xlsx"
            with pd.ExcelWriter(source_path, engine="openpyxl") as writer:
                writer.book.create_sheet("Sheet1")

            output_path = Path(tmpdir) / "HB_empty_amex.csv"
            result = amex_xlsx_mod.convert(str(source_path), str(output_path))

            self.assertEqual(Path(result), output_path)
            self.assertTrue(output_path.exists())
            lines = output_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)
            self.assertEqual(
                lines[0], "date;payment;info;payee;memo;amount;category;tags"
            )

    def test_conversion_service_marks_missing_output_as_failed(self):
        service = ConversionService()
        service._module_handlers["amex_xlsx"] = lambda *args, **kwargs: None

        result = service.convert(Path("dummy.xlsx"), "amex", "amex_xlsx")

        self.assertEqual(result.status, "FAILED")
        self.assertTrue(
            "not found" in result.error.lower()
            or "returned no output path" in result.error.lower()
        )

    def test_conversion_service_rejects_empty_source_file(self):
        service = ConversionService()
        with tempfile.TemporaryDirectory() as tmpdir:
            empty_path = Path(tmpdir) / "empty.xlsx"
            empty_path.write_bytes(b"")

            result = service.convert(empty_path, "amex", "amex_xlsx")

            self.assertEqual(result.status, "FAILED")
            self.assertIn("empty", result.error.lower())

    def test_conversion_service_rejects_malformed_xlsx_container(self):
        service = ConversionService()
        with tempfile.TemporaryDirectory() as tmpdir:
            malformed_path = Path(tmpdir) / "malformed.xlsx"
            malformed_path.write_text(
                "this is not a valid xlsx archive", encoding="utf-8"
            )

            result = service.convert(malformed_path, "amex", "amex_xlsx")

            self.assertEqual(result.status, "FAILED")
            self.assertIn("malformed", result.error.lower())


if __name__ == "__main__":
    unittest.main()
