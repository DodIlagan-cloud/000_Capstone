"""M5 - Document Parsing Module Start
Implements PDF text extraction, OCR fallback, classification, and evaluation metadata.
M5/M6 End"""

import hashlib
import io
import os
import time
import uuid
from pathlib import Path
from typing import Optional

from PIL import Image
from pypdf import PdfReader

from app.config import settings
from app.models.parsing import (
    DocumentParseResult,
    DocumentTrace,
    EvaluationMetadata,
    FindingSeverity,
    PageParseResult,
    ParseFinding,
    ParseMetadata,
    ParseStatus,
    QualityMetadata,
    RedactedEvidencePreview,
    StrategyDecision,
)
from app.services.classification_service import classify_document
from app.services.redaction_service import redact_text


PDF_SIGNATURE = b"%PDF"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
JPEG_SIGNATURE = b"\xff\xd8\xff"


def detect_mime_type(content: bytes, provided_content_type: Optional[str] = None) -> Optional[str]:
    if content.startswith(PDF_SIGNATURE):
        return "application/pdf"
    if content.startswith(PNG_SIGNATURE):
        return "image/png"
    if content.startswith(JPEG_SIGNATURE):
        return "image/jpeg"
    if provided_content_type:
        return provided_content_type.lower()
    return None


def normalize_filename(filename: str) -> str:
    return Path(filename or "unnamed").name or "unnamed"


def _finding(code: str, message: str, severity: FindingSeverity = FindingSeverity.error) -> ParseFinding:
    return ParseFinding(code=code, severity=severity, message=message)


