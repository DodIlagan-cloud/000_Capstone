from __future__ import annotations

from stats_data.database import open_azure_sql_connection
from stats_data.recognition_settings import save_label


CORE_LABELS = [
    ("document", "receipt", ["sales_receipt", "tax_receipt", "payment_terminal_receipt", "card_receipt", "medical_receipt", "unknown"]),
    ("transaction", "purchase", ["card_purchase", "eftpos_payment", "merchant_purchase", "cash_purchase", "unknown"]),
    ("spending", "transport", ["fuel", "public_transport", "parking", "rideshare", "unknown", "uncategorized"]),
]


def main() -> None:
    with open_azure_sql_connection() as connection:
        for scope, label, values in CORE_LABELS:
            save_label(connection, scope=scope, original_label="", label=label, values=values)
        connection.commit()
    print("Core recognition labels restored: receipt, purchase, transport")


if __name__ == "__main__":
    main()
