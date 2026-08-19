import tempfile
import unittest
from pathlib import Path

from scripts.services.conversion_service import ConversionService


class EdgeCaseBatchTests(unittest.TestCase):
    def test_large_batch_processing_returns_consistent_statuses(self):
        service = ConversionService()
        batch_size = 300

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            files = []
            for index in range(batch_size):
                file_path = tmp / f"hb_large_batch_{index:03d}.csv"
                file_path.write_text("already converted", encoding="utf-8")
                files.append(file_path)

            results = service.batch_convert(files)

            self.assertEqual(len(results), batch_size)
            self.assertTrue(all(result.status == "SKIPPED" for result in results))
            self.assertTrue(
                all(result.error == "No converter detected" for result in results)
            )


if __name__ == "__main__":
    unittest.main()
