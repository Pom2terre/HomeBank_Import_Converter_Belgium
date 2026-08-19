# HomeBank Converter

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)
![Tests](https://img.shields.io/badge/Tests-53%20passing-brightgreen)

HomeBank Converter is a Python-based tool for converting exported bank statements and PDF/CSV/XLSX files into HomeBank-compatible CSV files.

## Features

- Detects supported bank formats automatically
- Converts AMEX, Argenta, Keytrade, and Mastercard inputs
- Exports HomeBank-friendly CSV files
- Includes a desktop GUI for batch processing and review
- Produces conversion statistics and report files for auditability
- Supports localized output for French and English CSV exports

## Project layout

- `scripts/` — conversion logic, GUI, and service layer
- `tests/` — unit and regression tests
- `read_me/` — supporting project documentation
- `Input_file_examples/` — sample files used for validation and manual testing

## Quick start

1. Create and activate a virtual environment.
2. Install dependencies:
   `pip install -r requirements.txt`
3. Run the GUI:
   `python scripts/gui_poc.py`
4. Or run the batch conversion helper:
   `python scripts/select_and_convert.py`

## Release builds

The project now includes both a versioned Windows bundle and a true installer export path. Run the bundle script to generate a cleaned packaged artifact under `releases/`, then run the installer script to produce a Windows `.exe` installer.

- `./build_windows_bundle.ps1` — creates the bundled app and zip export.
- `./build_windows_installer.ps1` — creates an Inno Setup installer if `ISCC.exe` is installed; during setup it asks for the bank import folder plus a base output folder and writes `%USERPROFILE%/.homebank_converter.json`.

## Screenshots / Usage

The GUI provides a dark-mode dashboard for loading files, detecting compatible converters, and converting files in batch.

```bash
python scripts/gui_poc.py
```

A typical workflow is:

1. Add one or more bank files from the sidebar.
2. Select the desired action: convert selected, convert all, or retry failed items.
3. Review generated output and statistics reports.
4. Open the output folder or report from the GUI when needed.

## Validation

Run the project tests with:

```bash
pytest -q
```

## Notes

The project is designed to be usable from both CLI and GUI workflows, with robust conversion detection and clear report generation for imported financial files.
