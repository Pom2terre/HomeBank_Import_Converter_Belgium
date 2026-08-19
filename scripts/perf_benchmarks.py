#!/usr/bin/env python3
"""Small profiling benchmarks for scan/detect hot paths."""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import select_and_convert
from scripts.services.detection_service import detect_converter

FIXTURES = ROOT / "tests" / "fixtures" / "Input_file_examples"


def _legacy_scan(folder: Path) -> list[Path]:
    files: list[Path] = []
    for p in folder.iterdir():
        if not p.is_file() or p.suffix.lower() not in select_and_convert.ALLOWED_EXT:
            continue
        lowered = p.name.lower()
        if (
            lowered.startswith(select_and_convert.HOME_BANK_CSV_PREFIXES)
            and p.suffix.lower() == ".csv"
        ):
            continue
        files.append(p)
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files


def _optimized_scan(folder: Path) -> list[Path]:
    entries: list[tuple[float, Path]] = []
    with os.scandir(folder) as scan_iter:
        for entry in scan_iter:
            if not entry.is_file():
                continue

            suffix = Path(entry.name).suffix.lower()
            if suffix not in select_and_convert.ALLOWED_EXT:
                continue

            lowered_name = entry.name.lower()
            if (
                lowered_name.startswith(select_and_convert.HOME_BANK_CSV_PREFIXES)
                and suffix == ".csv"
            ):
                continue

            try:
                mtime = entry.stat().st_mtime
            except OSError:
                continue
            entries.append((mtime, Path(entry.path)))

    return [p for _, p in sorted(entries, key=lambda item: item[0], reverse=True)]


def benchmark_large_folder_scan(file_count: int = 6000) -> tuple[float, float, int]:
    with tempfile.TemporaryDirectory() as tmpdir:
        folder = Path(tmpdir)
        for i in range(file_count):
            if i % 3 == 0:
                name = f"Transactions_{i:05d}.csv"
            elif i % 3 == 1:
                name = f"Statement_{i:05d}.xlsx"
            else:
                name = f"readme_{i:05d}.txt"
            (folder / name).write_text("demo", encoding="utf-8")

        start_legacy = time.perf_counter()
        legacy_files = _legacy_scan(folder)
        legacy_elapsed = time.perf_counter() - start_legacy

        start_optimized = time.perf_counter()
        optimized_files = _optimized_scan(folder)
        optimized_elapsed = time.perf_counter() - start_optimized

        files = (
            optimized_files
            if len(legacy_files) == len(optimized_files)
            else legacy_files
        )

    return legacy_elapsed, optimized_elapsed, len(files)


def benchmark_detection_rounds(rounds: int = 200) -> tuple[float, int]:
    candidates = [
        FIXTURES / "activity.csv",
        FIXTURES / "activité.xlsx",
        FIXTURES / "Argenta_BE10000000000000_2026-08-14_080521.xlsx",
    ]
    existing = [p for p in candidates if p.exists()]
    if not existing:
        return 0.0, 0

    start = time.perf_counter()
    detections = 0
    for _ in range(rounds):
        for path in existing:
            detect_converter(path)
            detections += 1
    elapsed = time.perf_counter() - start
    return elapsed, detections


def main() -> None:
    legacy_scan_elapsed, scan_elapsed, scan_count = benchmark_large_folder_scan()
    det_elapsed, det_count = benchmark_detection_rounds()

    print("Performance benchmarks")
    print("-" * 60)
    print(
        f"Large-folder scan (legacy): {legacy_scan_elapsed:.4f}s for {scan_count} detected candidate files"
    )
    print(
        f"Large-folder scan (optimized): {scan_elapsed:.4f}s for {scan_count} detected candidate files"
    )
    if scan_count:
        print(f"  Legacy throughput: {scan_count / legacy_scan_elapsed:.1f} files/s")
        print(f"  Optimized throughput: {scan_count / scan_elapsed:.1f} files/s")
        print(f"  Scan speedup: {legacy_scan_elapsed / scan_elapsed:.2f}x")

    if det_count:
        print(f"Detection loop: {det_elapsed:.4f}s for {det_count} detections")
        print(f"  Throughput: {det_count / det_elapsed:.1f} detections/s")
    else:
        print("Detection loop: skipped (no fixtures found)")


if __name__ == "__main__":
    main()
