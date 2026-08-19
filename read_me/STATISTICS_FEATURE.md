# Statistics Pipeline Feature

## Overview

The HomeBank Converter now automatically generates detailed conversion statistics for every bank statement conversion. Statistics are generated, persisted, discovered, and made accessible through both the command-line interface and GUI.

## Features

### Automatic Statistics Generation
- Every converter (Keytrade, Amex CSV/XLSX, Argenta, Mastercard) automatically generates statistics
- Statistics capture transaction counts, amounts, payment type breakdown, and conversion metadata
- Both JSON (machine-readable) and TXT (human-readable) formats generated simultaneously

### Statistics Reports
Each conversion generates:
- **JSON Report**: `<output_name>_report.json` - Machine-readable format for integration/analysis
- **TXT Report**: `<output_name>_report.txt` - Human-readable report for review

Reports saved alongside the generated CSV output file in the same directory.

### GUI Integration
- **Report Column**: Treeview displays path to each conversion's report
- **View Report Button**: Opens report files in system default application
- **Status Bar**: Shows conversion results including report availability

### Service Layer Integration
- `ConversionResult` includes:
  - `report_path: Path | None` - Path to discovered report file
  - `statistics: ConversionStatistics | None` - Loaded statistics object with full data
- Report discovery and loading automatic after every conversion
- Graceful error handling ensures conversion never fails due to statistics issues

## Architecture

### Core Components

#### 1. **Statistics Dataclasses** (`scripts/converters/statistics.py`)

**ConversionStatistics**
```python
@dataclass
class ConversionStatistics:
    input_file_name: str          # Name of input file
    output_file_name: str         # Name of output CSV
    timestamp: str                # ISO 8601 UTC timestamp
    total_transactions: int       # Count of transactions
    total_net_movement: float     # Sum of all amounts (EUR)
    currency: str = "EUR"
    payment_type_breakdown: list[PaymentTypeStats] = []
    skipped_count: int = 0
    warnings: list[str] = []
    converter_name: str = ""
```

**PaymentTypeStats**
```python
@dataclass
class PaymentTypeStats:
    payment_code: str        # HomeBank payment code (e.g., '1')
    payment_info: str        # Human-readable description (e.g., 'CB')
    transaction_count: int   # Transactions with this payment type
    total_amount: float      # Sum of amounts for this type
```

#### 2. **Utility Functions** (`scripts/converters/utils.py`)

**generate_conversion_statistics()**
- Wrapper around the factory function
- Generates ConversionStatistics from transaction data
- Signature:
  ```python
  def generate_conversion_statistics(
      rows: list[dict[str, str]],
      input_path: Path,
      output_path: Path,
      title: str = "CONVERSION",
      skipped_count: int = 0,
      warnings: list[str] | None = None,
  ) -> ConversionStatistics
  ```

**save_statistics_report()**
- Persists statistics to JSON and/or TXT files
- Files automatically named with `_report` suffix
- Signature:
  ```python
  def save_statistics_report(
      stats: ConversionStatistics,
      output_csv_path: Path,
      format: str = "both",  # 'json', 'txt', or 'both'
  ) -> Path | tuple[Path, Path]
  ```

#### 3. **Factory Function** (`scripts/converters/statistics.py`)

**create_statistics()**
- Generates statistics from transaction rows
- Calculates totals, breakdowns, and payment type analysis
- Handles both comma and dot decimal separators
- Includes optional skipped row tracking and warnings

#### 4. **Converter Integration** (All 5 converters)

Each converter generates statistics after writing CSV:
```python
# After CSV output
stats = generate_conversion_statistics(
    rows=transactions,
    input_path=input_file,
    output_path=output_csv_path,
    title=converter_name,
    skipped_count=skipped_rows,
)
save_statistics_report(stats, output_csv_path, format="both")
```

#### 5. **Service Layer** (`scripts/services/conversion_service.py`)

**ConversionResult Enhancement**
- Extended with `report_path` and `statistics` fields
- `_find_report_for_output()`: Discovers reports next to CSV (prefers JSON)
- `_load_statistics_from_report()`: Loads ConversionStatistics from JSON
- `convert()` method: Automatically loads and returns statistics

#### 6. **GUI Enhancement** (`scripts/gui_poc.py`)

**Display**
- Report column in results treeview
- Shows path to report file for each conversion

**Interaction**
- "View Report" button opens report in system viewer
- Graceful handling for missing/unavailable reports

## Usage

### Command-Line Usage

When converting files programmatically:
```python
from scripts.services.conversion_service import ConversionService
from pathlib import Path

service = ConversionService()
result = service.convert(
    file_path=Path("statement.csv"),
    converter="keytrade",
    module_name="keytrade_csv"
)

# Access statistics
if result.statistics:
    print(f"Transactions: {result.statistics.total_transactions}")
    print(f"Net movement: {result.statistics.total_net_movement} EUR")
    print(f"Report: {result.report_path}")
```

### GUI Usage

1. Launch the GUI: `python main.py` or run `.bat` launcher
2. Add files for conversion
3. Click "Convert Selected" or "Convert All"
4. After conversion, "Report" column shows report path
5. Select a row and click "View Report" to open

### Report Contents

