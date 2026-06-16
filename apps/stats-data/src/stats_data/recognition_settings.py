"""M9 - Stats Data and Persistence Start
Stores active recognition labels and rules in Azure SQL.
M9 End"""

from __future__ import annotations

import json
import os
import hashlib
import uuid
from pathlib import Path
from typing import Any


LABEL_SCOPES = {"document", "transaction", "spending"}
RULE_SCOPES = {"document", "transaction", "spending"}
SUGGESTION_ACTIONS = {"approve", "reject"}


def active_recognition_settings(connection: Any) -> dict[str, Any]:
    seed_recognition_settings_if_empty(connection)
    labels = _load_labels(connection)
    rules = _load_rules(connection)
    document_vocabulary = _vocabulary(labels, "document", "document_types", "document_subtypes")
    transaction_vocabulary = _vocabulary(labels, "transaction", "transaction_types", "transaction_subtypes")
    spending_vocabulary = _vocabulary(labels, "spending", "spending_categories", "spending_subcategories")
    context = _recognition_context(
        document_vocabulary=document_vocabulary,
        document_rules={"rules": rules["document"]},
        transaction_vocabulary=transaction_vocabulary,
        transaction_rules={"rules": rules["transaction"]},
        spending_vocabulary=spending_vocabulary,
        spending_rules={"rules": rules["spending"]},
    )
    return {
        "recognition_context_version": context["version"],
        "recognition_context": context,
        "document_vocabulary": document_vocabulary,
        "document_rules": {"rules": rules["document"]},
        "transaction_vocabulary": transaction_vocabulary,
        "transaction_rules": {"rules": rules["transaction"]},
        "spending_vocabulary": spending_vocabulary,
        "spending_rules": {"rules": rules["spending"]},
    }


