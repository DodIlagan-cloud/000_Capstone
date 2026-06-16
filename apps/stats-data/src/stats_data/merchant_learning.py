"""M9 merchant classification learning and lookup helpers."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Any


NAMESPACE = uuid.UUID("7a783aa3-f5a3-44be-98c7-0c571e44c31f")
NOISE_WORDS = {
    "city",
    "ph",
    "philippines",
    "mandaluyong",
    "makati",
    "quezon",
    "pasig",
    "manila",
    "pasay",
}


@dataclass(frozen=True)
class MerchantClassificationLookup:
    merchant_key: str
    match_status: str
    match_type: str = "exact_normalized_merchant"
    merchant_display_name: str | None = None
    transaction_type: str | None = None
    transaction_subtype: str | None = None
    spending_category: str | None = None
    spending_subcategory: str | None = None
    profile_confidence: float = 0.0
    confirmation_count: int = 0
    conflict_count: int = 0
    profile_status: str | None = None
    reason_codes: list[str] | None = None


def normalize_merchant_key(description: Any) -> str:
    text = str(description or "").lower()
    text = re.sub(r"\b\d{1,2}\s*/\s*\d{1,2}\b", " ", text)
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"^[a-z0-9]{2,5}\*", " ", text)
    text = re.split(r"\s+-\s+|[-:]", text, maxsplit=1)[0]
    text = re.sub(r"[^a-z0-9&]+", " ", text)
    words = [word for word in text.split() if word not in NOISE_WORDS]
    if len(words) > 4:
        words = words[:4]
    return " ".join(words)


def lookup_merchant_classification(
    connection: Any,
    *,
    description: str,
    owner_user_id: str | None = None,
) -> MerchantClassificationLookup:
    merchant_key = normalize_merchant_key(description)
    if not merchant_key:
        return MerchantClassificationLookup(
            merchant_key="",
            match_status="not_found",
            reason_codes=["MERCHANT_KEY_UNAVAILABLE"],
        )

    match_type = "exact_normalized_merchant"
    row = _lookup_profile_row(connection, merchant_key, owner_user_id)
    if not row:
        backfill_merchant_classification_profiles(
            connection,
            merchant_key=merchant_key,
            owner_user_id=owner_user_id,
            limit=1000,
        )
        row = _lookup_profile_row(connection, merchant_key, owner_user_id)
    if not row:
        row = _lookup_profile_prefix_row(connection, merchant_key, owner_user_id)
        if row:
            match_type = "prefix_normalized_merchant"

    if not row:
        return MerchantClassificationLookup(
            merchant_key=merchant_key,
            match_status="not_found",
            reason_codes=["PRIOR_MERCHANT_CLASSIFICATION_NOT_FOUND"],
        )

    status = str(row[8] or "inactive").lower()
    confirmation_count = int(row[6] or 0)
    conflict_count = int(row[7] or 0)
    reason_codes = ["PRIOR_MERCHANT_CLASSIFICATION_REUSED"]
    match_status = "matched"
    if status == "conflicted" or conflict_count > 0:
        match_status = "conflicted"
        reason_codes = ["PRIOR_MERCHANT_CLASSIFICATION_CONFLICT"]
    elif status != "active":
        match_status = "inactive"
        reason_codes = ["PRIOR_MERCHANT_CLASSIFICATION_INACTIVE"]

    return MerchantClassificationLookup(
        merchant_key=str(row[0]),
        match_status=match_status,
        match_type=match_type,
        merchant_display_name=str(row[1] or ""),
        transaction_type=str(row[2] or "unknown"),
        transaction_subtype=str(row[3] or "unknown"),
        spending_category=str(row[4] or "uncategorized"),
        spending_subcategory=str(row[5] or "unknown"),
        profile_confidence=_profile_confidence(confirmation_count, conflict_count, status),
        confirmation_count=confirmation_count,
        conflict_count=conflict_count,
        profile_status=status,
        reason_codes=reason_codes,
    )


def backfill_merchant_classification_profiles(
    connection: Any,
    *,
    merchant_key: str | None = None,
    owner_user_id: str | None = None,
    limit: int = 1000,
) -> int:
    """Build merchant profiles from already saved human-confirmed transactions."""
    limit = max(1, min(int(limit or 1000), 5000))
    cursor = connection.cursor()
    try:
        cursor.execute(
            f"""
