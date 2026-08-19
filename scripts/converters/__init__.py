import json
from functools import lru_cache
from pathlib import Path

# HomeBank 5.10 payment type codes (as used in CSV imports)
HOME_BANK_PAYMENT_CODES = {
    "none": "0",
    "credit_card": "1",
    "cheque": "2",
    "cash": "3",
    "bank_transfer": "4",
    "debit_card": "5",
    "standing_order": "6",
    "electronic_payment": "7",
    "deposit": "8",
    "bank_fee": "9",
    "direct_debit": "10",
    "mobile_phone": "11",
}

try:
    import config
except ImportError:
    try:
        from scripts import config
    except ImportError:
        raise


def get_payment_rules_path(rules_path=None):
    if rules_path:
        return Path(rules_path)

    default_path = getattr(config, "PAYMENT_RULES", None)
    if default_path:
        return Path(default_path)

    return Path(__file__).resolve().parents[1] / "payment_rules.json"


@lru_cache(maxsize=8)
def _load_payment_rules_from_path(path_str: str):
    with open(path_str, "r", encoding="utf-8") as f:
        return json.load(f)


def load_payment_rules(rules_path=None):
    path = get_payment_rules_path(rules_path)
    try:
        return _load_payment_rules_from_path(str(path.resolve()))
    except Exception:
        return {}


def determine_payment_mode(description, amount, rules=None):
    if rules is None:
        rules = load_payment_rules()

    default_payment = rules.get("default_payment", {})
    default_code = str(default_payment.get("code", "5"))
    debit_info = default_payment.get("name_debit", "Outgoing transfer")
    credit_info = default_payment.get("name_credit", "Incoming transfer")

    normalized = (description or "").lower()
    for rule in rules.get("rules", []):
        for keyword in rule.get("keywords", []):
            if keyword.lower() in normalized:
                payment_info = rule.get("payment", {})
                code = str(payment_info.get("code", default_code))
                if amount < 0:
                    info = payment_info.get(
                        "info_debit", payment_info.get("info", debit_info)
                    )
                else:
                    info = payment_info.get(
                        "info_credit", payment_info.get("info", credit_info)
                    )
                return code, info

    if amount < 0:
        return default_code, debit_info
    return default_code, credit_info


from . import amex_csv, amex_xlsx, argenta_xlsx, keytrade_csv, mastercard_pdf

__all__ = [
    "HOME_BANK_PAYMENT_CODES",
    "get_payment_rules_path",
    "load_payment_rules",
    "determine_payment_mode",
    "amex_csv",
    "amex_xlsx",
    "argenta_xlsx",
    "keytrade_csv",
    "mastercard_pdf",
]
