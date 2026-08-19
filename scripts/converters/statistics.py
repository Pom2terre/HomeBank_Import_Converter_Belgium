#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Data structures and utilities for conversion statistics tracking and reporting."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypedDict


class PaymentTypeAccumulator(TypedDict):
    count: int
    sum: float


@dataclass
class PaymentTypeStats:
    """Statistics for a single payment type/method."""

    payment_code: str
    """HomeBank payment code (e.g., '1' for credit card, '4' for bank transfer)."""

    payment_info: str
    """Human-readable payment method description (e.g., 'credit card', 'Outgoing transfer')."""

    transaction_count: int
    """Number of transactions with this payment type."""

    total_amount: float
    """Sum of amounts for transactions with this payment type (in EUR, can be negative)."""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PaymentTypeStats:
        """Reconstruct from dictionary."""
        return cls(**data)


@dataclass
class ConversionStatistics:
    """Complete statistics for a single file conversion."""

    input_file_name: str
    """Name of the input file (e.g., 'statement.csv')."""

    output_file_name: str
    """Name of the generated output CSV file (e.g., 'HB_statement.csv')."""

    timestamp: str
    """ISO 8601 timestamp when conversion occurred."""

    total_transactions: int
    """Total number of transactions converted."""

    total_net_movement: float
    """Sum of all transaction amounts (net movement in EUR)."""

    currency: str = "EUR"
    """Currency code for all amounts (defaults to EUR)."""

    payment_type_breakdown: list[PaymentTypeStats] = field(default_factory=list)
    """Breakdown of transactions by payment type, sorted by transaction count (descending)."""

    skipped_count: int = 0
    """Number of rows/transactions that were skipped during conversion."""

    warnings: list[str] = field(default_factory=list)
    """Optional list of conversion warnings or issues encountered."""

    converter_name: str = ""
    """Name of the converter used (e.g., 'keytrade', 'amex', 'argenta', 'mastercard')."""

    def to_dict(self) -> dict[str, Any]:
        """
        Convert to dictionary for JSON serialization.

        Returns:
            Dictionary representation with nested PaymentTypeStats as dicts.
        """
        data = asdict(self)
        # Ensure payment_type_breakdown is a list of dicts
        data["payment_type_breakdown"] = [
            ps.to_dict() if isinstance(ps, PaymentTypeStats) else ps
            for ps in data["payment_type_breakdown"]
        ]
        return data

    def to_json(self, indent: int = 2) -> str:
        """
        Convert to pretty-printed JSON string.

        Args:
            indent: Number of spaces for indentation (default 2).

        Returns:
            JSON string representation.
        """
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConversionStatistics:
        """
        Reconstruct from dictionary (e.g., loaded from JSON).

        Args:
            data: Dictionary with ConversionStatistics fields.

        Returns:
            ConversionStatistics instance.
        """
        data_copy = data.copy()

        # Reconstruct nested PaymentTypeStats objects
        payment_stats = [
            PaymentTypeStats(**ps) if isinstance(ps, dict) else ps
            for ps in data_copy.get("payment_type_breakdown", [])
        ]
        data_copy["payment_type_breakdown"] = payment_stats

        return cls(**data_copy)

    @classmethod
    def from_json(cls, json_str: str) -> ConversionStatistics:
        """
        Load from JSON string.

        Args:
            json_str: JSON string representation.

        Returns:
            ConversionStatistics instance.
        """
        data = json.loads(json_str)
        return cls.from_dict(data)

    @classmethod
    def from_file(cls, file_path: Path) -> ConversionStatistics:
        """
        Load from JSON file.

        Args:
            file_path: Path to JSON report file.

        Returns:
            ConversionStatistics instance.

        Raises:
            FileNotFoundError: If file does not exist.
            json.JSONDecodeError: If file is not valid JSON.
        """
        with file_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)

    def save_to_file(self, file_path: Path, mode: str = "w", indent: int = 2) -> None:
        """
        Save statistics to JSON file.

        Args:
            file_path: Path where JSON should be saved.
            mode: File open mode ('w' for write, 'x' for exclusive create).
            indent: Number of spaces for indentation.
        """
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with file_path.open(mode, encoding="utf-8") as f:
            f.write(self.to_json(indent=indent))

    def to_text(self) -> str:
        """
        Generate human-readable text representation.

        Returns:
            Multi-line formatted string for display or file output.
        """
        lines = [
            "Conversion Report",
            "=" * 70,
            f"Timestamp:              {self.timestamp}",
            f"Converter:              {self.converter_name or 'Unknown'}",
            f"Input File:             {self.input_file_name}",
            f"Output File:            {self.output_file_name}",
            "",
            "Transaction Summary",
            "-" * 70,
            f"Total Transactions:     {self.total_transactions}",
            f"Total Net Movement:     {self.total_net_movement:12.2f} {self.currency}",
        ]

        if self.skipped_count > 0:
            lines.append(f"Skipped Rows:           {self.skipped_count}")

        lines.append("")

        if self.payment_type_breakdown:
            lines.append("Payment Type Breakdown")
            lines.append("-" * 70)
            lines.append(
                f"{'Code':<6s} {'Payment Method':<35s} {'Count':>8s} {'Total':>12s}"
            )
            lines.append("-" * 70)
            for ps in self.payment_type_breakdown:
                lines.append(
                    f"{ps.payment_code:<6s} {ps.payment_info:<35s} "
                    f"{ps.transaction_count:>8d} {ps.total_amount:>12.2f}"
                )
            lines.append("")

        if self.warnings:
            lines.append("Warnings")
            lines.append("-" * 70)
            for warning in self.warnings:
                lines.append(f"  • {warning}")
            lines.append("")

        lines.append("=" * 70)
        return "\n".join(lines)

    def save_text_to_file(self, file_path: Path, mode: str = "w") -> None:
        """
        Save human-readable text report to file.

        Args:
            file_path: Path where text report should be saved.
            mode: File open mode ('w' for write, 'x' for exclusive create).
        """
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with file_path.open(mode, encoding="utf-8") as f:
            f.write(self.to_text())

    def total_revenues(self) -> float:
        """Return the total amount received in positive entries."""
        return sum(max(item.total_amount, 0.0) for item in self.payment_type_breakdown)

    def total_expenses(self) -> float:
        """Return the total spent in negative entries."""
        return sum(
            abs(min(item.total_amount, 0.0)) for item in self.payment_type_breakdown
        )

    def summary(self) -> dict[str, float | int | str]:
        """Return a compact summary for GUI display and reporting."""
        return {
            "currency": self.currency,
            "total_transactions": self.total_transactions,
            "total_revenues": self.total_revenues(),
            "total_expenses": self.total_expenses(),
            "net_movement": self.total_net_movement,
            "skipped_count": self.skipped_count,
        }