SELECT TOP ({limit}) transaction_id, description, classification_confirmed_by_user_id,
       transaction_type, transaction_subtype, spending_category, spending_subcategory
FROM dbo.transactions
WHERE classification_human_confirmed = 1
  AND LOWER(COALESCE(transaction_type, 'unknown')) <> 'unknown'
  AND LOWER(COALESCE(transaction_subtype, 'unknown')) <> 'unknown'
  AND LOWER(COALESCE(spending_category, 'uncategorized')) NOT IN ('unknown', 'uncategorized')
  AND LOWER(COALESCE(spending_subcategory, 'unknown')) <> 'unknown'
ORDER BY COALESCE(classification_confirmed_at_utc, updated_at_utc, created_at_utc) DESC;
"""
        )
        rows = cursor.fetchall()
    finally:
        _close_cursor(cursor)

    profile_count = 0
    cursor = connection.cursor()
    try:
        for row in rows:
            description = str(row[1] or "")
            if merchant_key and normalize_merchant_key(description) != merchant_key:
                continue
            confirmed_by = owner_user_id or str(row[2] or "") or None
            upsert_merchant_classification_profile(
                cursor,
                description=description,
                transaction_id=str(row[0]),
                owner_user_id=confirmed_by,
                transaction_type=str(row[3] or "unknown").lower(),
                transaction_subtype=str(row[4] or "unknown").lower(),
                spending_category=str(row[5] or "uncategorized").lower(),
                spending_subcategory=str(row[6] or "unknown").lower(),
            )
            profile_count += 1
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        _close_cursor(cursor)
    return profile_count


def _lookup_profile_row(connection: Any, merchant_key: str, owner_user_id: str | None) -> Any | None:
    cursor = connection.cursor()
    try:
        if owner_user_id:
            cursor.execute(
                """
SELECT TOP (1) merchant_key, merchant_display_name, transaction_type, transaction_subtype,
       spending_category, spending_subcategory, confirmation_count, conflict_count,
       profile_status
FROM dbo.merchant_classification_profiles
WHERE merchant_key = ? AND (owner_user_id = ? OR owner_user_id IS NULL)
ORDER BY CASE WHEN owner_user_id = ? THEN 0 ELSE 1 END, updated_at_utc DESC;
""",
                merchant_key,
                owner_user_id,
                owner_user_id,
            )
        else:
            cursor.execute(
                """
SELECT TOP (1) merchant_key, merchant_display_name, transaction_type, transaction_subtype,
       spending_category, spending_subcategory, confirmation_count, conflict_count,
       profile_status
FROM dbo.merchant_classification_profiles
WHERE merchant_key = ?
ORDER BY updated_at_utc DESC;
""",
                merchant_key,
            )
        return cursor.fetchone()
    finally:
        _close_cursor(cursor)


def _lookup_profile_prefix_row(connection: Any, merchant_key: str, owner_user_id: str | None) -> Any | None:
    if len(merchant_key) < 6:
        return None

    cursor = connection.cursor()
    try:
        starts_with_profile = f"{merchant_key}%"
        if owner_user_id:
            cursor.execute(
                """
SELECT TOP (1) merchant_key, merchant_display_name, transaction_type, transaction_subtype,
       spending_category, spending_subcategory, confirmation_count, conflict_count,
       profile_status
FROM dbo.merchant_classification_profiles
WHERE (owner_user_id = ? OR owner_user_id IS NULL)
  AND (merchant_key LIKE ? OR ? LIKE merchant_key + '%')
ORDER BY CASE WHEN owner_user_id = ? THEN 0 ELSE 1 END,
         ABS(LEN(merchant_key) - ?),
         confirmation_count DESC,
         updated_at_utc DESC;
""",
                owner_user_id,
                starts_with_profile,
                merchant_key,
                owner_user_id,
                len(merchant_key),
            )
        else:
            cursor.execute(
                """
SELECT TOP (1) merchant_key, merchant_display_name, transaction_type, transaction_subtype,
       spending_category, spending_subcategory, confirmation_count, conflict_count,
       profile_status
