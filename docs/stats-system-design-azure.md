<!-- Stats System Design Start -->

# Stats System Design With Azure Resources

This diagram shows the current Stats application design as a container-first system, with Azure resources explicitly marked. The cloud-dev runtime hosts the Stats Web shell and module APIs inside one Stats runtime container; shared persistence, files, secrets, logs, and reporting integrations are externalized to Azure services.

## Word-Ready Image

Use this cleaned image with official Azure service icons for MS Word pages and presentation/report artefacts:

![Stats system design with Azure resources](assets/stats-system-design-azure-word-icons.png)

Additional exports:

- `docs/assets/stats-system-design-azure-word-icons.png`
- `docs/assets/stats-system-design-azure-word-icons.jpg`
- `docs/assets/stats-system-design-azure-word-clean.png`
- `docs/assets/stats-system-design-azure-word-clean.jpg`
- `docs/assets/stats-system-design-azure-word.png`
- `docs/assets/stats-system-design-azure-word.jpg`

## Detailed Mermaid Source

```mermaid
flowchart TB
    user["User / Admin<br/>Browser"] --> ingress["Azure Container Apps ingress<br/>HTTPS public endpoint<br/>AZURE: ca-stats-dev-001"]

    subgraph azure["Azure cloud-dev resource group"]
        ingress --> app["Azure Container App<br/>Stats runtime container<br/>AZURE: ca-stats-dev-001"]
        acr["Azure Container Registry<br/>Private image registry<br/>AZURE: acrstatsdev001"] --> app
        mi["User-assigned Managed Identity<br/>ACR pull / future resource access<br/>AZURE: id-stats-dev-acr-pull"] --> app
        kv["Key Vault / Container Apps secrets<br/>JWT, SQL, storage, email, AI, Power BI secrets<br/>AZURE: kv-stats-dev-001"]
        logs["Log Analytics workspace<br/>Container logs and cloud evidence<br/>AZURE: workspace-rgstatsdevgRlq"]
        job["Container Apps Job<br/>One-time admin bootstrap<br/>AZURE: job-stats-admin-bootstrap"]
        sql["Azure SQL Database<br/>Operational Stats store<br/>AZURE: sql-stats-dev-001 / sqldb-stats-dev"]
        blob["Azure Blob Storage<br/>Durable document / attachment intake<br/>AZURE: storage account + container"]
        fabric["Microsoft Fabric Lakehouse / Warehouse<br/>Curated analytics data<br/>AZURE/Fabric"]
        pbi["Power BI workspace / report<br/>Embedded or linked reporting<br/>AZURE/Power BI"]
    end

    subgraph runtime["Stats runtime container"]
        web["Stats Web shell<br/>ASP.NET Core Razor<br/>Port 8080"]
        identity["M1 Identity Access API<br/>FastAPI<br/>Port 8013"]
        fileValidation["M3 File Validation API<br/>FastAPI<br/>Port 8014"]
        parsing["M5 Document Parsing API<br/>FastAPI + OCR/Tesseract<br/>Port 8015"]
        extraction["M7 Transaction Extraction API<br/>FastAPI<br/>Port 8016"]
        validation["M8 Data Validation API<br/>FastAPI<br/>Port 8017"]
        statsData["M9 Stats Data API<br/>Persistence / duplicate checks / jobs<br/>Port 8018"]
        email["M12 Email Ingestion API<br/>Yahoo IMAP source profiles<br/>Port 8019"]
    end

    app --> web
    web --> identity
    web --> fileValidation
    web --> parsing
    web --> extraction
    web --> validation
    web --> statsData
    web --> email

    job --> identity
    job --> sql

    identity --> sql
    statsData --> sql
    validation --> statsData
    fileValidation --> blob
    email --> fileValidation
    email --> sql
    email --> yahoo["Yahoo Mail<br/>IMAP SSL<br/>External provider"]
    parsing --> fileValidation
    extraction --> parsing
    validation --> extraction

    web --> pbi
    statsData --> fabric
    fabric --> pbi

    app -. reads secret refs .-> kv
    job -. reads bootstrap secrets .-> kv
    app -. stdout logs .-> logs

    ai["Optional AI provider<br/>OpenAI / Gemini / compatible<br/>External provider"] -. classification assistance .-> parsing
    ai -. transaction assistance .-> extraction

    classDef azureResource fill:#e8f2ff,stroke:#2563eb,stroke-width:2px,color:#111827;
    classDef runtime fill:#f8fafc,stroke:#475569,stroke-width:1px,color:#111827;
    classDef external fill:#fff7ed,stroke:#f97316,stroke-width:1px,color:#111827;
    classDef user fill:#ecfdf5,stroke:#059669,stroke-width:1px,color:#111827;

    class ingress,app,acr,mi,kv,logs,job,sql,blob,fabric,pbi azureResource;
    class web,identity,fileValidation,parsing,extraction,validation,statsData,email runtime;
    class yahoo,ai external;
    class user user;
```

## Azure Resources Included

| Azure resource | Current Stats role |
| --- | --- |
| Azure Container Registry `acrstatsdev001` | Stores the private `stats-runtime` container image. |
| Azure Container Apps environment `cae-stats-dev-001` | Managed environment for the Stats Container App. |
| Azure Container App `ca-stats-dev-001` | Hosts Stats Web and all module APIs inside the single runtime container. |
| Azure SQL server `sql-stats-dev-001` | Logical SQL host for cloud operational persistence. |
| Azure SQL database `sqldb-stats-dev` | Stores users, documents, validation results, processing jobs, transactions, source profiles, and M12 email-ingestion settings. |
| Azure Blob Storage | Durable document and attachment intake target when `STATS_STORAGE_PROVIDER=AzureBlobStorage`. |
| Azure Key Vault `kv-stats-dev-001` / Container Apps secrets | Stores secret values and secret references for SQL, JWT, admin bootstrap, storage, email, AI, and Power BI credentials. |
| User-assigned managed identity `id-stats-dev-acr-pull` | Supports ACR image pull and future managed access to cloud resources. |
| Log Analytics workspace `workspace-rgstatsdevgRlq` | Collects Container Apps logs and supports cloud evidence review. |
| Container Apps Job `job-stats-admin-bootstrap` | Runs the one-time first-admin bootstrap flow against Azure SQL. |
| Microsoft Fabric workspace / Lakehouse | Planned/optional curated analytics layer fed from Stats operational data. |
| Power BI workspace / report | Planned/optional dashboard and reporting surface for curated Stats data. |

## Main Flows

1. Browser traffic enters through Azure Container Apps ingress and reaches Stats Web on port `8080`.
2. Stats Web calls module APIs through same-container internal proxy targets.
3. File upload and email attachment paths converge at M3 File Validation, then continue through parsing, extraction, validation, and Stats Data persistence.
4. Azure SQL is the central operational database for identity, processing jobs, document metadata, extracted/validated data, and email ingestion configuration.
5. Azure Blob Storage is the durable file store for accepted documents and attachments when cloud storage is enabled.
6. Secret values stay outside code and normal API responses through Key Vault, Container Apps secrets, and encrypted M12 secret storage.
7. Fabric and Power BI sit downstream of the operational store for analytics and reporting.

<!-- Stats System Design End -->
