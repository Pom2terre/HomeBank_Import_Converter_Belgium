Windows Distribution Guide
==========================

Goal
----
Provide a non-technical usage flow with:
1. One-click launcher from source checkout.
2. Optional bundled executable build for Windows distribution.

One-click launcher (source mode)
--------------------------------
Double-click:
- Launch_HomeBank_Converter.bat

Behavior:
- If a packaged exe exists at dist/HomeBankConverterGUI/HomeBankConverterGUI.exe, it launches that.
- Else it tries .venv/Scripts/python.exe.
- Else it falls back to py -3, then python.
- It starts the GUI directly (scripts/gui_launcher.py).

Bundled executable (optional)
-----------------------------
Build command (PowerShell):

    ./build_windows_bundle.ps1

What it does:
- Installs runtime deps from requirements.txt
- Installs PyInstaller
- Builds a windowed onedir app:

    dist/HomeBankConverterGUI/HomeBankConverterGUI.exe

Installer export (recommended)
------------------------------
Build command (PowerShell):

    ./build_windows_installer.ps1

What it does:
- Verifies the bundled app exists
- Builds a versioned installer package in releases/
- Uses Inno Setup if `ISCC.exe` is available to produce a setup .exe
- Falls back to a zip export if the installer compiler is missing
- During setup, asks for:
  - the bank import source folder (downloaded statements)
  - the base output folder where `Import_*` subfolders are created
- Writes the runtime config file to `%USERPROFILE%/.homebank_converter.json`

Distribution recommendation:
- Prefer the generated `releases/HomeBankConverterGUI-vX.Y.Z-setup.exe` for end-user installs.
- If you need a portable package, share the whole folder dist/HomeBankConverterGUI or the zip archive in releases/.

Packaged runtime defaults
-------------------------
When frozen, scripts/gui_launcher.py sets fallback env vars if missing:
- HBCONV_SOURCE_DIR -> %USERPROFILE%/Downloads
- HBCONV_SCRIPT_DIR -> exe directory
- HBCONV_HOMEBANK_DIR -> %USERPROFILE%/Documents/HomeBank
- HBCONV_PAYMENT_RULES -> payment_rules.json next to exe (if present)

Verification checklist
----------------------
After building:
1. Start dist/HomeBankConverterGUI/HomeBankConverterGUI.exe
2. Add a sample file in GUI
3. Convert it
4. Open output folder from GUI button
