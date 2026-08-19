"""
Unit and integration tests for the statistics pipeline.

Tests cover:
- Statistics generation from transaction data
- JSON/TXT serialization and deserialization
- Report file discovery and loading
- Integration with converters and service layer
"""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.converters.statistics import (
    ConversionStatistics,
    PaymentTypeStats,
    create_statistics,
)
from scripts.converters.utils import (
    display_conversion_stats,
    generate_conversion_statistics,
    save_statistics_report,
    write_csv,
)
from scripts.services.conversion_service import ConversionService


class TestPaymentTypeStats(unittest.TestCase):
    """Test PaymentTypeStats dataclass."""

    def test_payment_type_stats_creation(self) -> None:
        """Test creating a PaymentTypeStats instance."""
        stats = PaymentTypeStats(
            payment_code="1",
            payment_info="CB",
            transaction_count=5,
            total_amount=150.00,
        )
        self.assertEqual(stats.payment_code, "1")
        self.assertEqual(stats.payment_info, "CB")
        self.assertEqual(stats.transaction_count, 5)
        self.assertEqual(stats.total_amount, 150.00)

    def test_payment_type_stats_dict_conversion(self) -> None:
        """Test to_dict and from_dict methods."""
        original = PaymentTypeStats(
            payment_code="4",
            payment_info="VIREMENT",
            transaction_count=3,
            total_amount=75.50,
        )
        data = original.to_dict()
        restored = PaymentTypeStats.from_dict(data)
        self.assertEqual(original.payment_code, restored.payment_code)
        self.assertEqual(original.payment_info, restored.payment_info)
        self.assertEqual(original.transaction_count, restored.transaction_count)
        self.assertEqual(original.total_amount, restored.total_amount)

    def test_payment_type_stats_json_serialization(self) -> None:
        """Test JSON serialization of PaymentTypeStats."""
        stats = PaymentTypeStats(
            payment_code="1",
            payment_info="AMEX",
            transaction_count=2,
            total_amount=250.00,
        )
        json_str = json.dumps(stats.to_dict())
        self.assertIn("AMEX", json_str)
        self.assertIn("2", json_str)
        self.assertIn("250", json_str)


