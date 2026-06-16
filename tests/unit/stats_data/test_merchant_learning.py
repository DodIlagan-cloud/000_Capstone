"""M9 merchant learning helper tests."""

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[3]
STATS_DATA_SRC = REPO_ROOT / "apps" / "stats-data" / "src"
if str(STATS_DATA_SRC) not in sys.path:
    sys.path.insert(0, str(STATS_DATA_SRC))

from stats_data.merchant_learning import (
    backfill_merchant_classification_profiles,
    lookup_merchant_classification,
    normalize_merchant_key,
    upsert_merchant_classification_profile,
)


def test_normalize_merchant_key_groups_gateway_and_location_variants():
    assert normalize_merchant_key("Ghl*Happy Elements Inc Quezon City") == "happy elements inc"
    assert normalize_merchant_key("Grabtaxi Phils - Ipg ( Magallanes Ma") == "grabtaxi phils"
    assert normalize_merchant_key("Grabtaxi Phils - Makat Bangkal Makat") == "grabtaxi phils"
    assert normalize_merchant_key("Sm Dept Store-Megamall: 02/03") == "sm dept store"


def test_lookup_merchant_classification_uses_prefix_match_after_exact_miss():
    class FakeCursor:
        def __init__(self, connection):
            self.connection = connection
            self.one = None
            self.many = []

        def execute(self, query, *args):
            self.connection.queries.append(query)
            if "FROM dbo.transactions" in query:
                self.many = []
            elif "LIKE" in query:
                self.one = (
                    "olympic village rds",
                    "Olympic Village-Rds Pione",
                    "purchase",
                    "merchant_purchase",
                    "transport",
                    "parking",
                    2,
                    0,
                    "active",
                )
            else:
                self.one = None

        def fetchone(self):
            return self.one

        def fetchall(self):
            return self.many

        def close(self):
            pass

    class FakeConnection:
        def __init__(self):
            self.queries = []
            self.committed = False

        def cursor(self):
            return FakeCursor(self)

        def commit(self):
            self.committed = True

        def rollback(self):
            raise AssertionError("rollback should not be called")

    connection = FakeConnection()

    lookup = lookup_merchant_classification(connection, description="Olympic Village")

    assert lookup.match_status == "matched"
    assert lookup.match_type == "prefix_normalized_merchant"
    assert lookup.spending_subcategory == "parking"
    assert lookup.reason_codes == ["PRIOR_MERCHANT_CLASSIFICATION_REUSED"]
    assert connection.committed is True


def test_upsert_merchant_classification_profile_is_owner_scoped():
    class FakeCursor:
        def __init__(self):
            self.calls = []
            self.one = None

        def execute(self, query, *args):
            self.calls.append((query, args))

        def fetchone(self):
            return self.one

    cursor = FakeCursor()

    upsert_merchant_classification_profile(
        cursor,
        description="Grabtaxi Phils - Ipg ( Magallanes Ma",
        transaction_id="transaction_1",
        owner_user_id="user_a",
        transaction_type="purchase",
        transaction_subtype="merchant_purchase",
        spending_category="transport",
        spending_subcategory="rideshare",
    )

    select_query, select_args = cursor.calls[0]
    insert_args = cursor.calls[1][1]

    assert "owner_user_id = ?" in select_query
    assert "OR owner_user_id IS NULL" not in select_query
    assert select_args == ("grabtaxi phils", "user_a", "user_a")
    assert insert_args[3] == "user_a"


def test_backfill_uses_requesting_owner_for_created_profiles():
    class FakeCursor:
        def __init__(self, connection):
            self.connection = connection
            self.rows = []
            self.one = None

        def execute(self, query, *args):
            self.connection.calls.append((query, args))
            if "FROM dbo.transactions" in query:
                self.rows = [
                    (
                        "transaction_1",
                        "Grabtaxi Phils - Ipg",
                        "original_confirmer",
                        "purchase",
                        "merchant_purchase",
                        "transport",
                        "rideshare",
                    )
                ]
            else:
                self.rows = []

        def fetchall(self):
            return self.rows

        def fetchone(self):
            return self.one

        def close(self):
            pass

    class FakeConnection:
        def __init__(self):
            self.calls = []
            self.committed = False

        def cursor(self):
            return FakeCursor(self)

        def commit(self):
            self.committed = True

        def rollback(self):
            raise AssertionError("rollback should not be called")

    connection = FakeConnection()

    count = backfill_merchant_classification_profiles(connection, owner_user_id="requesting_user")
    insert_call = next(call for call in connection.calls if "INSERT INTO dbo.merchant_classification_profiles" in call[0])

    assert count == 1
    assert insert_call[1][3] == "requesting_user"
    assert connection.committed is True
