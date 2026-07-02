"""M12 - Email Ingestion Module Start.

Automated pipeline sub-package: headless orchestration that takes one ingested
document (parse -> extract -> validate -> process-to-database) by calling the
existing Stats module APIs. Folded into M12 so the Email Ingestion Module owns
the full email-to-database path. It does not modify the manual Upload flow; it
only consumes the same stable HTTP contracts. M12 End.
"""