class TestConversionStatistics(unittest.TestCase):
    """Test ConversionStatistics dataclass."""

    def setUp(self) -> None:
        """Set up test statistics."""
        self.stats = ConversionStatistics(
            input_file_name="test.csv",
            output_file_name="HB_test.csv",
            timestamp="2026-08-15T12:00:00Z",
            total_transactions=10,
            total_net_movement=-200.00,
            currency="EUR",
            payment_type_breakdown=[
                PaymentTypeStats("1", "CB", 5, 200.00),
                PaymentTypeStats("4", "VIREMENT", 3, 150.00),
                PaymentTypeStats("2", "CHEQUE", 2, 150.00),
            ],
            skipped_count=0,
            warnings=[],
            converter_name="keytrade",
        )

    def test_statistics_creation(self) -> None:
        """Test creating ConversionStatistics."""
        self.assertEqual(self.stats.total_transactions, 10)
        self.assertEqual(self.stats.total_net_movement, -200.00)
        self.assertEqual(self.stats.currency, "EUR")
        self.assertEqual(len(self.stats.payment_type_breakdown), 3)

    def test_statistics_to_dict(self) -> None:
        """Test conversion to dictionary."""
        data = self.stats.to_dict()
        self.assertEqual(data["total_transactions"], 10)
        self.assertEqual(data["currency"], "EUR")
        self.assertIn("payment_type_breakdown", data)
        self.assertEqual(len(data["payment_type_breakdown"]), 3)

    def test_statistics_from_dict(self) -> None:
        """Test creation from dictionary."""
        data = self.stats.to_dict()
        restored = ConversionStatistics.from_dict(data)
        self.assertEqual(self.stats.total_transactions, restored.total_transactions)
        self.assertEqual(self.stats.total_net_movement, restored.total_net_movement)
        self.assertEqual(
            len(self.stats.payment_type_breakdown), len(restored.payment_type_breakdown)
        )

    def test_statistics_json_serialization(self) -> None:
        """Test JSON round-trip serialization."""
        json_str = self.stats.to_json()
        data = json.loads(json_str)
        restored = ConversionStatistics.from_dict(data)
        self.assertEqual(self.stats.total_transactions, restored.total_transactions)
        self.assertEqual(self.stats.currency, restored.currency)
        self.assertEqual(
            len(self.stats.payment_type_breakdown), len(restored.payment_type_breakdown)
        )

    def test_statistics_to_text_report(self) -> None:
        """Test text report generation."""
        text = self.stats.to_text()
        self.assertIn("Conversion Report", text)
        self.assertIn("Total Transactions:", text)
        self.assertIn("10", text)
        self.assertIn("EUR", text)
        self.assertIn("Payment Type Breakdown", text)

    def test_statistics_summary_values(self) -> None:
        """Test summary totals for GUI display."""
        stats = ConversionStatistics(
            input_file_name="test.csv",
            output_file_name="HB_test.csv",
            timestamp="2026-08-15T12:00:00Z",
            total_transactions=5,
            total_net_movement=150.00,
            currency="EUR",
            payment_type_breakdown=[
                PaymentTypeStats("1", "SALARY", 2, 1200.00),
                PaymentTypeStats("2", "GROCERIES", 2, -850.00),
                PaymentTypeStats("3", "RENT", 1, -200.00),
            ],
        )

        summary = stats.summary()
        self.assertEqual(summary["total_revenues"], 1200.0)
        self.assertEqual(summary["total_expenses"], 1050.0)
        self.assertEqual(summary["net_movement"], 150.0)
        self.assertEqual(summary["total_transactions"], 5)

    def test_statistics_save_text_to_file(self) -> None:
        """Test saving text report to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = Path(tmpdir) / "stats_report.txt"
            self.stats.save_text_to_file(report_path)
            self.assertTrue(report_path.exists())
            content = report_path.read_text()
            self.assertIn("Conversion Report", content)
            self.assertIn("10", content)


class TestCreateStatistics(unittest.TestCase):
    """Test the create_statistics factory function."""

    def test_create_statistics_from_transactions(self) -> None:
        """Test generating statistics from transaction data."""
        transactions = [
            {
                "amount": "100.00",
                "payment": "1",
                "info": "CB SUPERMARKET",
            },
            {
                "amount": "50.00",
                "payment": "4",
                "info": "VIREMENT SALARY",
            },
            {
                "amount": "25.50",
                "payment": "1",
                "info": "CB RESTAURANT",
            },
        ]

        stats = create_statistics(
            rows=transactions,
            input_file_name="test.csv",
            output_file_name="HB_test.csv",
            currency="EUR",
            skipped_count=0,
        )

        self.assertIsInstance(stats, ConversionStatistics)
        self.assertEqual(stats.total_transactions, 3)
        self.assertEqual(stats.currency, "EUR")

    def test_create_statistics_with_comma_decimals(self) -> None:
        """Test handling of comma decimal separators."""
        transactions = [
            {
                "amount": "123,45",
                "payment": "1",
                "info": "CB",
            },
        ]

        stats = create_statistics(
            rows=transactions,
            input_file_name="test.csv",
            output_file_name="test.csv",
            currency="EUR",
        )
        self.assertEqual(stats.total_transactions, 1)

    def test_create_statistics_payment_type_breakdown(self) -> None:
        """Test payment type breakdown calculation."""
        transactions = [
            {"amount": "100.00", "payment": "1", "info": "CB SHOP1"},
            {"amount": "50.00", "payment": "1", "info": "CB SHOP2"},
            {"amount": "25.00", "payment": "4", "info": "VIREMENT"},
        ]

        stats = create_statistics(
            rows=transactions,
            input_file_name="test.csv",
            output_file_name="test.csv",
            currency="EUR",
        )
        self.assertGreater(len(stats.payment_type_breakdown), 0)

    def test_create_statistics_with_skipped_count(self) -> None:
        """Test statistics include skipped transaction count."""
        transactions = [
            {"amount": "100.00", "payment": "1", "info": "CB"},
        ]

        stats = create_statistics(
            rows=transactions,
            input_file_name="test.csv",
            output_file_name="test.csv",
            currency="EUR",
            skipped_count=5,
        )

        self.assertEqual(stats.total_transactions, 1)
        self.assertEqual(stats.skipped_count, 5)


class TestStatisticsUtilityFunctions(unittest.TestCase):
    """Test utility functions for statistics generation and saving."""

    def setUp(self) -> None:
        """Set up test data."""
        self.transactions = [
            {"amount": "100.00", "payment": "1", "info": "CB"},
            {"amount": "50.00", "payment": "4", "info": "VIREMENT"},
        ]

    def test_generate_conversion_statistics(self) -> None:
        """Test generate_conversion_statistics utility function."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.csv"
            input_path = Path(tmpdir) / "input.csv"

            stats = generate_conversion_statistics(
                rows=self.transactions,
                input_path=input_path,
                output_path=output_path,
                title="TEST",
                skipped_count=0,
            )
            self.assertIsInstance(stats, ConversionStatistics)
            self.assertEqual(stats.total_transactions, 2)

    def test_save_statistics_report_json(self) -> None:
        """Test saving statistics as JSON report."""
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "input.csv"
            output_path = Path(tmpdir) / "HB_output.csv"

            stats = generate_conversion_statistics(
                rows=self.transactions,
                input_path=input_path,
                output_path=output_path,
                title="TEST",
            )

            report_path = save_statistics_report(
                stats=stats,
                output_csv_path=output_path,
                format="json",
            )

            self.assertTrue(report_path.exists())
            self.assertEqual(report_path.suffix, ".json")

            # Verify JSON is valid
            with open(report_path) as f:
                data = json.load(f)
            self.assertEqual(data["total_transactions"], 2)

    def test_save_statistics_report_txt(self) -> None:
        """Test saving statistics as text report."""
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "input.csv"
            output_path = Path(tmpdir) / "HB_output.csv"

            stats = generate_conversion_statistics(
                rows=self.transactions,
                input_path=input_path,
                output_path=output_path,
                title="TEST",
            )

            report_path = save_statistics_report(
                stats=stats,
                output_csv_path=output_path,
                format="txt",
            )

            self.assertTrue(report_path.exists())
            self.assertEqual(report_path.suffix, ".txt")

            # Verify text is readable
            content = report_path.read_text()
            self.assertIn("Conversion Report", content)
            self.assertIn("2", content)

    def test_save_statistics_report_both_formats(self) -> None:
        """Test saving statistics in both formats."""
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "input.csv"
            output_path = Path(tmpdir) / "HB_output.csv"

            stats = generate_conversion_statistics(
                rows=self.transactions,
                input_path=input_path,
                output_path=output_path,
                title="TEST",
            )

            result = save_statistics_report(
                stats=stats,
                output_csv_path=output_path,
                format="both",
            )

            json_path, txt_path = result
            self.assertTrue(json_path.exists())
            self.assertTrue(txt_path.exists())
            self.assertNotEqual(json_path, txt_path)

    def test_write_csv_supports_french_headers(self) -> None:
        """Test exported CSV headers can be generated in French."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "HB_output.csv"
            row = {
                "date": "01/02/2025",
                "payment": "1",
                "info": "Grocery",
                "payee": "Market",
                "memo": "Weekly shop",
                "amount": "15,75",
                "category": "",
                "tags": "food",
            }

            write_csv([row], output_path, language="french")
            with output_path.open("r", encoding="utf-8", newline="") as handle:
                header = handle.readline().strip().split(";")

            self.assertIn("paiement", header)
            self.assertIn("montant", header)
            self.assertIn("beneficiaire", header)

    def test_display_conversion_stats_formats_cli_summary(self) -> None:
        """Test CLI summary output is readable and includes key metrics."""
        rows = [
            {
                "date": "01/01/2025",
                "payment": "5",
                "info": "virement sortant",
                "amount": "-286.10",
            },
            {
                "date": "02/01/2025",
                "payment": "5",
                "info": "virement entrant",
                "amount": "6.66",
            },
        ]
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            display_conversion_stats(
                rows,
                input_file="source.csv",
                output_file="HB_output.csv",
                title="AMEX",
                skipped_count=1,
            )
        output = stdout.getvalue()
        self.assertIn("STATISTIQUES DE CONVERSION AMEX", output)
        self.assertIn("Fichier source", output)
        self.assertIn("Total opérations", output)
        self.assertIn("Conversion terminée", output)
        self.assertIn("transaction(s) exportée", output)


class TestReportDiscoveryAndLoading(unittest.TestCase):
    """Test report discovery and loading in ConversionService."""

    def setUp(self) -> None:
        """Set up test service."""
        self.service = ConversionService()

    def test_find_report_for_output_json(self) -> None:
        """Test finding JSON report next to output file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "HB_output.csv"
            report_path = Path(tmpdir) / "HB_output_report.json"

            # Create dummy files
            output_path.touch()
            report_path.write_text('{"total_transactions": 5}')

            found = self.service._find_report_for_output(output_path)
            self.assertEqual(found, report_path)

    def test_find_report_for_output_txt(self) -> None:
        """Test finding TXT report next to output file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "HB_output.csv"
            report_path = Path(tmpdir) / "HB_output_report.txt"

            # Create dummy files
            output_path.touch()
            report_path.write_text("Report content")

            found = self.service._find_report_for_output(output_path)
            self.assertEqual(found, report_path)

    def test_find_report_for_output_prefers_json(self) -> None:
        """Test that JSON is preferred when both JSON and TXT exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "HB_output.csv"
            json_path = Path(tmpdir) / "HB_output_report.json"
            txt_path = Path(tmpdir) / "HB_output_report.txt"

            # Create both files
            output_path.touch()
            json_path.write_text('{"total": 5}')
            txt_path.write_text("Report")

            found = self.service._find_report_for_output(output_path)
            self.assertEqual(found, json_path)

    def test_find_report_for_output_not_found(self) -> None:
        """Test behavior when no report exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "HB_output.csv"
            output_path.touch()

            found = self.service._find_report_for_output(output_path)
            self.assertIsNone(found)

    def test_load_statistics_from_report_json(self) -> None:
        """Test loading ConversionStatistics from JSON report."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a valid statistics JSON file
            stats_original = ConversionStatistics(
                input_file_name="test.csv",
                output_file_name="HB_test.csv",
                timestamp="2026-08-15T12:00:00Z",
                total_transactions=5,
                total_net_movement=-50.00,
                currency="EUR",
                payment_type_breakdown=[],
            )

            report_path = Path(tmpdir) / "report.json"
            report_path.write_text(stats_original.to_json())

            loaded = self.service._load_statistics_from_report(report_path)
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded.total_transactions, 5)
            self.assertEqual(loaded.currency, "EUR")

    def test_load_statistics_from_report_invalid_file(self) -> None:
        """Test handling of invalid JSON report."""
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = Path(tmpdir) / "report.json"
            report_path.write_text("invalid json {{{")

            loaded = self.service._load_statistics_from_report(report_path)
            self.assertIsNone(loaded)

    def test_load_statistics_from_report_missing_fields(self) -> None:
        """Test handling of incomplete statistics data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = Path(tmpdir) / "report.json"
            report_path.write_text(
                '{"total_transactions": 5}'
            )  # Missing required fields

            loaded = self.service._load_statistics_from_report(report_path)
            self.assertIsNone(loaded)


class TestConversionResultStatistics(unittest.TestCase):
    """Test ConversionResult includes statistics."""

    def test_conversion_result_has_report_and_statistics_fields(self) -> None:
        """Test that ConversionResult includes report_path and statistics fields."""
        from scripts.services.conversion_service import ConversionResult

        result = ConversionResult(
            file_path=Path("test.csv"),
            converter="amex",
            module_name="amex_csv",
            status="OK",
            output_path=Path("output.csv"),
            report_path=Path("output_report.json"),
        )

        self.assertIsNotNone(result.report_path)
        self.assertEqual(str(result.report_path), "output_report.json")

    def test_conversion_result_statistics_field(self) -> None:
        """Test ConversionResult can store ConversionStatistics."""
        from scripts.services.conversion_service import ConversionResult

        stats = ConversionStatistics(
            input_file_name="test.csv",
            output_file_name="HB_test.csv",
            timestamp="2026-08-15T12:00:00Z",
            total_transactions=10,
            total_net_movement=-50.00,
            currency="EUR",
            payment_type_breakdown=[],
        )

        result = ConversionResult(
            file_path=Path("test.csv"),
            converter="amex",
            module_name="amex_csv",
            status="OK",
            output_path=Path("output.csv"),
            statistics=stats,
        )

        self.assertIsNotNone(result.statistics)
        assert result.statistics is not None
        self.assertEqual(result.statistics.total_transactions, 10)


class TestStatisticsPipelineIntegration(unittest.TestCase):
    """Integration tests for the complete statistics pipeline."""

    def test_full_pipeline_statistics_generation_and_loading(self) -> None:
        """Test complete pipeline: generate -> save -> discover -> load."""
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "input.csv"
            output_path = Path(tmpdir) / "HB_test_output.csv"

            # Step 1: Generate statistics
            transactions = [
                {"amount": "100.00", "payment": "1", "info": "CB"},
                {"amount": "50.00", "payment": "4", "info": "VIREMENT"},
            ]
            stats = generate_conversion_statistics(
                rows=transactions,
                input_path=input_path,
                output_path=output_path,
                title="TEST",
            )

            # Step 2: Save report
            report_path = save_statistics_report(stats, output_path, format="json")
            self.assertTrue(report_path.exists())

            # Step 3: Discover report
            service = ConversionService()
            found_path = service._find_report_for_output(output_path)
            self.assertEqual(found_path, report_path)
            assert found_path is not None

            # Step 4: Load statistics
            loaded_stats = service._load_statistics_from_report(found_path)
            self.assertIsNotNone(loaded_stats)
            assert loaded_stats is not None
            self.assertEqual(loaded_stats.total_transactions, stats.total_transactions)
            self.assertEqual(loaded_stats.currency, stats.currency)

    def test_pipeline_with_multiple_report_formats(self) -> None:
        """Test pipeline with both JSON and TXT reports."""
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "input.csv"
            output_path = Path(tmpdir) / "HB_test.csv"

            transactions = [
                {"amount": "200.00", "payment": "1", "info": "CB"},
            ]
            stats = generate_conversion_statistics(
                rows=transactions,
                input_path=input_path,
                output_path=output_path,
                title="TEST",
            )

            # Save both formats
            json_path, txt_path = save_statistics_report(
                stats, output_path, format="both"
            )

            self.assertTrue(json_path.exists())
            self.assertTrue(txt_path.exists())

            # Discover should prefer JSON
            service = ConversionService()
            found = service._find_report_for_output(output_path)
            self.assertEqual(found, json_path)
            assert found is not None

            # Load should work from JSON
            loaded = service._load_statistics_from_report(found)
            self.assertIsNotNone(loaded)


if __name__ == "__main__":
    unittest.main()
