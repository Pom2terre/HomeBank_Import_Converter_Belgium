# GUI Migration Plan (Incremental)

## Goal
Prepare the project for a graphical UI while keeping current CLI behavior intact.

## What was added now
- New service layer: `scripts/services/conversion_service.py`
- Public service API:
  - `ConversionService.detect(file_path)`
  - `ConversionService.convert(file_path, converter, module_name)`
  - `ConversionService.batch_convert(files)`
- DTOs for UI-friendly data exchange:
  - `DetectionResult`
  - `ConversionResult`

This layer isolates detection/conversion orchestration so a future GUI can call pure Python methods without parsing CLI output.

## Current architecture
- CLI entry points:
  - `main.py`
  - `scripts/select_and_convert.py`
- Converter implementations:
  - `scripts/converters/*`
- Orchestration for UI/CLI reuse:
  - `scripts/services/conversion_service.py`

## Next recommended steps
1. Refactor `main.py` and `scripts/select_and_convert.py` to call `ConversionService` instead of converter modules directly.
2. Replace converter `print(...)` side effects with optional logger callbacks or structured events.
3. Add a lightweight presenter layer that formats stats for CLI while GUI consumes raw result objects.
4. Create a GUI adapter (Tkinter/PySide/CustomTkinter) that calls `ConversionService` methods.
5. Keep integration tests around current fixtures to validate behavior parity.

## Why this helps for GUI
A GUI needs structured results (`status`, `error`, `output_path`) and should avoid terminal-coupled logic (`input()`, `print()`, clear-screen). The service layer is the first step in that separation.
