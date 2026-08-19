import tempfile
import unittest
from pathlib import Path

from scripts.services.detection_service import detect_converter

ROOT = Path(__file__).resolve().parent.parent
EDGE_FIXTURES_DIR = ROOT / "tests" / "fixtures" / "edge_cases"


class EdgeCaseDetectionTests(unittest.TestCase):
    def test_detect_converter_handles_malformed_csv(self):
        fixture = EDGE_FIXTURES_DIR / "malformed_input.csv"
        self.assertTrue(fixture.exists(), f"Missing fixture: {fixture}")

        detected, module_name = detect_converter(fixture)

        self.assertIsNone(detected)
        self.assertIsNone(module_name)

    def test_detect_converter_handles_malformed_xlsx(self):
        fixture = EDGE_FIXTURES_DIR / "malformed_input.xlsx"
        self.assertTrue(fixture.exists(), f"Missing fixture: {fixture}")

        detected, module_name = detect_converter(fixture)

        self.assertIsNone(detected)
        self.assertIsNone(module_name)

    def test_detect_converter_handles_malformed_pdf(self):
        fixture = EDGE_FIXTURES_DIR / "malformed_input.pdf"
        self.assertTrue(fixture.exists(), f"Missing fixture: {fixture}")

        detected, module_name = detect_converter(fixture)

        self.assertIsNone(detected)
        self.assertIsNone(module_name)

    def test_ambiguous_detection_prefers_keytrade_marker(self):
        fixture = EDGE_FIXTURES_DIR / "ambiguous_markers.csv"
        self.assertTrue(fixture.exists(), f"Missing fixture: {fixture}")

        detected, module_name = detect_converter(fixture)

        self.assertEqual(detected, "keytrade")
        self.assertEqual(module_name, "keytrade_csv")

    def test_detect_converter_supports_utf8_bom_and_latin1_csv(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            utf8_bom = tmp / "amex_utf8_bom.csv"
            latin1_file = tmp / "amex_latin1.csv"

            utf8_bom.write_text(
                "date,description,montant\n14/08/2026,Règlement enregistré,-10.00\n",
                encoding="utf-8-sig",
            )
            latin1_file.write_bytes(
                "date,description,montant\n14/08/2026,Online purchase,-10.00\n".encode(
                    "latin-1"
                )
            )

            utf8_detected, utf8_module = detect_converter(utf8_bom)
            latin1_detected, latin1_module = detect_converter(latin1_file)

            self.assertEqual((utf8_detected, utf8_module), ("amex", "amex_csv"))
            self.assertEqual((latin1_detected, latin1_module), ("amex", "amex_csv"))


if __name__ == "__main__":
    unittest.main()
