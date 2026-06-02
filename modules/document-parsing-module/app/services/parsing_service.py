"""M5 - Document Parsing Module Start
Implements PDF text extraction, OCR fallback, classification, and evaluation metadata.
M5/M6 End"""

import hashlib
import io
import os
import re
import time
import uuid
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Optional

from PIL import Image, ImageEnhance, ImageOps
from pypdf import PdfReader

from app.config import settings
from app.models.parsing import (
    DocumentParseResult,
    DocumentTrace,
    EvaluationMetadata,
    FindingSeverity,
    M7HandoffAudit,
    OcrWordBlock,
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
OCR_KEYWORDS = {
    "account",
    "amount",
    "balance",
    "bill",
    "confirmation",
    "credit",
    "date",
    "debit",
    "due",
    "invoice",
    "payment",
    "purchase",
    "receipt",
    "reference",
    "statement",
    "total",
    "transfer",
}
TRANSACTION_SIGNAL_KEYWORDS = {
    "amount",
    "balance",
    "charge",
    "credit",
    "debit",
    "deposit",
    "due",
    "fee",
    "payment",
    "purchase",
    "receipt",
    "reference",
    "statement",
    "total",
    "transaction",
    "transfer",
    "withdrawal",
}


@dataclass(frozen=True)
class OcrAttempt:
    text: str
    mean_confidence: Optional[float]
    quality_score: float
    alnum_ratio: float
    keyword_hits: int
    orientation: int
    psm: int
    variant: str
    word_blocks: list[OcrWordBlock] = field(default_factory=list)
    attempt_count: int = 1


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


def _transaction_signal_count(text: str) -> int:
    lowered = (text or "").lower()
    keyword_hits = sum(1 for keyword in TRANSACTION_SIGNAL_KEYWORDS if keyword in lowered)
    amount_like_hits = len(re.findall(r"\b\d{1,3}(?:,\d{3})*(?:\.\d{2})\b", text or ""))
    date_like_hits = len(re.findall(r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})\b", text or ""))
    return keyword_hits + min(amount_like_hits, 10) + min(date_like_hits, 10)


def _m7_readiness_reason_codes(
    status: ParseStatus,
    text_length: int,
    transaction_signal_count: int,
    findings: list[ParseFinding],
) -> list[str]:
    reason_codes: list[str] = []
    if status in {ParseStatus.failed, ParseStatus.unsupported}:
        reason_codes.append("PARSE_NOT_SUCCESSFUL")
    if text_length < settings.min_text_length:
        reason_codes.append("LOW_TEXT_LENGTH")
    if transaction_signal_count == 0:
        reason_codes.append("NO_TRANSACTION_SIGNALS")
    if any(finding.code in {"TESSERACT_UNAVAILABLE", "OCR_FAILED", "PDF_RENDERER_UNAVAILABLE"} for finding in findings):
        reason_codes.append("OCR_BLOCKED_OR_FAILED")
    return reason_codes


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
    except (Exception, SystemExit):
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


def _prepare_image_for_ocr(image: Image.Image) -> Image.Image:
    corrected = ImageOps.exif_transpose(image)
    if corrected.mode not in {"RGB", "L"}:
        corrected = corrected.convert("RGB")

    width, height = corrected.size
    shortest_side = max(1, min(width, height))
    if shortest_side < 1200:
        scale = min(3.0, 1200 / shortest_side)
        corrected = corrected.resize(
            (int(width * scale), int(height * scale)),
            Image.Resampling.LANCZOS,
        )

    return corrected


def _image_variants(image: Image.Image) -> list[tuple[str, Image.Image]]:
    grayscale = ImageOps.grayscale(image)
    high_contrast = ImageEnhance.Contrast(grayscale).enhance(1.8)
    return [
        ("normalized", image),
        ("grayscale_contrast", high_contrast),
    ]


def _ocr_image_with_confidence(
    image: Image.Image,
    language: str,
    psm: int,
    page_number: int = 1,
) -> tuple[str, Optional[float], list[OcrWordBlock]]:
    import pytesseract

    if settings.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd
    if settings.tessdata_prefix:
        os.environ["TESSDATA_PREFIX"] = settings.tessdata_prefix

    config = f"--psm {psm}"
    try:
        data = pytesseract.image_to_data(
            image,
            lang=language,
            config=config,
            output_type=pytesseract.Output.DICT,
        )
        words: list[str] = []
        confidences: list[float] = []
        blocks: list[OcrWordBlock] = []
        for index, (raw_text, raw_confidence) in enumerate(zip(data.get("text", []), data.get("conf", []))):
            token = str(raw_text).strip()
            try:
                confidence = float(raw_confidence)
            except (TypeError, ValueError):
                confidence = None
            if token:
                words.append(token)
                blocks.append(
                    OcrWordBlock(
                        page_number=page_number,
                        text=token,
                        confidence=confidence if confidence is not None and confidence >= 0 else None,
                        x=float(data.get("left", [0])[index]),
                        y=float(data.get("top", [0])[index]),
                        width=float(data.get("width", [0])[index]),
                        height=float(data.get("height", [0])[index]),
                    )
                )
            if confidence is None:
                continue
            if confidence >= 0:
                confidences.append(confidence)

        text = " ".join(words).strip()
        mean_confidence = sum(confidences) / len(confidences) if confidences else None
        if text:
            return text, mean_confidence, blocks
    except Exception:
        pass

    return pytesseract.image_to_string(image, lang=language, config=config).strip(), None, []


def _ocr_quality(text: str, mean_confidence: Optional[float]) -> tuple[float, float, int]:
    stripped = text.strip()
    if not stripped:
        return 0.0, 0.0, 0

    alnum_count = sum(character.isalnum() for character in stripped)
    alnum_ratio = alnum_count / max(len(stripped), 1)
    lowered = stripped.lower()
    keyword_hits = sum(1 for keyword in OCR_KEYWORDS if keyword in lowered)
    confidence_score = (mean_confidence / 100.0) if mean_confidence is not None else 0.0
    length_score = min(len(stripped) / 500.0, 1.0)
    keyword_score = min(keyword_hits / 4.0, 1.0)
    quality_score = (
        confidence_score * 0.50
        + length_score * 0.20
        + alnum_ratio * 0.15
        + keyword_score * 0.15
    )
    return round(quality_score, 3), round(alnum_ratio, 3), keyword_hits


def _rotate_image(image: Image.Image, degrees: int) -> Image.Image:
    if degrees == 0:
        return image
    return image.rotate(degrees, expand=True)


def _ocr_best_image(image: Image.Image, language: str, page_number: int = 1) -> OcrAttempt:
    prepared_image = _prepare_image_for_ocr(image)
    orientations = [0, 90, 180, 270] if settings.ocr_retry_orientations else [0]
    psm_values = settings.ocr_psm_values or [6]
    best_attempt = OcrAttempt(
        text="",
        mean_confidence=None,
        quality_score=0.0,
        alnum_ratio=0.0,
        keyword_hits=0,
        orientation=0,
        psm=psm_values[0],
        variant="normalized",
    )
    attempt_count = 0

    for orientation in orientations:
        rotated = _rotate_image(prepared_image, orientation)
        for variant_name, variant in _image_variants(rotated):
            for psm in psm_values:
                attempt_count += 1
                text, mean_confidence, word_blocks = _ocr_image_with_confidence(variant, language, psm, page_number)
                quality_score, alnum_ratio, keyword_hits = _ocr_quality(text, mean_confidence)
                attempt = OcrAttempt(
                    text=text,
                    mean_confidence=mean_confidence,
                    quality_score=quality_score,
                    alnum_ratio=alnum_ratio,
                    keyword_hits=keyword_hits,
                    orientation=orientation,
                    psm=psm,
                    variant=variant_name,
                    word_blocks=word_blocks,
                )
                if attempt.quality_score > best_attempt.quality_score:
                    best_attempt = attempt

    return replace(best_attempt, attempt_count=attempt_count)


def _ocr_image_content(content: bytes, language: str) -> tuple[str, list[PageParseResult], int, dict[str, object]]:
    with Image.open(io.BytesIO(content)) as image:
        attempt = _ocr_best_image(image, language, 1)

    return (
        attempt.text,
        [
            PageParseResult(
                page_number=1,
                text=attempt.text,
                text_length=len(attempt.text),
                empty=not bool(attempt.text.strip()),
                ocr_word_blocks=attempt.word_blocks,
            )
        ],
        1,
        _ocr_quality_metadata([attempt]),
    )


def _ocr_quality_metadata(attempts: list[OcrAttempt]) -> dict[str, object]:
    if not attempts:
        return {
            "quality_score": None,
            "mean_confidence": None,
            "selected_orientation": None,
            "selected_psm": None,
            "attempt_count": 0,
            "alnum_ratio": None,
            "keyword_hits": 0,
        }

    best_attempt = max(attempts, key=lambda attempt: attempt.quality_score)
    return {
        "quality_score": best_attempt.quality_score,
        "mean_confidence": round(best_attempt.mean_confidence, 2) if best_attempt.mean_confidence is not None else None,
        "selected_orientation": best_attempt.orientation,
        "selected_psm": best_attempt.psm,
        "attempt_count": sum(attempt.attempt_count for attempt in attempts),
        "alnum_ratio": best_attempt.alnum_ratio,
        "keyword_hits": best_attempt.keyword_hits,
    }


def _unpack_ocr_result(raw_result: tuple) -> tuple[str, list[PageParseResult], int, dict[str, object]]:
    if len(raw_result) == 4:
        return raw_result

    text, pages, page_count = raw_result
    quality_score, alnum_ratio, keyword_hits = _ocr_quality(text, None)
    return text, pages, page_count, {
        "quality_score": quality_score,
        "mean_confidence": None,
        "selected_orientation": 0,
        "selected_psm": None,
        "attempt_count": 1 if text else 0,
        "alnum_ratio": alnum_ratio,
        "keyword_hits": keyword_hits,
    }


def _ocr_pdf_pages(content: bytes, page_limit: int, language: str) -> tuple[str, list[PageParseResult], int, dict[str, object]]:
    import fitz

    document = fitz.open(stream=content, filetype="pdf")
    page_count = document.page_count
    pages: list[PageParseResult] = []
    extracted_parts: list[str] = []
    attempts: list[OcrAttempt] = []
    matrix = fitz.Matrix(2.0, 2.0)

    try:
        for page_number in range(1, min(page_count, page_limit) + 1):
            page = document.load_page(page_number - 1)
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            image = Image.open(io.BytesIO(pixmap.tobytes("png")))
            attempt = _ocr_best_image(image, language, page_number)
            attempts.append(attempt)
            page_text = attempt.text
            pages.append(
                PageParseResult(
                    page_number=page_number,
                    text=page_text,
                    text_length=len(page_text),
                    empty=not bool(page_text.strip()),
                    ocr_word_blocks=attempt.word_blocks,
                )
            )
            if page_text:
                extracted_parts.append(page_text)
    finally:
        document.close()

    return "\n".join(extracted_parts), pages, page_count, _ocr_quality_metadata(attempts)


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
    ocr_quality: dict[str, object] = _ocr_quality_metadata([])
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
                            text, pages, page_count, ocr_quality = _unpack_ocr_result(
                                _ocr_pdf_pages(content, effective_page_limit, effective_language)
                            )
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
                        text, pages, page_count, ocr_quality = _unpack_ocr_result(
                            _ocr_image_content(content, effective_language)
                        )
                    except Exception:
                        findings.append(_finding("OCR_FAILED", "Tesseract OCR could not process the image."))
            else:
                selected_strategy = "ocr_disabled"
                strategy_reason = "Image input requires OCR but fallback is disabled."
                findings.append(_finding("OCR_FALLBACK_DISABLED", "Image input requires OCR and OCR fallback is disabled."))

    if ocr_attempted and text:
        selected_orientation = ocr_quality.get("selected_orientation")
        attempt_count = int(ocr_quality.get("attempt_count") or 0)
        psm_count = max(1, len(settings.ocr_psm_values or [6]))
        if attempt_count > psm_count or selected_orientation not in {None, 0}:
            findings.append(
                _finding(
                    "OCR_ORIENTATION_RETRIED",
                    "OCR tried multiple image orientations or page segmentation modes and selected the best scored result.",
                    FindingSeverity.info,
                )
            )

        mean_confidence = ocr_quality.get("mean_confidence")
        if isinstance(mean_confidence, (int, float)) and mean_confidence < settings.ocr_min_confidence:
            findings.append(
                _finding(
                    "LOW_OCR_CONFIDENCE",
                    "Tesseract OCR confidence was below the configured threshold.",
                    FindingSeverity.warning,
                )
            )

        quality_score = ocr_quality.get("quality_score")
        alnum_ratio = ocr_quality.get("alnum_ratio")
        if (
            isinstance(quality_score, (int, float))
            and quality_score < settings.ocr_min_quality_score
        ) or (
            isinstance(alnum_ratio, (int, float))
            and alnum_ratio < settings.ocr_min_alnum_ratio
        ):
            findings.append(
                _finding(
                    "OCR_TEXT_NOISY",
                    "OCR produced text but quality scoring indicates the output may be noisy.",
                    FindingSeverity.warning,
                )
            )

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
    transaction_signal_count = _transaction_signal_count(text)
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
        predicted_document_subtype=classification.document_subtype,
        classification_confidence=classification.confidence,
        classification_reason_codes=classification.reason_codes,
        classification_status=classification.status,
    )
    m7_reason_codes = _m7_readiness_reason_codes(status, quality.text_length, transaction_signal_count, findings)
    parse_id = f"parse_{uuid.uuid4().hex[:16]}"
    selected_ocr_engine = "tesseract" if ocr_attempted and selected_strategy == "tesseract_ocr" else None

    return DocumentParseResult(
        parse_id=parse_id,
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
            ocr_engine=selected_ocr_engine,
            page_count=page_count,
            pages_processed=quality.pages_processed,
            elapsed_ms=elapsed_ms,
            language=effective_language,
            page_limit=effective_page_limit,
            ocr_quality_score=ocr_quality.get("quality_score") if ocr_attempted else None,
            ocr_mean_confidence=ocr_quality.get("mean_confidence") if ocr_attempted else None,
            ocr_selected_orientation=ocr_quality.get("selected_orientation") if ocr_attempted else None,
            ocr_selected_psm=ocr_quality.get("selected_psm") if ocr_attempted else None,
            ocr_attempt_count=int(ocr_quality.get("attempt_count") or 0) if ocr_attempted else 0,
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
        m7_handoff=M7HandoffAudit(
            parse_id=parse_id,
            document_id=document_id,
            filename=normalized_filename,
            strategy=selected_strategy,
            extraction_method=extraction_method,
            ocr_engine=selected_ocr_engine,
            ocr_attempted=ocr_attempted,
            tesseract_available=tesseract_available,
            status=status,
            confidence=classification.confidence,
            text_length=quality.text_length,
            page_count=quality.page_count,
            pages_processed=quality.pages_processed,
            warnings=[finding.code for finding in findings if finding.severity == FindingSeverity.warning],
            m7_ready=not m7_reason_codes,
            m7_readiness_reason_codes=m7_reason_codes,
            transaction_signal_count=transaction_signal_count,
            redacted_preview=redacted_preview if settings.redact_evidence_output else text,
            redaction_summary=redaction_counts,
            redaction_applied=redaction_applied,
        ),
        findings=findings,
    )
