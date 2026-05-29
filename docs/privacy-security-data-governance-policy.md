<!-- M0 Foundation Start -->
<!-- Formalizes privacy, security, and data-governance expectations for financial document processing. -->

# Privacy, Security, and Data Governance Policy

## Purpose

Stats processes sensitive financial material: uploaded statements, receipts, invoices, bills, OCR text, extracted financial candidates, user accounts, screenshots, logs, and assessment evidence. The project must therefore show that data protection has been considered from the beginning of development, not added after the MVP.

This policy does not claim that the Capstone MVP is ISO 27001, SOC 2, PCI DSS, or production-certified. Instead, it documents the practical privacy and security controls expected during development and identifies what would be required before production deployment.

## Core Principle

Privacy, security, and data governance must be designed into the build loop.

Every module that handles users, files, OCR text, transactions, logs, screenshots, evidence, database records, container runtime settings, or cloud configuration must state how sensitive data is controlled.

## Data Classification

| Data Type | Sensitivity | Examples | Handling Rule |
| --- | --- | --- | --- |
| User identity data | Sensitive | Email, full name, role, password hash, token claims | Store only through the identity module and database; never commit credentials or tokens. |
| Authentication secrets | Secret | JWT signing keys, admin passwords, database passwords | Use environment variables, ignored `.env` files, or future managed secret providers. |
| Financial source documents | Highly sensitive | PDFs, bank statements, receipts, invoices, bills, email attachments | Keep under ignored local fixture/runtime folders; never commit real files to GitHub. |
| OCR text | Highly sensitive | Raw extracted text from statements or receipts | Avoid storing full raw text in assessment evidence; use redacted previews and metadata. |
| Extracted financial data | Sensitive | Amounts, merchants, dates, account-like references, transaction candidates | Treat as financial data; persist only through the Stats Data module when that module exists. |
| Evidence screenshots | Potentially sensitive | Browser output, JSON views, terminal output | Capture only what is needed and avoid exposing full personal financial details. |
| Logs and raw outputs | Potentially sensitive | API responses, parse summaries, container logs | Keep under `tests/results`; redact or summarize sensitive values when used in reports. |
| Local paths | Private developer data | Machine-specific folders, Google Drive paths | Store in ignored local config only; do not hardcode or commit personal paths. |

## Source Control Rules

The repository must not commit:

- Real financial documents.
- Raw private TestData folders.
- `.env` files.
- `*.local.json` config overrides.
- Real credentials, access tokens, API keys, or database passwords.
- Full unredacted OCR extracts from personal financial documents.
- Machine-specific private paths.

Safe examples and defaults may be committed only when they contain no real secrets or personal data.

## Fixture And Evidence Rules

Approved real-data fixtures belong under:

```text
tests/input/
```

The real fixture files are local and ignored. The folder exists so Docker and evidence scripts have a stable configured input location without depending on a private host path.

Evidence belongs under:

```text
tests/results/
```

Evidence must prefer:

- Redacted previews.
- Counts and metadata.
- Document type, strategy, confidence, elapsed time, and finding codes.
- JSON summaries that avoid full raw financial text.
- Browser screenshots that prove behavior without unnecessarily exposing private values.

## Runtime Configuration And Secrets

Runtime values must come from configuration or environment providers, not source-code literals.

This includes:

- Database URLs and passwords.
- JWT/token secrets.
- Ports and service URLs.
- File storage roots.
- Test fixture directories.
- OCR engine paths.
- Tesseract and tessdata paths.
- Cloud resource names.
- Feature switches.

Committed defaults may be used for local development only when they are clearly non-production and contain no real secrets.

## Access Control

Stats uses the Identity Access Module to separate authentication and authorization from the rest of the product.

Current access-control expectations:

- Users must authenticate before using protected Stats Web screens.
- Administrator functions must require an administrator role.
- Password handling belongs to the identity module, not Stats Web presentation code.
- Token creation and validation belong to the identity module.
- Other modules should rely on explicit identity or workflow contracts rather than implementing their own user logic.

Future production work should add more complete authorization around document ownership, workflow records, and reporting access.

## Module Data Boundaries

Each module should touch only the data it needs:

| Module Area | Data Boundary |
| --- | --- |
| Stats Web | Presents user flows and calls APIs; should not implement OCR, parsing, password hashing, or persistence internals. |
| Identity Access | Owns users, roles, password hashes, and tokens. |
| File Validation and Ingestion | Owns file accept/reject checks, file metadata, hashes, and ingestion handoff. |
| Document Parsing | Owns OCR/direct text extraction, classification, quality metadata, and redacted preview behavior. |
| Transaction Extraction | Consumes M5 parse results and returns candidates; does not rerun OCR or persist Stats records. |
| Stats Data and Persistence | Will own project-specific schema, persistence, and retrieval. |
| M13 Containerization | Packages runtime dependencies and exposes configuration; does not own business data rules. |

This boundary reduces unnecessary spread of sensitive data across the codebase.

## Container And Runtime Security

M13 containerization supports privacy and security by making runtime behavior reproducible.

Container expectations:

- Tesseract and OCR dependencies are installed inside the image rather than assumed on a developer laptop.
- Runtime values are supplied through Compose environment files or environment variables.
- Secrets are not baked into Docker images.
- Logs go to container stdout/stderr so they can later be captured by cloud logging.
- Health checks prove service readiness without exposing sensitive document contents.
- `tests/input` is the controlled local fixture source for acceptance evidence.

## Cloud Readiness Boundary

M14 Cloud Readiness remains deferred until the MVP is stable. When M14 begins, this policy should be extended to cover:

- Cloud secret management, such as Azure Key Vault.
- Managed database security.
- Storage encryption and access policies.
- TLS and custom domains.
- Backup, retention, and deletion rules.
- Audit logging.
- Vulnerability scanning.
- Container registry access control.
- Monitoring and alerting.
- Privacy notice and user-facing data handling statements.

## Production Gap Statement

The Capstone MVP is a development and assessment system, not a certified production financial platform.

Before production use, Stats would need:

- Formal threat modelling.
- Security review.
- Dependency vulnerability scanning.
- Strong secret rotation.
- Encrypted storage policy.
- Document retention and deletion policy.
- Audit logs for document access and admin actions.
- Role-based access over stored documents.
- Privacy policy reviewed against applicable law.
- Incident response and backup/recovery procedures.
- Review against relevant compliance expectations such as ISO 27001, SOC 2, PCI DSS, or local privacy law where applicable.

## WIP Report Rationale

This policy captures a key engineering decision made during development: the project should show that financial data, OCR text, user credentials, evidence artefacts, and runtime secrets have been considered intentionally. The MVP does not claim enterprise certification, but it avoids the common failure mode of fast-built apps that ignore privacy, security, and data handling until after implementation.

<!-- M0 Foundation End -->
