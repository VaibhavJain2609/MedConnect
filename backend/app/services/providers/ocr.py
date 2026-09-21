"""
Lab-report OCR / AI-ingest provider adapter — pluggable, disabled by default.

Extracts structured lab values (analyte name, measured value, unit,
reference range, abnormal flag) from an uploaded lab-report image so a
doctor can review them and prefill a lab-result entry form. This is a
human-in-the-loop assist: extracted values are returned as *candidates*
only — the ingest endpoint never writes ``LabResult`` rows.

Provider contract:

    async def extract_lab_values(
        *,
        image_bytes: bytes | None = None,
        storage_key: str | None = None,
        content_type: str | None = None,
    ) -> list[LabValueCandidate]

Either ``image_bytes`` (local storage backend — the router reads the
object from disk) or ``storage_key`` (S3 backend — the provider fetches
the object itself) is supplied. Implementations MUST raise
``OcrUnavailable`` for any provider-level failure (not configured,
transport error, upstream timeout) and MUST NOT leak image bytes or
parsed PHI into logs — identifiers (provider name, candidate count)
only.

Settings (all optional; the feature is OFF unless OCR_PROVIDER is set):

    OCR_PROVIDER              — "none" (default) | "llm"
    OCR_LLM_BASE_URL          — OpenAI-compatible vision endpoint base URL
    OCR_LLM_API_KEY           — API key for the vision backend
    OCR_LLM_MODEL             — model name (e.g. "gpt-4o", "claude-…")
    OCR_LLM_TIMEOUT_SECONDS   — upstream timeout (default 30)

To enable, set ``OCR_PROVIDER=llm`` plus the ``OCR_LLM_*`` settings in the
backend environment (see RUNBOOK.md § "Lab-report OCR ingest"). Until a
real backend is wired in ``LlmVisionOcrProvider._call_vision_api`` the
provider raises ``OcrUnavailable`` cleanly — the endpoint maps that to
503, and ``OCR_PROVIDER=none`` yields 503 OCR_NOT_CONFIGURED.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

import structlog

from app.config import settings

logger = structlog.get_logger()

_TIMEOUT_SECONDS = 30.0


class OcrUnavailable(Exception):
    """Provider-level failure: not configured, not implemented, or the
    upstream vision backend is unreachable. Mapped to 503 by callers."""


@dataclass
class LabValueCandidate:
    """One extracted lab analyte, pre-normalization. All fields optional
    except ``name`` — OCR output is noisy and reviewers fix gaps inline.

    ``flag`` is a coarse abnormal marker: "normal" | "low" | "high" |
    "abnormal" | "critical" (provider-supplied, free-form tolerated).
    ``ref_low`` / ``ref_high`` are the printed reference-range bounds as
    strings; units differ per analyte so no numeric coercion happens here.
    """

    name: str
    value: str | None = None
    unit: str | None = None
    ref_low: str | None = None
    ref_high: str | None = None
    flag: str | None = None
    extra: dict = field(default_factory=dict)


@runtime_checkable
class OcrProvider(Protocol):
    """Pluggable OCR/AI extraction backend."""

    name: str

    async def extract_lab_values(
        self,
        *,
        image_bytes: bytes | None = None,
        storage_key: str | None = None,
        content_type: str | None = None,
    ) -> list[LabValueCandidate]:
        """Return extracted lab-value candidates for human review.

        Raises ``OcrUnavailable`` on any provider-level failure."""
        ...


class NullOcrProvider:
    """Default provider — feature disabled. Always raises OcrUnavailable;
    the router short-circuits to 503 OCR_NOT_CONFIGURED before calling it."""

    name = "none"

    async def extract_lab_values(
        self,
        *,
        image_bytes: bytes | None = None,
        storage_key: str | None = None,
        content_type: str | None = None,
    ) -> list[LabValueCandidate]:
        raise OcrUnavailable("OCR provider not configured (OCR_PROVIDER=none)")


class LlmVisionOcrProvider:
    """Stub for an LLM-vision backend (OpenAI-compatible chat/completions
    with an image input, or a hosted OCR API).

    The request/response scaffolding is in place — ``_build_prompt`` and
    ``_parse_response`` define the contract — but ``_call_vision_api`` is
    deliberately NOT implemented: no real OCR/LLM credentials are
    available, so it raises ``OcrUnavailable`` instead of making a network
    call. Wire in ``httpx.AsyncClient`` against ``OCR_LLM_BASE_URL`` when
    a backend is provisioned.
    """

    name = "llm"

    def __init__(self) -> None:
        self._base_url = settings.OCR_LLM_BASE_URL
        self._api_key = settings.OCR_LLM_API_KEY
        self._model = settings.OCR_LLM_MODEL
        self._timeout = settings.OCR_LLM_TIMEOUT_SECONDS or _TIMEOUT_SECONDS

    @property
    def configured(self) -> bool:
        return bool(self._base_url and self._api_key and self._model)

    async def extract_lab_values(
        self,
        *,
        image_bytes: bytes | None = None,
        storage_key: str | None = None,
        content_type: str | None = None,
    ) -> list[LabValueCandidate]:
        if not self.configured:
            # Missing OCR_LLM_* pieces — treated as unavailable, not a 500.
            raise OcrUnavailable(
                "LLM vision OCR selected but OCR_LLM_BASE_URL / "
                "OCR_LLM_API_KEY / OCR_LLM_MODEL are not all set"
            )
        if image_bytes is None and storage_key is None:
            raise OcrUnavailable("No image supplied for OCR extraction")

        prompt = self._build_prompt()
        raw = await self._call_vision_api(
            prompt, image_bytes=image_bytes, storage_key=storage_key
        )
        candidates = self._parse_response(raw)
        # PHI note: log identifiers only — never image bytes or parsed values.
        logger.info(
            "lab_ocr_extraction_complete",
            provider=self.name,
            candidate_count=len(candidates),
        )
        return candidates

    # -- internals ------------------------------------------------------

    @staticmethod
    def _build_prompt() -> str:
        """Extraction prompt for the vision backend. Kept as a separate
        method so the contract is testable without a live model."""
        return (
            "Extract every analyte row from this lab report image. "
            "Return strict JSON: a list of objects with keys "
            '"name", "value", "unit", "ref_low", "ref_high", "flag". '
            "Use null for fields not printed. Do not invent values."
        )

    async def _call_vision_api(
        self,
        prompt: str,
        *,
        image_bytes: bytes | None,
        storage_key: str | None,
    ) -> dict:
        """NOT IMPLEMENTED — placeholder for the upstream call.

        Intended shape: POST {OCR_LLM_BASE_URL}/chat/completions with an
        OpenAI-style message list embedding the image (base64 data URL or
        a presigned GET for ``storage_key``), ``Authorization: Bearer``
        with OCR_LLM_API_KEY, and a response_format of json_object.
        Raises OcrUnavailable until a real backend is wired in."""
        raise OcrUnavailable(
            "LLM vision OCR backend not implemented — wire _call_vision_api "
            "to an OpenAI-compatible endpoint before enabling"
        )

    @staticmethod
    def _parse_response(raw: dict) -> list[LabValueCandidate]:
        """Map a vision-backend JSON payload to LabValueCandidate rows.

        Tolerates both a bare list and {"results": [...]} envelopes and
        skips entries without a usable ``name``. Never raises on bad rows —
        partial extraction is still useful to a human reviewer."""
        rows = raw.get("results") if isinstance(raw, dict) else raw
        if not isinstance(rows, list):
            return []
        out: list[LabValueCandidate] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            name = row.get("name") or row.get("test_name")
            if not name:
                continue
            out.append(
                LabValueCandidate(
                    name=str(name),
                    value=_opt_str(row.get("value")),
                    unit=_opt_str(row.get("unit")),
                    ref_low=_opt_str(row.get("ref_low")),
                    ref_high=_opt_str(row.get("ref_high")),
                    flag=_opt_str(row.get("flag")),
                )
            )
        return out


def _opt_str(v) -> str | None:
    return None if v is None else str(v)


def get_ocr_provider() -> OcrProvider:
    """Factory — resolves the configured provider from settings.

    ``OCR_PROVIDER`` values: "none" (default → NullOcrProvider) | "llm"
    (→ LlmVisionOcrProvider stub). Unknown values fall back to the null
    provider so a typo disables the feature instead of crashing requests.
    """
    kind = (settings.OCR_PROVIDER or "none").strip().lower()
    if kind == "llm":
        return LlmVisionOcrProvider()
    if kind != "none":
        logger.warning("lab_ocr_unknown_provider", configured=kind)
    return NullOcrProvider()