**JSON Report** - Machine-readable statistics:
```json
{
  "input_file_name": "statement.csv",
  "output_file_name": "HB_statement.csv",
  "timestamp": "2026-08-15T12:00:00Z",
  "total_transactions": 42,
  "total_net_movement": -523.75,
  "currency": "EUR",
  "payment_type_breakdown": [
    {
      "payment_code": "1",
      "payment_info": "CB",
      "transaction_count": 25,
      "total_amount": -450.50
    },
    {
      "payment_code": "4",
      "payment_info": "VIREMENT",
      "transaction_count": 17,
      "total_amount": -73.25
    }
  ],
  "skipped_count": 0,
  "warnings": [],
  "converter_name": "keytrade"
}
```

**TXT Report** - Human-readable summary:
```
Conversion Report
======================================================================
Timestamp:              2026-08-15T12:00:00Z
Converter:              keytrade
Input File:             statement.csv
Output File:            HB_statement.csv

Transaction Summary
----------------------------------------------------------------------
Total Transactions:     42
Total Net Movement:        -523.75 EUR

Payment Type Breakdown
----------------------------------------------------------------------
Code   Payment Method                         Count        Total
----------------------------------------------------------------------
1      CB                                        25      -450.50
4      VIREMENT                                  17       -73.25

======================================================================
```

## Implementation Details

### Error Handling
- Statistics generation wrapped in try/except in all converters
- Report discovery failures don't cause conversion failures
- Invalid JSON/TXT gracefully returns None
- Incomplete data detected and handled appropriately

### Performance
- Statistics generation completes in milliseconds
- Report discovery uses efficient path checks
- Lazy loading of statistics from JSON
- No blocking I/O in GUI threads

### Localization
- Handles comma (,) decimal separators (common in European locales)
- ISO 8601 timestamps in UTC for consistency
- Currency-agnostic (configurable, defaults to EUR)

### Backward Compatibility
- Existing converter behavior unchanged
- Statistics generation is optional (wrapped, can fail gracefully)
- GUI retains all existing functionality
- No changes to CSV output format or content

## Testing

Comprehensive test suite in `tests/test_statistics_pipeline.py` with 28 tests:

**Test Coverage:**
- ✅ Data serialization/deserialization (JSON, dict, text)
- ✅ Statistics generation from various transaction formats
- ✅ Decimal separator handling (comma, dot)
- ✅ Payment type breakdown and sorting
- ✅ Report file creation and discovery
- ✅ Error handling and resilience
- ✅ Service layer integration
- ✅ GUI field storage and retrieval
- ✅ End-to-end pipeline scenarios

**Running Tests:**
```bash
# All statistics tests
python -m pytest tests/test_statistics_pipeline.py -v

# Specific test class
python -m pytest tests/test_statistics_pipeline.py::TestConversionStatistics -v

# All project tests (46 total)
python -m pytest tests/ -v
```

## Configuration

No additional configuration required. Statistics are generated automatically for all conversions.

### Optional Customization

If you want to extend statistics generation:

1. **Add custom fields**: Extend `ConversionStatistics` dataclass
2. **Add custom breakdowns**: Modify `create_statistics()` factory function
3. **Change report formats**: Add custom serialization methods to dataclasses

## Troubleshooting

### Report not found
- Verify output CSV file exists
- Check file permissions in output directory
- Look for `_report.json` or `_report.txt` file in same directory as CSV

### Invalid report data
- Report files may be corrupted or incomplete
- Delete and re-run conversion to regenerate
- Check logs for conversion errors

### GUI "View Report" button not working
- Ensure no default application is associated with .json/.txt files
- Try opening report manually by double-clicking in file explorer
- Verify report file path is correct in "Report" column

## File Structure

```
scripts/
├── converters/
│   ├── statistics.py           # Core dataclasses and factory
│   ├── utils.py                # Utility functions (generate, save)
│   ├── keytrade_csv.py         # Converter with stats integration
│   ├── amex_csv.py             # Converter with stats integration
│   ├── amex_xlsx.py            # Converter with stats integration
│   ├── argenta_xlsx.py         # Converter with stats integration
│   └── mastercard_pdf.py       # Converter with stats integration
├── services/
│   └── conversion_service.py   # Service with report discovery/loading
└── gui_poc.py                  # GUI with report column and button

tests/
└── test_statistics_pipeline.py # Complete test suite (28 tests)
```

## Future Enhancements

Possible improvements for future versions:

1. **HTML Report Format**: Pretty formatted HTML with charts
2. **Report Comparison**: Compare statistics across multiple conversions
3. **Statistics Aggregation**: Combine multiple conversion reports
4. **CSV Export**: Export statistics breakdown as separate CSV
5. **Visualization**: Charts/graphs in GUI for payment breakdown
6. **Report Customization**: User-selectable report fields and formats
7. **Email Integration**: Send reports via email after conversion

## Support

For issues or questions:
1. Check test suite in `tests/test_statistics_pipeline.py` for usage examples
2. Review converter implementations for integration patterns
3. Examine GUI code for UI integration examples
4. Check `scripts/converters/statistics.py` for data structure details

---

**Version**: 1.0  
**Release Date**: August 2026  
**Last Updated**: 2026-08-15
