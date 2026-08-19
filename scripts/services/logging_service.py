#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared logging utilities for CLI, GUI, and services."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


class CallbackLogHandler(logging.Handler):
    """Forward formatted log lines to a callback (for GUI/status consoles)."""

    def __init__(self, callback: Callable[[str], None]) -> None:
        super().__init__()
        self._callback = callback

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._callback(self.format(record))
        except Exception:
            # Logging should never raise into application flow.
            pass


def configure_logging(
    level: int = logging.INFO,
    log_file: str | Path | None = None,
    callback: Callable[[str], None] | None = None,
) -> None:
    """Configure root logging once, with optional file and callback handlers."""

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    if not root_logger.handlers:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(logging.Formatter(LOG_FORMAT))
        root_logger.addHandler(stream_handler)

    if log_file is not None:
        target = str(Path(log_file))
        has_same_file_handler = any(
            isinstance(handler, logging.FileHandler)
            and getattr(handler, "baseFilename", None) == str(Path(target).resolve())
            for handler in root_logger.handlers
        )
        if not has_same_file_handler:
            Path(target).parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(target, encoding="utf-8")
            file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
            root_logger.addHandler(file_handler)

    if callback is not None:
        callback_handler = CallbackLogHandler(callback)
        callback_handler.setFormatter(logging.Formatter(LOG_FORMAT))
        root_logger.addHandler(callback_handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