def _recognition_context(
    *,
    document_vocabulary: dict[str, Any],
    document_rules: dict[str, Any],
    transaction_vocabulary: dict[str, Any],
    transaction_rules: dict[str, Any],
    spending_vocabulary: dict[str, Any],
    spending_rules: dict[str, Any],
) -> dict[str, Any]:
    context = {
        "document": {
            "vocabulary": document_vocabulary,
            "rules": _compact_rules(document_rules),
            "aliases": {},
            "deprecation_hints": {},
            "merge_hints": {},
        },
        "transaction": {
            "vocabulary": transaction_vocabulary,
            "subtype_parent_map": _child_parent_map(transaction_vocabulary, "transaction_subtypes"),
            "rules": _compact_rules(transaction_rules),
            "aliases": {},
            "deprecation_hints": {},
            "merge_hints": {},
        },
        "spending": {
            "vocabulary": spending_vocabulary,
            "subcategory_parent_map": _child_parent_map(spending_vocabulary, "spending_subcategories"),
            "rules": _compact_rules(spending_rules),
            "aliases": {},
            "deprecation_hints": {},
            "merge_hints": {},
        },
    }
    version = hashlib.sha256(json.dumps(context, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()[:16]
    return {"version": version, **context}


def _child_parent_map(vocabulary: dict[str, Any], subtypes_key: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    ambiguous_children = {"unknown", "uncategorized"}
    for parent, children in (vocabulary.get(subtypes_key, {}) or {}).items():
        parent_key = str(parent).strip().lower()
        for child in children or []:
            child_key = str(child).strip().lower()
            if child_key in ambiguous_children:
                continue
            if child_key and child_key not in mapping:
                mapping[child_key] = parent_key
    return dict(sorted(mapping.items()))


def _compact_rules(rules: dict[str, Any]) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for rule in rules.get("rules", []):
        compact.append(
            {
                key: rule.get(key)
                for key in [
                    "document_type",
                    "document_subtype",
                    "transaction_type",
                    "transaction_subtype",
                    "spending_category",
                    "spending_subcategory",
                    "reason_code",
                    "required_any",
                    "signals",
                    "minimum_score",
                ]
                if key in rule
            }
        )
    return compact


def save_label(connection: Any, *, scope: str, original_label: str, label: str, values: list[str]) -> None:
    scope = _scope(scope, LABEL_SCOPES)
    original_key = _normalize(original_label) if original_label else ""
    next_key = _normalize(label)
    values = _normalize_values(values, default_value="uncategorized" if scope == "spending" else "unknown")
    cursor = connection.cursor()
    if original_key and original_key != next_key:
        cursor.execute(
            """
UPDATE dbo.recognition_labels
SET label_key = ?, display_label = ?, values_json = ?, updated_at_utc = SYSUTCDATETIME()
WHERE label_scope = ? AND label_key = ?;
""",
            next_key,
            _display(next_key),
            json.dumps(values),
            scope,
            original_key,
        )
        if int(getattr(cursor, "rowcount", 0) or 0) == 0:
            raise ValueError("Recognition label to rename was not found. Refresh the page and try again.")
        _rename_rule_targets(cursor, scope, original_key, next_key)
    else:
        cursor.execute(
            """
MERGE dbo.recognition_labels AS target
USING (SELECT ? AS label_scope, ? AS label_key) AS source
ON target.label_scope = source.label_scope AND target.label_key = source.label_key
WHEN MATCHED THEN
    UPDATE SET display_label = ?, values_json = ?, is_active = 1, updated_at_utc = SYSUTCDATETIME()
WHEN NOT MATCHED THEN
    INSERT (label_id, label_scope, label_key, display_label, values_json, is_system, is_active)
    VALUES (?, ?, ?, ?, ?, 0, 1);
""",
            scope,
            next_key,
            _display(next_key),
            json.dumps(values),
            f"{scope}:{next_key}",
            scope,
            next_key,
            _display(next_key),
            json.dumps(values),
        )
    connection.commit()


def delete_label(connection: Any, *, scope: str, label: str) -> None:
    scope = _scope(scope, LABEL_SCOPES)
    key = _deletable_key(label)
    cursor = connection.cursor()
    cursor.execute(
        """
UPDATE dbo.recognition_labels
SET is_active = 0, updated_at_utc = SYSUTCDATETIME()
WHERE label_scope = ? AND label_key = ?;
""",
        scope,
        key,
    )
    cursor.execute(
        """
UPDATE dbo.recognition_rules
SET is_active = 0, updated_at_utc = SYSUTCDATETIME()
WHERE rule_scope = ? AND target_label = ?;
""",
        scope,
        key,
    )
    connection.commit()


def save_rule(
    connection: Any,
    *,
    scope: str,
    original_reason_code: str,
    target_label: str,
    target_subtype: str,
    reason_code: str,
    required_any: list[str],
    signals: list[str],
    minimum_score: float,
) -> None:
    scope = _scope(scope, RULE_SCOPES)
    target_label_key = _normalize(target_label)
    target_subtype_key = _normalize(target_subtype)
    reason_code = reason_code.strip().upper()
    if not reason_code:
        raise ValueError("Rule reason cannot be blank.")
    if minimum_score < 0 or minimum_score > 1:
        raise ValueError("Minimum score must be between 0 and 1.")
    _ensure_label_value(connection, scope, target_label_key, target_subtype_key)
    original = original_reason_code.strip().upper()
    cursor = connection.cursor()
    if original and original != reason_code:
        cursor.execute("DELETE FROM dbo.recognition_rules WHERE rule_scope = ? AND reason_code = ?;", scope, original)
    cursor.execute(
        """
MERGE dbo.recognition_rules AS target
USING (SELECT ? AS rule_scope, ? AS reason_code) AS source
ON target.rule_scope = source.rule_scope AND target.reason_code = source.reason_code
WHEN MATCHED THEN
    UPDATE SET target_label = ?, target_subtype = ?, required_any_json = ?, signals_json = ?,
               minimum_score = ?, is_active = 1, updated_at_utc = SYSUTCDATETIME()
WHEN NOT MATCHED THEN
    INSERT (rule_id, rule_scope, target_label, target_subtype, reason_code, required_any_json, signals_json, minimum_score, is_system, is_active)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 1);
""",
        scope,
        reason_code,
        target_label_key,
        target_subtype_key,
        json.dumps(_clean_values(required_any)),
        json.dumps(_clean_values(signals)),
        minimum_score,
        f"{scope}:{reason_code}",
        scope,
        target_label_key,
        target_subtype_key,
        reason_code,
        json.dumps(_clean_values(required_any)),
        json.dumps(_clean_values(signals)),
        minimum_score,
    )
    connection.commit()


def delete_rule(connection: Any, *, scope: str, reason_code: str) -> None:
    scope = _scope(scope, RULE_SCOPES)
    reason_code = reason_code.strip().upper()
    if not reason_code:
        raise ValueError("Rule reason cannot be blank.")
    cursor = connection.cursor()
    cursor.execute(
        """
UPDATE dbo.recognition_rules
SET is_active = 0, updated_at_utc = SYSUTCDATETIME()
WHERE rule_scope = ? AND reason_code = ?;
""",
        scope,
        reason_code,
    )
    connection.commit()


def review_suggestion(
    connection: Any,
    *,
    suggestion_id: str,
    action: str,
    admin_user_id: str | None = None,
    review_note: str | None = None,
) -> dict[str, Any]:
    action = action.strip().lower()
    if action not in SUGGESTION_ACTIONS:
        raise ValueError("Unsupported suggestion review action.")
    cursor = connection.cursor()
    suggestion = _suggestion(cursor, suggestion_id)
    if not suggestion:
        raise ValueError("Recognition suggestion was not found.")
    current_status = str(suggestion.get("suggestion_status") or "").strip().lower()
    if current_status in {"approved", "rejected"}:
        return {
            "status": current_status,
            "suggestion_id": suggestion_id,
            "already_reviewed": True,
            "message": f"Recognition suggestion was already {current_status}.",
            "updated_documents": 0,
            "updated_transactions": 0,
        }
    if action == "reject":
        _mark_suggestion_reviewed(
            cursor,
            suggestion_id,
            status="rejected",
            admin_user_id=admin_user_id,
            action="rejected",
            review_note=review_note,
        )
        _record_config_change(cursor, suggestion_id, admin_user_id, "reject_suggestion", review_note)
        connection.commit()
        return {"status": "rejected", "suggestion_id": suggestion_id, "updated_documents": 0, "updated_transactions": 0}

    updated_transactions = 0
    updated_documents = 0
    if suggestion.get("suggested_document_type"):
        _upsert_label_value(
            cursor,
            "document",
            str(suggestion["suggested_document_type"]),
            str(suggestion.get("suggested_document_subtype") or "unknown"),
        )
        updated_documents += _apply_document_label(
            cursor,
            suggestion_id,
            str(suggestion["suggested_document_type"]),
        )
    if suggestion.get("suggested_transaction_type"):
        _upsert_label_value(
            cursor,
            "transaction",
            str(suggestion["suggested_transaction_type"]),
            str(suggestion.get("suggested_transaction_subtype") or "unknown"),
        )
        updated_transactions += _apply_transaction_label(
            cursor,
            suggestion_id,
            "transaction_type",
            str(suggestion["suggested_transaction_type"]),
            fallback_values={"unknown"},
        )
        updated_transactions += _apply_transaction_label(
            cursor,
            suggestion_id,
            "transaction_subtype",
            str(suggestion.get("suggested_transaction_subtype") or "unknown"),
            fallback_values={"unknown"},
        )
    if suggestion.get("suggested_spending_category"):
        _upsert_label_value(
            cursor,
            "spending",
            str(suggestion["suggested_spending_category"]),
            str(suggestion.get("suggested_spending_subcategory") or "unknown"),
        )
        updated_transactions += _apply_transaction_label(
            cursor,
            suggestion_id,
            "spending_category",
            str(suggestion["suggested_spending_category"]),
            fallback_values={"uncategorized", "unknown"},
        )
        updated_transactions += _apply_transaction_label(
            cursor,
            suggestion_id,
            "spending_subcategory",
            str(suggestion.get("suggested_spending_subcategory") or "unknown"),
            fallback_values={"unknown"},
        )
    cursor.execute(
        """
UPDATE dbo.transactions
SET recognition_suggestion_status = ?
WHERE recognition_suggestion_id = ?;
""",
        "approved",
        suggestion_id,
    )
    _mark_suggestion_reviewed(
        cursor,
        suggestion_id,
        status="approved",
        admin_user_id=admin_user_id,
        action="approved",
        review_note=review_note,
    )
    config_change_id = _record_config_change(cursor, suggestion_id, admin_user_id, "approve_suggestion", review_note)
    _record_sync_run(cursor, config_change_id, updated_documents + updated_transactions)
    connection.commit()
    return {
        "status": "approved",
        "suggestion_id": suggestion_id,
        "updated_documents": updated_documents,
        "updated_transactions": updated_transactions,
    }


def seed_recognition_settings_if_empty(connection: Any) -> None:
    cursor = connection.cursor()
    seed_labels = not _table_has_rows(cursor, "dbo.recognition_labels")
    seed_rules = not _table_has_rows(cursor, "dbo.recognition_rules")
    if not seed_labels and not seed_rules:
        return

    settings = _seed_payload()
    if seed_labels:
        for scope, vocabulary in (
            ("document", settings["document_vocabulary"]),
            ("transaction", settings["transaction_vocabulary"]),
            ("spending", settings["spending_vocabulary"]),
        ):
            subtype_key = {
                "document": "document_subtypes",
                "transaction": "transaction_subtypes",
                "spending": "spending_subcategories",
            }[scope]
            for label, values in vocabulary.get(subtype_key, {}).items():
                key = _normalize(label)
                _seed_label(
                    cursor,
                    f"{scope}:{key}",
                    scope,
                    key,
                    _display(key),
                    json.dumps(_normalize_values(values, "uncategorized" if scope == "spending" else "unknown")),
                )
    if seed_rules:
        for scope, rule_payload in (
            ("document", settings["document_rules"]),
            ("transaction", settings["transaction_rules"]),
            ("spending", settings["spending_rules"]),
        ):
            label_key = {
                "document": "document_type",
                "transaction": "transaction_type",
                "spending": "spending_category",
            }[scope]
            subtype_key = {
                "document": "document_subtype",
                "transaction": "transaction_subtype",
                "spending": "spending_subcategory",
            }[scope]
            for rule in rule_payload.get("rules", []):
                reason_code = str(rule.get("reason_code") or f"{scope.upper()}_RULE").upper()
                _seed_rule(
                    cursor,
                    f"{scope}:{reason_code}",
                    scope,
                    _normalize(str(rule.get(label_key) or "unknown")),
                    _normalize(str(rule.get(subtype_key) or "unknown")),
                    reason_code,
                    json.dumps(_clean_values(rule.get("required_any", []))),
                    json.dumps(_clean_values(rule.get("signals", []))),
                    float(rule.get("minimum_score") or 0.35),
                )
    connection.commit()


def _table_has_rows(cursor: Any, table_name: str) -> bool:
    cursor.execute(f"SELECT TOP (1) 1 FROM {table_name};")
    return cursor.fetchone() is not None


def _seed_label(
    cursor: Any,
    label_id: str,
    scope: str,
    key: str,
    display_label: str,
    values_json: str,
) -> None:
    cursor.execute(
        """
MERGE dbo.recognition_labels WITH (HOLDLOCK) AS target
USING (SELECT ? AS label_id) AS source
ON target.label_id = source.label_id
WHEN NOT MATCHED THEN
    INSERT (label_id, label_scope, label_key, display_label, values_json, is_system, is_active)
    VALUES (?, ?, ?, ?, ?, 1, 1);
""",
        label_id,
        label_id,
        scope,
        key,
        display_label,
        values_json,
    )


def _seed_rule(
    cursor: Any,
    rule_id: str,
    scope: str,
    target_label: str,
    target_subtype: str,
    reason_code: str,
    required_any_json: str,
    signals_json: str,
    minimum_score: float,
) -> None:
    cursor.execute(
        """
MERGE dbo.recognition_rules WITH (HOLDLOCK) AS target
USING (SELECT ? AS rule_id) AS source
ON target.rule_id = source.rule_id
WHEN NOT MATCHED THEN
    INSERT (rule_id, rule_scope, target_label, target_subtype, reason_code, required_any_json, signals_json, minimum_score, is_system, is_active)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 1);
""",
        rule_id,
        rule_id,
        scope,
        target_label,
        target_subtype,
        reason_code,
        required_any_json,
        signals_json,
        minimum_score,
    )


def _load_labels(connection: Any) -> dict[str, dict[str, list[str]]]:
    cursor = connection.cursor()
    cursor.execute(
        """
SELECT label_scope, label_key, values_json
FROM dbo.recognition_labels
WHERE is_active = 1
ORDER BY label_key;
"""
    )
    labels: dict[str, dict[str, list[str]]] = {scope: {} for scope in LABEL_SCOPES}
    for row in cursor.fetchall():
        labels[str(row[0])][str(row[1])] = json.loads(str(row[2] or "[]"))
    return labels


def _load_rules(connection: Any) -> dict[str, list[dict[str, Any]]]:
    cursor = connection.cursor()
    cursor.execute(
        """
SELECT rule_scope, target_label, target_subtype, reason_code, required_any_json, signals_json, minimum_score
FROM dbo.recognition_rules
WHERE is_active = 1
ORDER BY rule_scope, target_label, target_subtype, reason_code;
"""
    )
    rules: dict[str, list[dict[str, Any]]] = {scope: [] for scope in RULE_SCOPES}
    for row in cursor.fetchall():
        scope = str(row[0])
        label_field = {"document": "document_type", "transaction": "transaction_type", "spending": "spending_category"}[scope]
        subtype_field = {"document": "document_subtype", "transaction": "transaction_subtype", "spending": "spending_subcategory"}[scope]
        rules[scope].append(
            {
                label_field: str(row[1]),
                subtype_field: str(row[2]),
                "reason_code": str(row[3]),
                "required_any": json.loads(str(row[4] or "[]")),
                "signals": json.loads(str(row[5] or "[]")),
                "minimum_score": float(row[6]),
            }
        )
    return rules


def _vocabulary(labels: dict[str, dict[str, list[str]]], scope: str, labels_key: str, subtypes_key: str) -> dict[str, Any]:
    scoped = labels.get(scope, {})
    keys = sorted(scoped, key=lambda value: "zzzz" if value in {"unknown", "uncategorized"} else value)
    return {labels_key: keys, subtypes_key: scoped}


def _seed_payload() -> dict[str, Any]:
    root = Path(os.environ.get("STATS_APP_ROOT") or Path.cwd())
    config = root / "config"
    return {
        "document_vocabulary": _json(config / "document-classification.vocabulary.json", {"document_types": ["unknown"], "document_subtypes": {"unknown": ["unknown"]}}),
        "document_rules": _json(config / "document-classification.rules.json", {"rules": []}),
        "transaction_vocabulary": _json(config / "transaction-classification.vocabulary.json", {"transaction_types": ["unknown"], "transaction_subtypes": {"unknown": ["unknown"]}}),
        "transaction_rules": _json(config / "transaction-classification.rules.json", {"rules": []}),
        "spending_vocabulary": _json(config / "spending-category.vocabulary.json", {"spending_categories": ["uncategorized"], "spending_subcategories": {"uncategorized": ["unknown"]}}),
        "spending_rules": _json(config / "spending-category.rules.json", {"rules": []}),
    }


def _json(path: Path, fallback: dict[str, Any]) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


def _rename_rule_targets(cursor: Any, scope: str, old_key: str, next_key: str) -> None:
    cursor.execute(
        """
UPDATE dbo.recognition_rules
SET target_label = ?, updated_at_utc = SYSUTCDATETIME()
WHERE rule_scope = ? AND target_label = ?;
""",
        next_key,
        scope,
        old_key,
    )


def _ensure_label_value(connection: Any, scope: str, label: str, subtype: str) -> None:
    cursor = connection.cursor()
    cursor.execute(
        "SELECT values_json FROM dbo.recognition_labels WHERE label_scope = ? AND label_key = ? AND is_active = 1;",
        scope,
        label,
    )
    row = cursor.fetchone()
    if not row:
        raise ValueError("Rule target label does not exist.")
    values = json.loads(str(row[0] or "[]"))
    if subtype not in values:
        values.append(subtype)
        cursor.execute(
            "UPDATE dbo.recognition_labels SET values_json = ?, updated_at_utc = SYSUTCDATETIME() WHERE label_scope = ? AND label_key = ?;",
            json.dumps(values),
            scope,
            label,
        )


def _suggestion(cursor: Any, suggestion_id: str) -> dict[str, Any] | None:
    cursor.execute(
        """
SELECT suggestion_id, suggestion_status, suggested_document_type, suggested_document_subtype,
       suggested_transaction_type, suggested_transaction_subtype,
       suggested_spending_category, suggested_spending_subcategory
FROM dbo.recognition_label_suggestions
WHERE suggestion_id = ?;
""",
        suggestion_id,
    )
    row = cursor.fetchone()
    if not row:
        return None
    return {
        "suggestion_id": str(row[0]),
        "suggestion_status": _text(row[1]),
        "suggested_document_type": _text(row[2]),
        "suggested_document_subtype": _text(row[3]),
        "suggested_transaction_type": _text(row[4]),
        "suggested_transaction_subtype": _text(row[5]),
        "suggested_spending_category": _text(row[6]),
        "suggested_spending_subcategory": _text(row[7]),
    }


def _upsert_label_value(cursor: Any, scope: str, label: str, subtype: str) -> None:
    key = _normalize(label)
    subtype_key = _normalize(subtype)
    cursor.execute(
        "SELECT values_json FROM dbo.recognition_labels WHERE label_scope = ? AND label_key = ?;",
        scope,
        key,
    )
    row = cursor.fetchone()
    if row:
        values = json.loads(str(row[0] or "[]"))
        if subtype_key not in values:
            values.append(subtype_key)
        cursor.execute(
            """
UPDATE dbo.recognition_labels
SET values_json = ?, is_active = 1, updated_at_utc = SYSUTCDATETIME()
WHERE label_scope = ? AND label_key = ?;
""",
            json.dumps(_normalize_values(values, "uncategorized" if scope == "spending" else "unknown")),
            scope,
            key,
        )
        return
    cursor.execute(
        """
INSERT INTO dbo.recognition_labels (label_id, label_scope, label_key, display_label, values_json, is_system, is_active)
VALUES (?, ?, ?, ?, ?, 0, 1);
""",
        f"{scope}:{key}",
        scope,
        key,
        _display(key),
        json.dumps(_normalize_values([subtype_key], "uncategorized" if scope == "spending" else "unknown")),
    )


def _apply_transaction_label(
    cursor: Any,
    suggestion_id: str,
    field_name: str,
    value: str,
    *,
    fallback_values: set[str],
) -> int:
    normalized = _normalize(value)
    placeholders = ", ".join("?" for _ in fallback_values)
    cursor.execute(
        f"""
UPDATE dbo.transactions
SET {field_name} = ?
WHERE recognition_suggestion_id = ?
  AND LOWER({field_name}) IN ({placeholders});
""",
        normalized,
        suggestion_id,
        *sorted(fallback_values),
    )
    return max(int(getattr(cursor, "rowcount", 0) or 0), 0)


def _apply_document_label(cursor: Any, suggestion_id: str, value: str) -> int:
    normalized = _normalize(value)
    cursor.execute(
        """
UPDATE dbo.stats_documents
SET document_type = ?,
    recognition_suggestion_status = ?,
    updated_at_utc = SYSUTCDATETIME()
WHERE recognition_suggestion_id = ?
  AND LOWER(COALESCE(document_type, 'unknown')) = 'unknown';
""",
        normalized,
        "approved",
        suggestion_id,
    )
    document_count = max(int(getattr(cursor, "rowcount", 0) or 0), 0)
    cursor.execute(
        """
UPDATE dbo.validation_results
SET document_type = ?
WHERE validation_result_id IN (
    SELECT validation_result_id
    FROM dbo.stats_documents
    WHERE recognition_suggestion_id = ?
)
  AND LOWER(COALESCE(document_type, 'unknown')) = 'unknown';
""",
        normalized,
        suggestion_id,
    )
    validation_count = max(int(getattr(cursor, "rowcount", 0) or 0), 0)
    return document_count + validation_count


def _mark_suggestion_reviewed(
    cursor: Any,
    suggestion_id: str,
    *,
    status: str,
    admin_user_id: str | None,
    action: str,
    review_note: str | None,
) -> None:
    cursor.execute(
        """
UPDATE dbo.recognition_label_suggestions
SET suggestion_status = ?,
    reviewed_at_utc = SYSUTCDATETIME(),
    reviewed_by_user_id = ?,
    review_action = ?,
    review_note = ?
WHERE suggestion_id = ?;
""",
        status,
        admin_user_id,
        action,
        review_note,
        suggestion_id,
    )


def _record_config_change(
    cursor: Any,
    suggestion_id: str,
    admin_user_id: str | None,
    action_type: str,
    review_note: str | None,
) -> str:
    config_change_id = f"config_change_{uuid.uuid4().hex[:24]}"
    cursor.execute(
        """
INSERT INTO dbo.recognition_config_changes
    (config_change_id, suggestion_id, admin_user_id, action_type, config_file, change_reason)
VALUES (?, ?, ?, ?, ?, ?);
""",
        config_change_id,
        suggestion_id,
        admin_user_id,
        action_type,
        "database:recognition_labels",
        review_note,
    )
    return config_change_id


def _record_sync_run(cursor: Any, config_change_id: str, affected_row_count: int) -> None:
    cursor.execute(
        """
INSERT INTO dbo.recognition_label_sync_runs
    (sync_run_id, config_change_id, sync_policy, label_field, affected_row_count, status, completed_at_utc)
VALUES (?, ?, ?, ?, ?, ?, SYSUTCDATETIME());
""",
        f"sync_{uuid.uuid4().hex[:24]}",
        config_change_id,
        "apply_to_unknown_records",
        "recognition_suggestion_id",
        affected_row_count,
        "completed",
    )


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _scope(value: str, allowed: set[str]) -> str:
    normalized = value.strip().lower()
    if normalized not in allowed:
        raise ValueError("Unsupported recognition settings scope.")
    return normalized


def _normalize(value: str) -> str:
    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
    normalized = "_".join(part for part in normalized.split("_") if part)
    if not normalized:
        raise ValueError("Label cannot be blank.")
    return normalized


def _deletable_key(value: str) -> str:
    key = _normalize(value)
    if key in {"unknown", "uncategorized"}:
        raise ValueError("The fallback label cannot be deleted.")
    return key


def _normalize_values(values: list[str], default_value: str) -> list[str]:
    cleaned = _clean_values(values)
    if default_value not in cleaned:
        cleaned.append(default_value)
    return cleaned


def _clean_values(values: Any) -> list[str]:
    if isinstance(values, str):
        values = values.split(",")
    cleaned = []
    for value in values or []:
        text = _normalize(str(value))
        if text not in cleaned:
            cleaned.append(text)
    return cleaned


def _display(value: str) -> str:
    return " ".join(word.capitalize() for word in value.split("_"))
