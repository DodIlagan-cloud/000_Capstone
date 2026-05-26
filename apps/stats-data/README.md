# Stats Data and Persistence

<!-- M0 Foundation: target owner folder for Stats-specific persistence. -->

This folder is the target home for the Stats product database schema, migrations, persistence adapters, and query layer.

Future Stats Data work should define its schema, migrations, persistence adapters, and configuration samples directly here.

Stats Data stores outputs from reusable modules for this product. It is not a reusable OCR, validation, extraction, or identity processing module.

<!-- M3/M4 - File Intake Module Start -->
<!-- Documents the Stats-owned default intake storage path used by the merged File Validation and Ingestion Module. -->

## Document Intake Data

The merged M3/M4 file intake service stores accepted intake files under the configured `STORAGE_ROOT` path:

```text
<STORAGE_ROOT>/<ingestion_id>/<normalized_filename>
```

The reusable module owns the ingestion behavior and record shape. The stored document content is treated as common Stats app data, and the concrete directory is supplied through configuration rather than hardcoded in module code.

<!-- M3/M4 End -->