def create_statistics(
    rows: list[dict[str, str]],
    input_file_name: str,
    output_file_name: str,
    converter_name: str = "",
    skipped_count: int = 0,
    warnings: list[str] | None = None,
    currency: str = "EUR",
) -> ConversionStatistics:
    """
    Factory function to generate ConversionStatistics from transaction data.

    This is a convenience function that calculates all statistics from a list
    of transaction dictionaries (as produced by converters).

    Args:
        rows: List of transaction dictionaries with 'amount', 'payment', 'info' fields.
        input_file_name: Name of the input file.
        output_file_name: Name of the output CSV file.
        converter_name: Name of the converter used (e.g., 'keytrade', 'amex').
        skipped_count: Number of rows skipped during conversion.
        warnings: Optional list of conversion warnings.
        currency: Currency code for amounts (default 'EUR').

    Returns:
        ConversionStatistics object with all calculated fields.
    """
    timestamp = datetime.now(timezone.utc).isoformat()

    # Calculate total and net movement
    total_net = 0.0
    for row in rows:
        try:
            amount_str = row.get("amount", "0")
            # Handle both comma and dot as decimal separator
            amount_str = amount_str.replace(",", ".")
            total_net += float(amount_str)
        except (ValueError, AttributeError):
            pass

    # Build payment type breakdown
    stats_by_type: dict[tuple[str, str], PaymentTypeAccumulator] = {}
    for row in rows:
        payment_code = row.get("payment", "")
        payment_info = row.get("info", "")
        key = (payment_code, payment_info)

        try:
            amount_str = row.get("amount", "0")
            amount_str = amount_str.replace(",", ".")
            amount = float(amount_str)
        except (ValueError, AttributeError):
            amount = 0.0

        if key not in stats_by_type:
            stats_by_type[key] = {"count": 0, "sum": 0.0}

        stats_by_type[key]["count"] += 1
        stats_by_type[key]["sum"] += amount

    # Convert to PaymentTypeStats, sorted by transaction count (descending)
    payment_breakdown = [
        PaymentTypeStats(
            payment_code=code,
            payment_info=info,
            transaction_count=int(data["count"]),
            total_amount=float(data["sum"]),
        )
        for (code, info), data in stats_by_type.items()
    ]
    payment_breakdown.sort(key=lambda x: x.transaction_count, reverse=True)

    return ConversionStatistics(
        input_file_name=input_file_name,
        output_file_name=output_file_name,
        timestamp=timestamp,
        total_transactions=len(rows),
        total_net_movement=total_net,
        currency=currency,
        payment_type_breakdown=payment_breakdown,
        skipped_count=skipped_count,
        warnings=warnings or [],
        converter_name=converter_name,
    )
