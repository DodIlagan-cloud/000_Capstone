<!-- M3 - File Validation Module Start -->
<!-- Provides the swimlane activity flow for the standalone File Validation Module. -->

# M3 File Validation Module Activity Flow

## Swimlane Activity Diagram

```mermaid
flowchart TB
    subgraph Caller["Caller"]
        A["Choose or drop candidate file"]
        A2["Automatically submit for validation"]
        B["Receive validation result"]
        C{"Accepted?"}
        D["Prepare next parsing step"]
        E["Display or log rejection reasons"]
    end

    subgraph Api["File Validation API"]
        F["Receive validation request"]
        G["Read file and request policy"]
        H["Return status, metadata, findings, policy"]
    end

    subgraph Config["Configuration"]
        I["Load default policy"]
        J["Apply local or environment overrides"]
    end

    subgraph Service["Validation Service"]
        K["Normalize filename and extension"]
        L["Check size and empty content"]
        M["Detect PDF, PNG, or JPEG signature"]
        N["Check extension, type, and mismatch rules"]
        O["Compute SHA-256 when enabled"]
        P["Build metadata and findings"]
        Q{"Any error finding?"}
        R["Set rejected"]
        S["Set accepted"]
    end

    A --> A2 --> F --> G
    I --> J --> G
    G --> K --> L --> M --> N --> O --> P --> Q
    Q -- "Yes" --> R --> H
    Q -- "No" --> S --> H
    H --> B --> C
    C -- "Yes" --> D
    C -- "No" --> E
```

## Activity Summary

| Swimlane | Responsibility |
| --- | --- |
| Caller | Supplies the candidate file and consumes the accepted/rejected result. |
| File Validation API | Owns the HTTP boundary, upload parsing, policy construction, and response contract. |
| Configuration | Supplies safe runtime defaults and environment-specific overrides. |
| Validation Service | Performs reusable validation checks and produces metadata/findings. |

## Decision Outcomes

| Decision | Accepted Path | Rejected or Warning Path |
| --- | --- | --- |
| Empty file | Non-empty content continues. | `EMPTY_FILE` error. |
| File size | Size is within policy. | `FILE_TOO_LARGE` error. |
| Extension | Extension is allowed. | `MISSING_EXTENSION` or `UNSUPPORTED_EXTENSION` error. |
| Signature | Known PDF/PNG/JPEG signature when required. | `UNKNOWN_SIGNATURE` error. |
| Type policy | Detected MIME type is allowed. | `UNSUPPORTED_TYPE` error. |
| Extension/signature consistency | Extension matches detected content. | `SIGNATURE_EXTENSION_MISMATCH` error. |
| Browser content type | Matches detected content. | `CONTENT_TYPE_MISMATCH` warning. |

<!-- M3 End -->
