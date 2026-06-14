# Document Classification Contract

M5 owns document classification after text has been extracted from direct PDF text, scanned-PDF OCR, or image OCR.

The active document recognition source of truth is M9 database-backed recognition settings. Historical JSON files may be kept only as migration seed/reference material and must not be used as a silent runtime fallback once M9 recognition settings are enabled.

M5 loads active approved document types, subtypes, aliases, rules, deprecation hints, and merge hints from M9 before classifying a document. M5 applies these settings and returns `document_type`, `document_subtype`, confidence, status, reason codes, and diagnostic scores. M7 may use the result as an extraction hint. M8 preserves downstream candidate quality and does not classify documents. M9 stores selected type/subtype values. M11 may filter and report by those stored values.

When AI-assisted document classification is enabled, M5 must provide the AI only bounded active recognition context and redacted extracted text. The AI must be instructed to choose an existing active document type/subtype when one fits and to propose a new label only when the document evidence does not map safely to active vocabulary.

Runtime uploads must not silently mutate vocabulary or rules. In the MVP manual Upload flow, a user-reviewed accepted AI suggestion is the human confirmation step; M9 persists the accepted document classification and activates any new document type/subtype during save with audit metadata. For post-MVP email ingestion, automated workflows, or other unreviewed paths, unknown or new document shapes remain pending admin governance through `/Admin/Classifications`.
