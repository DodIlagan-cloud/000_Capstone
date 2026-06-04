# Document Classification Contract

M5 owns document classification after text has been extracted from direct PDF text, scanned-PDF OCR, or image OCR.

The shared vocabulary and rule files are:

- `config/document-classification.vocabulary.json`
- `config/document-classification.rules.json`

M5 applies these files and returns `document_type`, `document_subtype`, confidence, status, reason codes, and diagnostic scores. M7 may use the result as an extraction hint. M8 preserves downstream candidate quality and does not classify documents. M9 later stores selected type/subtype values. M11 may filter and report by those stored values.

Runtime uploads must not mutate the vocabulary or rules. Unknown document shapes should be classified as `unknown / unknown` with evidence and findings so a later developer-reviewed iteration can update the JSON files and tests.