FROM dbo.merchant_classification_profiles
WHERE merchant_key LIKE ? OR ? LIKE merchant_key + '%'
ORDER BY ABS(LEN(merchant_key) - ?), confirmation_count DESC, updated_at_utc DESC;
""",
                starts_with_profile,
                merchant_key,
                len(merchant_key),
            )
        return cursor.fetchone()
    finally:
        _close_cursor(cursor)


def upsert_merchant_classification_profile(
    cursor: Any,
    *,
    description: str,
    transaction_id: str,
    owner_user_id: str | None,
    transaction_type: str,
    transaction_subtype: str,
    spending_category: str,
    spending_subcategory: str,
) -> None:
    merchant_key = normalize_merchant_key(description)
    if not merchant_key or transaction_subtype == "unknown" or spending_subcategory == "unknown":
        return

    cursor.execute(
        """
SELECT merchant_profile_id, transaction_type, transaction_subtype, spending_category,
       spending_subcategory, profile_status
FROM dbo.merchant_classification_profiles WITH (UPDLOCK, HOLDLOCK)
WHERE merchant_key = ? AND ((? IS NULL AND owner_user_id IS NULL) OR owner_user_id = ?);
""",
        merchant_key,
        owner_user_id,
        owner_user_id,
    )
    row = cursor.fetchone()
    display_name = _display_name(description, merchant_key)
    if not row:
        cursor.execute(
            """
INSERT INTO dbo.merchant_classification_profiles (
    merchant_profile_id, merchant_key, merchant_display_name, owner_user_id,
    transaction_type, transaction_subtype, spending_category, spending_subcategory,
    classification_source, confirmation_count, conflict_count, profile_status,
    first_confirmed_transaction_id, last_confirmed_transaction_id,
    last_confirmed_by_user_id, last_confirmed_at_utc
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0, 'active', ?, ?, ?, SYSUTCDATETIME());
""",
            str(uuid.uuid5(NAMESPACE, f"merchant-profile|{owner_user_id or 'global'}|{merchant_key}")),
            merchant_key,
            display_name,
            owner_user_id,
            transaction_type,
            transaction_subtype,
            spending_category,
            spending_subcategory,
            "human_confirmed_transaction",
            transaction_id,
            transaction_id,
            owner_user_id,
        )
        return

    same_classification = (
        _same(row[1], transaction_type)
        and _same(row[2], transaction_subtype)
        and _same(row[3], spending_category)
        and _same(row[4], spending_subcategory)
    )
    if same_classification and str(row[5] or "").lower() != "conflicted":
        cursor.execute(
            """
UPDATE dbo.merchant_classification_profiles
SET merchant_display_name = ?,
    confirmation_count = confirmation_count + 1,
    last_confirmed_transaction_id = ?,
    last_confirmed_by_user_id = ?,
    last_confirmed_at_utc = SYSUTCDATETIME(),
    updated_at_utc = SYSUTCDATETIME()
WHERE merchant_profile_id = ?;
""",
            display_name,
            transaction_id,
            owner_user_id,
            row[0],
        )
        return

    cursor.execute(
        """
UPDATE dbo.merchant_classification_profiles
SET conflict_count = conflict_count + 1,
    profile_status = 'conflicted',
    last_confirmed_transaction_id = ?,
    last_confirmed_by_user_id = ?,
    last_confirmed_at_utc = SYSUTCDATETIME(),
    updated_at_utc = SYSUTCDATETIME()
WHERE merchant_profile_id = ?;
""",
        transaction_id,
        owner_user_id,
        row[0],
    )


def _profile_confidence(confirmation_count: int, conflict_count: int, status: str) -> float:
    if status != "active" or conflict_count > 0:
        return 0.0
    return min(0.97, 0.86 + max(0, confirmation_count - 1) * 0.03)


def _display_name(description: str, merchant_key: str) -> str:
    text = " ".join(str(description or "").split())
    return text[:200] if text else merchant_key.title()


def _same(left: Any, right: Any) -> bool:
    return str(left or "").strip().lower() == str(right or "").strip().lower()


def _close_cursor(cursor: Any) -> None:
    try:
        cursor.close()
    except Exception:
        pass
