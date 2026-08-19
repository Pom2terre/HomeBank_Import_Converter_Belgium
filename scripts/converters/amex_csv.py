import csv
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, cast

try:
    from scripts.typing_contracts import PathLike
except ImportError:
    from typing_contracts import PathLike

try:
    from . import HOME_BANK_PAYMENT_CODES
    from .utils import (
        display_conversion_stats,
        generate_conversion_statistics,
        parse_date,
        parse_float,
        save_statistics_report,
        write_csv,
    )
except ImportError:
    try:
        from converters import HOME_BANK_PAYMENT_CODES
        from converters.utils import (
            display_conversion_stats,
            generate_conversion_statistics,
            parse_date,
            parse_float,
            save_statistics_report,
            write_csv,
        )
    except ImportError:
        from scripts.converters import HOME_BANK_PAYMENT_CODES
        from scripts.converters.utils import (
            display_conversion_stats,
            generate_conversion_statistics,
            parse_date,
            parse_float,
            save_statistics_report,
            write_csv,
        )

logger = logging.getLogger(__name__)

try:
    import config
except ImportError:
    sys.path.append(str(Path(__file__).resolve().parent.parent))
    import config


def charger_mapping() -> dict[str, Any]:
    """Charge le dictionnaire complet depuis categories_payees_homebank.json."""
    chemin_json = os.path.join(config.DOSSIER_SCRIPT, "categories_payees_homebank.json")
    try:
        with open(chemin_json, "r", encoding="utf-8") as f:
            return cast(dict[str, Any], json.load(f))
    except Exception:
        return {"categories": {}, "payees": []}


def convertir(chemin_source: PathLike, nom_fichier: PathLike | None = None) -> Path:
    input_filename = Path(chemin_source).name
    logger.info("Debut de la conversion AMEX pour %s", input_filename)

    payment_code = HOME_BANK_PAYMENT_CODES["credit_card"]
    payment_info = "credit card"
    mapping = charger_mapping()
    payees_liste = mapping.get("payees", [])

    payees_dict = {}
    items_to_parse = (
        payees_liste.values() if isinstance(payees_liste, dict) else payees_liste
    )
    for p in items_to_parse:
        if isinstance(p, dict) and p.get("name"):
            nom_tiers = p["name"].lower()
            nom_categorie = p.get("category_name") or p.get("category") or ""
            payees_dict[nom_tiers] = nom_categorie

    transactions = []
    lignes_ignorees = 0

    with open(chemin_source, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f, delimiter=",")
        next(reader, None)

        for index, row in enumerate(reader, start=2):
            if not row or len(row) < 3:
                continue

            try:
                date_str = row[0].strip()
                description = row[1].strip()
                montant_str = row[2].strip()

                if (
                    "règlement enregistré" in description.lower()
                    or "5 cents bonus" in description.lower()
                ):
                    lignes_ignorees += 1
                    continue

                date_obj = parse_date(date_str)
                if date_obj is None:
                    continue

                date_hb = date_obj.strftime("%d/%m/%Y")

                parsed_amount = parse_float(montant_str)
                montant_float = -(parsed_amount if parsed_amount is not None else 0.0)

                amount_str = f"{montant_float:.2f}".replace(".", ",")

                category = ""
                desc_lower = description.lower()
                for nom_tiers, nom_cat in payees_dict.items():
                    if nom_tiers in desc_lower:
                        category = nom_cat
                        description = nom_tiers.upper()
                        break

                transaction = {
                    "date": date_hb,
                    "payment": payment_code,
                    "info": payment_info,
                    "payee": description,
                    "memo": "",
                    "amount": amount_str,
                    "category": category,
                    "tags": "Amex",
                }
                transactions.append(transaction)

            except Exception as e:
                logger.warning("Erreur ligne %d: %s", index, e)

    nom_sortie = nom_fichier or f"HB_Amex_ {Path(chemin_source).name}"
    nom_sortie_path = Path(nom_sortie)
    if nom_sortie_path.is_absolute():
        chemin_sortie = str(nom_sortie_path)
        os.makedirs(str(nom_sortie_path.parent), exist_ok=True)
    else:
        chemin_sortie = os.path.join(config.DOSSIER_SORTIE_AMEX, nom_sortie)
        os.makedirs(config.DOSSIER_SORTIE_AMEX, exist_ok=True)

    write_csv(transactions, chemin_sortie)

    display_conversion_stats(transactions, chemin_source, chemin_sortie, title="AMEX")
    logger.info("Conversion AMEX CSV terminee")
    logger.info("%d transactions exportees", len(transactions))
    if lignes_ignorees > 0:
        logger.info("%d reglements ignores", lignes_ignorees)
    logger.info("Sauvegarde dans: %s", chemin_sortie)

    # Generate and save statistics report
    try:
        stats = generate_conversion_statistics(
            rows=transactions,
            input_path=Path(chemin_source),
            output_path=Path(chemin_sortie),
            title="AMEX",
            skipped_count=lignes_ignorees,
        )
        save_statistics_report(stats, Path(chemin_sortie), format="both")
    except Exception as e:
        logger.warning("Failed to generate statistics report: %s", e)

    return Path(chemin_sortie)


def convert(
    source: PathLike, output: PathLike | None = None, rules_path: PathLike | None = None
) -> Path:
    """Unified converter contract: convert(source, output=None, rules_path=None) -> Path."""
    del rules_path  # AMEX CSV currently does not use payment rules.

    source_path = Path(source)
    if output is None:
        output_name = f"HB_Amex_ {source_path.name}"
    else:
        output_name = str(Path(output))

    return convertir(str(source_path), output_name)