def _finding_counts(findings: list[ParseFinding]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for finding in findings:
        counts[finding.code] = counts.get(finding.code, 0) + 1
    return counts


def _is_tesseract_available() -> bool:
    if settings.ocr_engine != "tesseract":
        return False

    try:
        import pytesseract

        if settings.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd
        if settings.tessdata_prefix:
            os.environ["TESSDATA_PREFIX"] = settings.tessdata_prefix
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def _is_pdf_renderer_available() -> bool:
    try:
        import fitz  # noqa: F401

        return True
    except Exception:
        return False


def get_ocr_readiness() -> dict[str, object]:
    return {
        "enabled": settings.allow_ocr_fallback,
        "engine": settings.ocr_engine,
        "languages": settings.ocr_languages,
        "tesseract_cmd": settings.tesseract_cmd,
        "tessdata_prefix": settings.tessdata_prefix,
        "tesseract_available": _is_tesseract_available(),
        "renderer": "PyMuPDF",
        "renderer_available": _is_pdf_renderer_available(),
    }


def _extract_pdf_text(content: bytes, page_limit: int) -> tuple[str, list[PageParseResult], int]:
    reader = PdfReader(io.BytesIO(content))
    page_count = len(reader.pages)
    pages: list[PageParseResult] = []
    extracted_parts: list[str] = []

    for page_number, page in enumerate(reader.pages[:page_limit], start=1):
        page_text = page.extract_text() or ""
        normalized_page_text = page_text.strip()
        pages.append(
            PageParseResult(
                page_number=page_number,
                text=normalized_page_text,
                text_length=len(normalized_page_text),
                empty=not bool(normalized_page_text),
            )
        )
        if normalized_page_text:
            extracted_parts.append(normalized_page_text)

    return "\n".join(extracted_parts), pages, page_count


def _ocr_image(image: Image.Image, language: str) -> str:
    import pytesseract

    if settings.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd
    if settings.tessdata_prefix:
        os.environ["TESSDATA_PREFIX"] = settings.tessdata_prefix

    return pytesseract.image_to_string(image, lang=language).strip()


def _ocr_image_content(content: bytes, language: str) -> tuple[str, list[PageParseResult], int]:
    with Image.open(io.BytesIO(content)) as image:
        text = _ocr_image(image, language)

    return (
        text,
        [PageParseResult(page_number=1, text=text, text_length=len(text), empty=not bool(text.strip()))],
        1,
    )


def _ocr_pdf_pages(content: bytes, page_limit: int, language: str) -> tuple[str, list[PageParseResult], int]:
    import fitz

    document = fitz.open(stream=content, filetype="pdf")
    page_count = document.page_count
    pages: list[PageParseResult] = []
    extracted_parts: list[str] = []
    matrix = fitz.Matrix(2.0, 2.0)

    try:
        for page_number in range(1, min(page_count, page_limit) + 1):
            page = document.load_page(page_number - 1)
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            image = Image.open(io.BytesIO(pixmap.tobytes("png")))
            page_text = _ocr_image(image, language)
            pages.append(
                PageParseResult(
                    page_number=page_number,
                    text=page_text,
                    text_length=len(page_text),
                    empty=not bool(page_text.strip()),
                )
            )
            if page_text:
                extracted_parts.append(page_text)
    finally:
        document.close()

    return "\n".join(extracted_parts), pages, page_count


def parse_document_content(
    content: bytes,
    filename: str,
    provided_content_type: Optional[str] = None,
    ingestion_id: Optional[str] = None,
    source_type: Optional[str] = None,
    source_id: Optional[str] = None,
    sha256: Optional[str] = None,
    allow_direct_text: Optional[bool] = None,
    allow_ocr_fallback: Optional[bool] = None,
    language: Optional[str] = None,
    page_limit: Optional[int] = None,
    classification_threshold: Optional[float] = None,
) -> DocumentParseResult:
    started = time.perf_counter()
    findings: list[ParseFinding] = []
    normalized_filename = normalize_filename(filename)
    detected_mime_type = detect_mime_type(content, provided_content_type)
    document_hash = sha256 or hashlib.sha256(content).hexdigest()
    document_id = ingestion_id or document_hash[:16]
    effective_allow_direct_text = settings.allow_direct_text if allow_direct_text is None else allow_direct_text
    effective_allow_ocr_fallback = settings.allow_ocr_fallback if allow_ocr_fallback is None else allow_ocr_fallback
    effective_language = language or (settings.ocr_languages[0] if settings.ocr_languages else "eng")
    effective_page_limit = page_limit or settings.max_page_count
    effective_threshold = classification_threshold if classification_threshold is not None else settings.classification_confidence_threshold
    tesseract_available = _is_tesseract_available()
    renderer_available = _is_pdf_renderer_available()
    text = ""
    pages: list[PageParseResult] = []
    page_count = 0
    extraction_method = "none"
    selected_strategy = "failed"
    strategy_reason = "Parsing did not run."
    direct_text_attempted = False
    ocr_attempted = False

    if not content:
        findings.append(_finding("MISSING_DOCUMENT", "No document content was supplied."))
    elif settings.max_document_size_bytes > 0 and len(content) > settings.max_document_size_bytes:
        findings.append(_finding("DOCUMENT_TOO_LARGE", "Document exceeds the configured maximum size."))
    elif detected_mime_type not in settings.supported_mime_types:
        findings.append(_finding("UNSUPPORTED_MEDIA_TYPE", "Document type is not supported by parsing policy."))

    if not any(finding.severity == FindingSeverity.error for finding in findings):
        if detected_mime_type == "application/pdf":
            if effective_allow_direct_text:
                direct_text_attempted = True
                try:
                    text, pages, page_count = _extract_pdf_text(content, effective_page_limit)
                    extraction_method = "direct_pdf_text"
                    selected_strategy = "pdf_text"
                    strategy_reason = "PDF text extraction selected for PDF input."
                    if page_count > effective_page_limit:
                        findings.append(
                            _finding(
                                "PAGE_LIMIT_APPLIED",
                                "Extraction processed only the configured maximum number of pages.",
                                FindingSeverity.warning,
                            )
                        )
                except Exception:
                    findings.append(_finding("UNREADABLE_DOCUMENT", "The PDF could not be opened or parsed."))
            else:
                findings.append(_finding("DIRECT_TEXT_DISABLED", "Direct PDF text extraction is disabled.", FindingSeverity.warning))

            if len(text.strip()) < settings.min_text_length:
                if effective_allow_ocr_fallback:
                    ocr_attempted = True
                    selected_strategy = "tesseract_ocr"
                    strategy_reason = "PDF had insufficient embedded text; OCR fallback was selected."
                    extraction_method = "ocr"
                    if not tesseract_available:
                        findings.append(_finding("TESSERACT_UNAVAILABLE", "Tesseract OCR was needed but is unavailable."))
                    elif not renderer_available:
                        findings.append(_finding("PDF_RENDERER_UNAVAILABLE", "PDF OCR was needed but PyMuPDF rendering is unavailable."))
                    else:
                        try:
                            text, pages, page_count = _ocr_pdf_pages(content, effective_page_limit, effective_language)
                        except Exception:
                            findings.append(_finding("OCR_FAILED", "Tesseract OCR could not process the PDF."))
                else:
                    findings.append(
                        _finding(
                            "OCR_FALLBACK_DISABLED",
                            "PDF had insufficient embedded text and OCR fallback is disabled.",
                            FindingSeverity.warning,
                        )
                    )
        elif detected_mime_type in {"image/png", "image/jpeg"}:
            if effective_allow_ocr_fallback:
                ocr_attempted = True
                selected_strategy = "tesseract_ocr"
                strategy_reason = "Image input requires OCR."
                extraction_method = "ocr"
                if not tesseract_available:
                    findings.append(_finding("TESSERACT_UNAVAILABLE", "Tesseract OCR was needed but is unavailable."))
                else:
                    try:
                        text, pages, page_count = _ocr_image_content(content, effective_language)
                    except Exception:
                        findings.append(_finding("OCR_FAILED", "Tesseract OCR could not process the image."))
            else:
                selected_strategy = "ocr_disabled"
                strategy_reason = "Image input requires OCR but fallback is disabled."
                findings.append(_finding("OCR_FALLBACK_DISABLED", "Image input requires OCR and OCR fallback is disabled."))

    if text and len(text.strip()) < settings.min_text_length:
        findings.append(_finding("LOW_TEXT_QUALITY", "Extracted text is below the configured minimum text threshold.", FindingSeverity.warning))
    elif not text and not any(finding.severity == FindingSeverity.error for finding in findings):
        findings.append(_finding("NO_TEXT_EXTRACTED", "Parsing completed without usable extracted text.", FindingSeverity.warning))

    classification = classify_document(
        text=text,
        supported_document_types=settings.supported_document_types,
        confidence_threshold=effective_threshold,
        allow_unknown=settings.classification_allow_unknown,
    )
    if classification.status == "unknown":
        findings.append(_finding("CLASSIFICATION_UNKNOWN", "Document could not be classified above the configured confidence threshold.", FindingSeverity.warning))
    elif classification.status == "ambiguous":
        findings.append(_finding("CLASSIFICATION_AMBIGUOUS", "Multiple document classes were plausible.", FindingSeverity.warning))
    elif classification.status == "unsupported":
        findings.append(_finding("UNSUPPORTED_DOCUMENT_CLASS", "No supported document classes were configured."))

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    has_error = any(finding.severity == FindingSeverity.error for finding in findings)
    has_warning = any(finding.severity == FindingSeverity.warning for finding in findings)
    if detected_mime_type not in settings.supported_mime_types:
        status = ParseStatus.unsupported
    elif has_error:
        status = ParseStatus.failed
    elif has_warning:
        status = ParseStatus.completed_with_warnings
    else:
        status = ParseStatus.completed

    empty_page_count = sum(1 for page in pages if page.empty)
    redacted_preview, redaction_counts = redact_text(text, settings.redaction_preview_chars)
    redaction_applied = bool(redaction_counts)
    quality = QualityMetadata(
        text_length=len(text),
        page_count=page_count,
        pages_processed=len(pages),
        empty_page_count=empty_page_count,
        low_text=len(text.strip()) < settings.min_text_length,
    )
    evaluation = EvaluationMetadata(
        document_id=document_id,
        input_media_type=detected_mime_type,
        strategy=selected_strategy,
        status=status,
        page_count=quality.page_count,
        pages_processed=quality.pages_processed,
        text_length=quality.text_length,
        empty_page_count=quality.empty_page_count,
        elapsed_ms=elapsed_ms,
        finding_counts=_finding_counts(findings),
        redaction_applied=redaction_applied,
        redaction_finding_counts=redaction_counts,
        predicted_document_type=classification.document_type,
        classification_confidence=classification.confidence,
        classification_reason_codes=classification.reason_codes,
        classification_status=classification.status,
    )

    return DocumentParseResult(
        parse_id=f"parse_{uuid.uuid4().hex[:16]}",
        status=status,
        document=DocumentTrace(
            original_filename=filename or "",
            normalized_filename=normalized_filename,
            size_bytes=len(content),
            provided_content_type=provided_content_type.lower() if provided_content_type else None,
            detected_mime_type=detected_mime_type,
            ingestion_id=ingestion_id,
            source_type=source_type,
            source_id=source_id,
            sha256=document_hash,
        ),
        text=text,
        pages=pages,
        metadata=ParseMetadata(
            extraction_method=extraction_method,
            ocr_engine=settings.ocr_engine if ocr_attempted else None,
            page_count=page_count,
            pages_processed=quality.pages_processed,
            elapsed_ms=elapsed_ms,
            language=effective_language,
            page_limit=effective_page_limit,
        ),
        strategy=StrategyDecision(
            selected_strategy=selected_strategy,
            reason=strategy_reason,
            direct_text_attempted=direct_text_attempted,
            ocr_attempted=ocr_attempted,
            tesseract_available=tesseract_available,
        ),
        classification=classification,
        quality=quality,
        evaluation=evaluation,
        evidence=RedactedEvidencePreview(
            redacted_text_preview=redacted_preview if settings.redact_evidence_output else text,
            redaction_counts=redaction_counts,
            redaction_applied=redaction_applied,
        ),
        findings=findings,
    )
