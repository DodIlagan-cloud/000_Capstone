<!-- Stats Overall Schematic Start -->

# Stats App Overall Schematic

Use this page-friendly image for Word documents:

![Stats app overall schematic](assets/stats-app-overall-schematic-word.png)

## Diagram Summary

The Stats app is built as a container-first system. Users enter through the Stats Web shell, then manual uploads and email attachments flow through reusable processing modules: validation/intake, document parsing/OCR, transaction extraction, data validation, and Stats Data persistence. Azure SQL is the operational store, Blob Storage is the durable file target, Key Vault/App Secrets protect sensitive configuration, Log Analytics supports runtime evidence, and Fabric/Power BI sit downstream for analytics and reporting.

## Mermaid Source

```mermaid
flowchart LR
    User["User / Admin Browser"] --> Web["Stats Web Shell\nASP.NET Core UI + API proxy"]
    Manual["Manual Upload\nPDF / image financial documents"] --> Intake
    EmailSource["Email Source\nIMAP attachment intake"] --> Email["M12 Email Ingestion"]

    subgraph Runtime["Stats runtime container in Azure Container Apps"]
        Web --> Identity["M1 Identity Access\nusers, roles, password maintenance"]
        Web --> Email
        Web --> Intake["M3/M4 File Validation + Ingestion\nduplicate/idempotency gate"]
        Intake --> Parsing["M5 Document Parsing\nPDF text + OCR/Tesseract"]
        Parsing --> Extraction["M7 Transaction Extraction\ntransactions + financial fields"]
        Extraction --> Validation["M8 Data Validation\nnormalization + quality findings"]
        Validation --> Data["M9 Stats Data\nsave batches, jobs, queries, recognition settings"]
    end

    Email --> Intake
    Identity --> Sql["Azure SQL Database\nusers, documents, jobs, transactions, source profiles"]
    Data --> Sql
    Intake --> Blob["Azure Blob Storage\ndurable document / attachment storage target"]
    Runtime -. secrets .-> Secrets["Key Vault / Container Apps secrets"]
    Runtime -. logs .-> Logs["Log Analytics"]

    Sql --> Fabric["Microsoft Fabric\ncurated analytics layer"]
    Fabric --> PowerBI["Power BI / Stats Reports"]
    PowerBI --> Web
    Sql --> Evaluation["M15 Evaluation Evidence\naccuracy, completeness, timing, success measures"]

    AI["Optional AI provider\nadditional cost; currently deferred"] -. classification assistance .-> Parsing
    AI -. transaction assistance .-> Extraction
```

<!-- Stats Overall Schematic End -->
