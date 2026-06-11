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
    ExtractionHandoffAudit,
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
OCR_CRITICAL_EVIDENCE_PATTERNS = [
    re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b"),
    re.compile(r"\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+\d{2,4}\b", re.IGNORECASE),
    re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?\b"),
    re.compile(r"\b(?:NZD|NZ\$|PHP|USD|AUD|\$)\s*\d{1,3}(?:,\d{3})*(?:\.\s?\d{2}|,\d{2})\b", re.IGNORECASE),
    re.compile(r"\b(?:EFTPOS|TERMINAL|APPROVED|AUTHORISATION|AUTHORIZATION|REFERENCE|RRN|PURCHASE|TOTAL)\b", re.IGNORECASE),
]


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
    early_stopped: bool = False
    early_stop_reason: Optional[str] = None
    amount_coherence_score: float = 0.0
    amount_coherence_status: str = "not_evaluated"
    amount_conflict_reasons: tuple[str, ...] = ()


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


def _extraction_readiness_reason_codes(
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
    document_crop = _document_crop_variant(image)
    grayscale = ImageOps.grayscale(image)
    autocontrast = ImageOps.autocontrast(grayscale)
    high_contrast = ImageEnhance.Contrast(grayscale).enhance(1.8)
    sharpened_contrast = ImageEnhance.Sharpness(high_contrast).enhance(2.0)
    thresholded = autocontrast.point(lambda pixel: 255 if pixel > 170 else 0)
    variants = [
        ("normalized", image),
        ("grayscale_contrast", high_contrast),
        ("autocontrast", autocontrast),
        ("sharpened_contrast", sharpened_contrast),
        ("thresholded", thresholded),
    ]
    if document_crop is not None:
        crop_gray = ImageOps.grayscale(document_crop)
        crop_autocontrast = ImageOps.autocontrast(crop_gray)
        variants.insert(1, ("document_crop", document_crop))
        variants.insert(2, ("document_crop_autocontrast", crop_autocontrast))
    return variants


def _document_crop_variant(image: Image.Image) -> Image.Image | None:
    width, height = image.size
    if width < 300 or height < 300:
        return None

    grayscale = ImageOps.grayscale(image)
    thumbnail = ImageOps.autocontrast(grayscale.copy())
    thumbnail.thumbnail((900, 900), Image.Resampling.LANCZOS)
    thumb_width, thumb_height = thumbnail.size
    pixels = thumbnail.load()
    threshold = 182
    xs: list[int] = []
    ys: list[int] = []

    for y in range(thumb_height):
        for x in range(thumb_width):
            if pixels[x, y] >= threshold:
                xs.append(x)
                ys.append(y)

    if not xs or not ys:
        return None

    left, right = min(xs), max(xs)
    top, bottom = min(ys), max(ys)
    crop_width = right - left + 1
    crop_height = bottom - top + 1
    crop_area_ratio = (crop_width * crop_height) / max(thumb_width * thumb_height, 1)
    if crop_area_ratio < 0.18 or crop_area_ratio > 0.96:
        return None
    if crop_width < thumb_width * 0.25 or crop_height < thumb_height * 0.25:
        return None

    scale_x = width / thumb_width
    scale_y = height / thumb_height
    pad_x = int(width * 0.025)
    pad_y = int(height * 0.025)
    box = (
        max(0, int(left * scale_x) - pad_x),
        max(0, int(top * scale_y) - pad_y),
        min(width, int((right + 1) * scale_x) + pad_x),
        min(height, int((bottom + 1) * scale_y) + pad_y),
    )
    cropped = image.crop(box)
    if cropped.size == image.size:
        return None
    return cropped


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
    critical_hits = sum(len(pattern.findall(stripped)) for pattern in OCR_CRITICAL_EVIDENCE_PATTERNS)
    confidence_score = (mean_confidence / 100.0) if mean_confidence is not None else 0.0
    length_score = min(len(stripped) / 500.0, 1.0)
    keyword_score = min(keyword_hits / 4.0, 1.0)
    critical_score = min(critical_hits / 6.0, 1.0)
    quality_score = (
        confidence_score * 0.40
        + length_score * 0.18
        + alnum_ratio * 0.12
        + keyword_score * 0.12
        + critical_score * 0.18
    )
    return round(quality_score, 3), round(alnum_ratio, 3), keyword_hits


def _rotate_image(image: Image.Image, degrees: int) -> Image.Image:
    if degrees == 0:
        return image
    return image.rotate(degrees, expand=True)


def _ocr_best_image(image: Image.Image, language: str, page_number: int = 1, fast_pdf_profile: bool = False) -> OcrAttempt:
    prepared_image = _prepare_image_for_ocr(image)
    if fast_pdf_profile:
        fast_psm_values = list(dict.fromkeys(settings.ocr_pdf_fast_psm_values or [6]))
        fast_attempt = _ocr_attempt_profile(
            prepared_image,
            language,
            page_number,
            orientations=[0],
            psm_values=fast_psm_values,
            max_variants=2,
        )
        if _ocr_attempt_meets_fast_threshold(fast_attempt):
            return fast_attempt

        repair_attempt = _ocr_best_image(image, language, page_number, fast_pdf_profile=False)
        return replace(repair_attempt, attempt_count=fast_attempt.attempt_count + repair_attempt.attempt_count)

    orientations = [0, 90, 180, 270] if settings.ocr_retry_orientations else [0]
    psm_values = list(dict.fromkeys([*(settings.ocr_psm_values or [6]), 3]))
    fast_psm_values = list(dict.fromkeys(settings.ocr_image_fast_psm_values or [psm_values[0]]))
    return _ocr_attempt_profile(
        prepared_image,
        language,
        page_number,
        orientations=orientations,
        psm_values=list(dict.fromkeys([*fast_psm_values, *psm_values])),
        max_variants=None,
        early_stop_checker=_ocr_attempt_meets_image_early_stop_threshold,
    )


def _ocr_attempt_profile(
    prepared_image: Image.Image,
    language: str,
    page_number: int,
    orientations: list[int],
    psm_values: list[int],
    max_variants: Optional[int],
    early_stop_checker=None,
) -> OcrAttempt:
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
        variants = _image_variants(rotated)
        if max_variants is not None:
            variants = variants[:max_variants]
        if orientation != 0:
            variants = variants[:2]
        for variant_name, variant in variants:
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
                coherence = _receipt_amount_coherence(text)
                attempt = replace(
                    attempt,
                    amount_coherence_score=coherence["score"],
                    amount_coherence_status=coherence["status"],
                    amount_conflict_reasons=tuple(coherence["reasons"]),
                )
                if _ocr_attempt_is_better(attempt, best_attempt):
                    best_attempt = attempt
                if early_stop_checker and early_stop_checker(attempt):
                    return replace(
                        attempt,
                        attempt_count=attempt_count,
                        early_stopped=True,
                        early_stop_reason="STRONG_RECEIPT_AND_CLEAN_TOTAL",
                    )

    return replace(best_attempt, attempt_count=attempt_count)


def _ocr_attempt_meets_fast_threshold(attempt: OcrAttempt) -> bool:
    if len(attempt.text.strip()) < settings.ocr_fast_min_text_length:
        return False
    if attempt.quality_score < settings.ocr_fast_min_quality_score:
        return False
    if attempt.mean_confidence is not None and attempt.mean_confidence < settings.ocr_min_confidence:
        return False
    return (
        attempt.keyword_hits > 0
        or _financial_amount_token_score(attempt.text) > 0
        or _receipt_amount_evidence_score(attempt.text) > 0
    )


def _ocr_attempt_meets_image_early_stop_threshold(attempt: OcrAttempt) -> bool:
    text = attempt.text.strip()
    if len(text) < settings.ocr_image_fast_min_text_length:
        return False
    if attempt.quality_score < settings.ocr_image_fast_min_quality_score:
        return False
    if attempt.mean_confidence is not None and attempt.mean_confidence < settings.ocr_image_fast_min_confidence:
        return False
    if _financial_amount_token_score(text) == 0:
        return False
    if _document_shape_signal_score(text) < 3:
        return False
    coherence = _receipt_amount_coherence(text)
    return coherence["status"] == "clean" and coherence["score"] >= 3


def _ocr_attempt_is_better(attempt: OcrAttempt, best_attempt: OcrAttempt) -> bool:
    amount_evidence_delta = _receipt_amount_evidence_score(attempt.text) - _receipt_amount_evidence_score(best_attempt.text)
    if amount_evidence_delta >= 3 and attempt.quality_score >= best_attempt.quality_score - 0.08:
        return True
    if attempt.quality_score > best_attempt.quality_score + 0.01:
        return True
    if abs(attempt.quality_score - best_attempt.quality_score) > 0.01:
        return False
    return _ocr_attempt_tiebreak(attempt) > _ocr_attempt_tiebreak(best_attempt)


def _ocr_attempt_tiebreak(attempt: OcrAttempt) -> tuple[int, int, int, float]:
    confidence = attempt.mean_confidence or 0.0
    return (
        _receipt_amount_evidence_score(attempt.text),
        _financial_amount_token_score(attempt.text),
        len(attempt.text),
        attempt.keyword_hits,
        confidence,
    )


def _receipt_amount_evidence_score(text: str) -> int:
    normalized = re.sub(r"\s+", " ", text or "").strip()
    if not normalized:
        return 0

    lowered = normalized.lower()
    score = 0
    score += min(len(re.findall(r"\bnz\s?[$s]\s*\d{1,4}(?:[.,]\d{2})\b", lowered)), 3) * 3
    score += min(len(re.findall(r"\bnzd\s*\d{1,4}(?:[.,]\d{2})\b", lowered)), 3) * 3
    score += min(len(re.findall(r"\b(?:total|purchase|approved|paid|amount)\b.{0,32}\d{1,4}(?:[.,]\d{2})\b", lowered)), 5)
    score += min(len(re.findall(r"\b\d{1,4}(?:[.,]\d{2})\b.{0,16}\b(?:total|purchase|approved|paid)\b", lowered)), 3)
    return score


def _receipt_amount_coherence(text: str) -> dict[str, object]:
    normalized = re.sub(r"\s+", " ", text or "").strip()
    if not normalized:
        return {"score": 0.0, "status": "missing", "reasons": ["NO_TEXT"]}

    lowered = normalized.lower()
    reasons: list[str] = []
    final_label_pattern = r"(?:grand\s+total|total|eftpos|ef\s*tpos|complete|amount\s+due|due\s+amount|bank\s+card|debit\s+card|credit\s+card|purchase|paid)"
    clean_labelled = re.findall(
        rf"\b{final_label_pattern}\b.{{0,40}}?(?:NZD|NZ\$|\$|PHP|USD|AUD)?\s*\d{{1,4}}(?:,\d{{3}})*(?:\.\s?\d{{2}}|,\d{{2}})\b",
        normalized,
        re.IGNORECASE,
    )
    clean_amounts = {
        round(float(match.group(0).replace(",", "").replace(" ", "")), 2)
        for match in re.finditer(r"\b\d{1,3}(?:,\d{3})*(?:\.\s?\d{2}|,\d{2})\b", normalized)
    }
    damaged_patterns = [
        r"\bNZD\s*0?\d{2,4}\s*(?:[.,]\s*)?(?:O[0OF]?|[O0]F|G[O0]|[O0]{1,2})\b",
        r"\b(?:total|eftpos|complete|amount\s+due|due\s+amount)\b.{0,40}\b(?:NZD|NZ\$|\$)?\s*0?\d{2,4}\s+\d{2}\b",
        r"\b(?:total|eftpos|complete|amount\s+due|due\s+amount)\b.{0,40}\b(?:NZD|NZ\$|\$)?\s*\d{1,4}\s*[.,]\s*[A-Z]{1,3}\b",
    ]
    damaged_hits = [pattern for pattern in damaged_patterns if re.search(pattern, normalized, re.IGNORECASE)]
    if damaged_hits:
        reasons.append("DAMAGED_LABELLED_AMOUNT")

    if clean_labelled:
        reasons.append("CLEAN_LABELLED_AMOUNT")
    if len(clean_amounts) >= 3:
        reasons.append("MULTIPLE_AMOUNT_VALUES")

    score = 0.0
    score += min(len(clean_labelled), 3) * 2.0
    score += min(_receipt_amount_evidence_score(normalized), 4) * 0.5
    score += min(_document_shape_signal_score(normalized), 4) * 0.25
    score -= min(len(damaged_hits), 2) * 1.5
    if len(clean_amounts) >= 3 and damaged_hits:
        score -= 1.0

    if not clean_labelled:
        status = "weak"
        reasons.append("NO_CLEAN_LABELLED_AMOUNT")
    elif damaged_hits or (len(clean_amounts) >= 3 and re.search(r"\b(?:total|eftpos|complete|due\s+amount|amount\s+due)\b", lowered)):
        status = "conflicting"
    else:
        status = "clean"

    return {"score": round(max(score, 0.0), 2), "status": status, "reasons": reasons}


def _document_shape_signal_score(text: str) -> int:
    normalized = re.sub(r"\s+", " ", text or "").strip().lower()
    if not normalized:
        return 0

    signal_groups = [
        r"\b(?:tax\s+invoice|receipt|invoice)\b",
        r"\b(?:total|subtotal|amount\s+due|due\s+amount)\b",
        r"\b(?:eftpos|ef\s*tpos|card|approved|purchase|paid)\b",
        r"\b(?:gst|tax|include\s+tax|includes\s+gst)\b",
        r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b\d{4}-\d{2}-\d{2}\b",
        r"\b\d{1,2}:\d{2}(?::\d{2})?\b",
        r"(?:NZD|NZ\$|\$|PHP|USD|AUD)\s*\d{1,4}(?:[.,]\s?\d{2})",
    ]
    return sum(1 for pattern in signal_groups if re.search(pattern, normalized, re.IGNORECASE))


def _financial_amount_token_score(text: str) -> int:
    score = 0
    for match in re.finditer(r"\b\d{1,3}(?:,\d{3})*(?:\.\s?\d{2}|,\d{2})\b", text or ""):
        try:
            amount = float(match.group(0).replace(",", "").replace(" ", ""))
        except ValueError:
            continue
        if amount >= 10:
            score += 1
    return score


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
            "selected_variant": None,
            "attempt_count": 0,
            "alnum_ratio": None,
            "keyword_hits": 0,
            "early_stopped": False,
            "early_stop_reason": None,
            "amount_coherence_score": None,
            "amount_coherence_status": None,
            "amount_conflict_reasons": [],
        }

    best_attempt = max(attempts, key=lambda attempt: attempt.quality_score)
    return {
        "quality_score": best_attempt.quality_score,
        "mean_confidence": round(best_attempt.mean_confidence, 2) if best_attempt.mean_confidence is not None else None,
        "selected_orientation": best_attempt.orientation,
        "selected_psm": best_attempt.psm,
        "selected_variant": best_attempt.variant,
        "attempt_count": sum(attempt.attempt_count for attempt in attempts),
        "alnum_ratio": best_attempt.alnum_ratio,
        "keyword_hits": best_attempt.keyword_hits,
        "early_stopped": best_attempt.early_stopped,
        "early_stop_reason": best_attempt.early_stop_reason,
        "amount_coherence_score": best_attempt.amount_coherence_score,
        "amount_coherence_status": best_attempt.amount_coherence_status,
        "amount_conflict_reasons": list(best_attempt.amount_conflict_reasons),
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
    matrix = fitz.Matrix(settings.ocr_pdf_render_scale, settings.ocr_pdf_render_scale)

    try:
        for page_number in range(1, min(page_count, page_limit) + 1):
            page = document.load_page(page_number - 1)
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            image = Image.open(io.BytesIO(pixmap.tobytes("png")))
            attempt = _ocr_best_image(image, language, page_number, fast_pdf_profile=True)
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
        if "RECOGNITION_SETTINGS_UNAVAILABLE" in classification.reason_codes:
            findings.append(
                _finding(
                    "RECOGNITION_SETTINGS_UNAVAILABLE",
                    "Recognition settings could not be loaded from Stats Data, so document classification needs review.",
                    FindingSeverity.warning,
                )
            )
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
        classification_source=classification.classification_source,
    )
    extraction_reason_codes = _extraction_readiness_reason_codes(status, quality.text_length, transaction_signal_count, findings)
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
            ocr_selected_variant=ocr_quality.get("selected_variant") if ocr_attempted else None,
            ocr_early_stopped=bool(ocr_quality.get("early_stopped")) if ocr_attempted else False,
            ocr_early_stop_reason=ocr_quality.get("early_stop_reason") if ocr_attempted else None,
            amount_coherence_score=ocr_quality.get("amount_coherence_score") if ocr_attempted else None,
            amount_coherence_status=ocr_quality.get("amount_coherence_status") if ocr_attempted else None,
            amount_conflict_reasons=list(ocr_quality.get("amount_conflict_reasons") or []) if ocr_attempted else [],
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
        extraction_handoff=ExtractionHandoffAudit(
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
            extraction_ready=not extraction_reason_codes,
            extraction_readiness_reason_codes=extraction_reason_codes,
            transaction_signal_count=transaction_signal_count,
            redacted_preview=redacted_preview if settings.redact_evidence_output else text,
            redaction_summary=redaction_counts,
            redaction_applied=redaction_applied,
        ),
        findings=findings,
    )
