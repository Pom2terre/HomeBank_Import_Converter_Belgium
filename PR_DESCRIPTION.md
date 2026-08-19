Title: Move CLI entrypoint to root and align HomeBank payment mappings

Summary:
- Move CLI entrypoint from scripts/main.py to main.py at repository root.
- Update payment and info mapping rules to match requested HomeBank 5.10 behavior.
- Fix Argenta XLSX tags mapping so output tags come from input Référence/reference column when present.
- Force AMEX and MASTERCARD converters to use credit card payment mapping.
- Add latest Argenta fixture and extend tests with explicit payment/info mapping assertions.
- Update documentation references to reflect the new entrypoint location.

Files changed:
- main.py (moved from scripts/main.py)
- scripts/converters/__init__.py
- scripts/converters/amex_csv.py
- scripts/converters/amex_xlsx.py
- scripts/converters/argenta_xlsx.py
- scripts/converters/mastercard_pdf.py
- scripts/payment_rules.json
- tests/test_select_and_convert.py
- tests/fixtures/Input_file_examples/Argenta_BE10000000000000_2026-08-14_080521.xlsx
- read_me/Overview_HomeBank_New.txt
- read_me/GUI_MIGRATION_PLAN.md

Testing:
- Passed locally: python -m unittest discover -s tests -v
- Result: 10 tests, 0 failures, 0 errors.

Release notes:
- New project entrypoint location: run from repository root using python main.py.
- Payment mapping now follows revised business rules for debit card, direct debit, standing order, e-commerce card payments, and bank transfers.
- AMEX and MASTERCARD exports now consistently map to HomeBank credit card payment type.
- Argenta exports now fill tags from the Référence field when available.
