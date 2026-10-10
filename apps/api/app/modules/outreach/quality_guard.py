from __future__ import annotations

import re
from dataclasses import dataclass, field

# --- Outreach factuality and quality guard -------------------------------
#
# The model writes the draft; this decides whether the draft is safe to put
# in front of a human. Every check here is deterministic and explainable --
# no second model is asked "is this true?", because that would just move the
# hallucination one layer down.
#
# The guard's job is narrow and specific: catch the claims a prospect could
# call us out on. A number we never measured, a client we never had, a
# guarantee we cannot honour, or a template placeholder that escaped.

SEVERITY_BLOCK = "block"
SEVERITY_WARN = "warn"

_NUMBER_RE = re.compile(r"\b\d[\d,.]*\s?(?:%|percent|x|k|m)?\b", re.IGNORECASE)
_PLACEHOLDER_RE = re.compile(r"(\{\{.*?\}\}|\[[A-Z_ ]{3,}\]|\bTODO\b|\bXYZ\b|\bLOREM\b)")
_GUARANTEE_RE = re.compile(
    r"\b(guarantee[ds]?|guaranteed results|we promise|risk[- ]free|100%\s+(?:success|satisfaction)"
    r"|double your (?:revenue|sales|bookings)|no[- ]risk)\b",
    re.IGNORECASE,
)
_PROPER_NOUN_RE = re.compile(r"\b(?:[A-Z][a-z]{2,}\s){1,3}[A-Z][a-z]{2,}\b")

#: Multi-word capitalized phrases that are ordinary English, not client names.
_PROPER_NOUN_ALLOWLIST = frozenset(
    {
        "best regards", "kind regards", "dear sir", "dear madam", "thank you",
        "google business profile", "google maps", "whats app", "whatsapp business",
        "search engine", "social media", "best wishes", "looking forward",
    }
)

#: Numbers that carry no factual claim.
_INNOCUOUS_NUMBERS = frozenset({"1", "2", "3", "4", "5", "10", "15", "20", "30", "24", "7"})


@dataclass(frozen=True, slots=True)
class GuardFinding:
    code: str
    severity: str
    detail: str
    evidence: str


@dataclass(frozen=True, slots=True)
class GuardReport:
    findings: list[GuardFinding] = field(default_factory=list)

    @property
    def blocked(self) -> bool:
        return any(finding.severity == SEVERITY_BLOCK for finding in self.findings)

    @property
    def passed(self) -> bool:
        return not self.findings

    def as_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "blocked": self.blocked,
            "findings": [
                {
                    "code": finding.code,
                    "severity": finding.severity,
                    "detail": finding.detail,
                    "evidence": finding.evidence,
                }
                for finding in self.findings
            ],
        }


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


@dataclass
class OutreachQualityGuard:
    """Checks a generated outreach draft against what we can actually stand behind.

    `grounding` is the text the run actually retrieved this session -- knowledge
    excerpts and lead facts. A claim that appears nowhere in it is not
    necessarily false, but it is unsupported, and an unsupported specific in a
    cold email is the thing that loses the meeting.
    """

    max_subject_chars: int = 90
    max_body_words: int = 220
    min_body_words: int = 40

    def check(
        self,
        *,
        subject: str | None,
        body: str,
        grounding: list[str],
        lead_terms: list[str],
    ) -> GuardReport:
        findings: list[GuardFinding] = []
        haystack = _normalize(" ".join([*grounding, *lead_terms]))
        normalized_body = _normalize(body)

        findings.extend(self._check_placeholders(body))
        findings.extend(self._check_guarantees(body))
        findings.extend(self._check_numbers(body, haystack))
        findings.extend(self._check_named_entities(body, haystack, lead_terms))
        findings.extend(self._check_shape(subject, normalized_body))
        return GuardReport(findings=findings)

    # --- individual checks ---------------------------------------------

    def _check_placeholders(self, body: str) -> list[GuardFinding]:
        return [
            GuardFinding(
                code="placeholder_left_in_draft",
                severity=SEVERITY_BLOCK,
                detail="The draft still contains a template placeholder.",
                evidence=match.group(0),
            )
            for match in _PLACEHOLDER_RE.finditer(body)
        ]

    def _check_guarantees(self, body: str) -> list[GuardFinding]:
        return [
            GuardFinding(
                code="unbacked_guarantee",
                severity=SEVERITY_BLOCK,
                detail="The draft promises an outcome we cannot contractually guarantee.",
                evidence=match.group(0),
            )
            for match in _GUARANTEE_RE.finditer(body)
        ]

    def _check_numbers(self, body: str, haystack: str) -> list[GuardFinding]:
        findings: list[GuardFinding] = []
        seen: set[str] = set()
        for match in _NUMBER_RE.finditer(body):
            raw = match.group(0).strip()
            digits = re.sub(r"[^\d]", "", raw)
            if not digits or digits in _INNOCUOUS_NUMBERS or raw.lower() in seen:
                continue
            seen.add(raw.lower())
            if digits in haystack or raw.lower() in haystack:
                continue
            findings.append(
                GuardFinding(
                    code="unsupported_number",
                    severity=SEVERITY_BLOCK,
                    detail=(
                        "This figure does not appear in any knowledge passage or lead fact "
                        "retrieved during this run."
                    ),
                    evidence=raw,
                )
            )
        return findings

    def _check_named_entities(
        self, body: str, haystack: str, lead_terms: list[str]
    ) -> list[GuardFinding]:
        lead_haystack = _normalize(" ".join(lead_terms))
        findings: list[GuardFinding] = []
        seen: set[str] = set()
        for match in _PROPER_NOUN_RE.finditer(body):
            phrase = match.group(0).strip()
            normalized = _normalize(phrase)
            if normalized in seen or normalized in _PROPER_NOUN_ALLOWLIST:
                continue
            seen.add(normalized)
            if normalized in haystack or normalized in lead_haystack:
                continue
            findings.append(
                GuardFinding(
                    code="unsupported_named_entity",
                    severity=SEVERITY_WARN,
                    detail=(
                        "This looks like a client or product name that was not retrieved this "
                        "run. Cite a case study or remove it."
                    ),
                    evidence=phrase,
                )
            )
        return findings

    def _check_shape(self, subject: str | None, normalized_body: str) -> list[GuardFinding]:
        findings: list[GuardFinding] = []
        if subject is not None and len(subject) > self.max_subject_chars:
            findings.append(
                GuardFinding(
                    code="subject_too_long",
                    severity=SEVERITY_WARN,
                    detail=f"Subject exceeds {self.max_subject_chars} characters.",
                    evidence=subject[:120],
                )
            )
        words = len(normalized_body.split())
        if words > self.max_body_words:
            findings.append(
                GuardFinding(
                    code="body_too_long",
                    severity=SEVERITY_WARN,
                    detail=f"Body is {words} words; cold outreach above "
                    f"{self.max_body_words} rarely gets read.",
                    evidence=f"{words} words",
                )
            )
        elif words < self.min_body_words:
            findings.append(
                GuardFinding(
                    code="body_too_short",
                    severity=SEVERITY_WARN,
                    detail=f"Body is {words} words; too short to carry a specific reason to reply.",
                    evidence=f"{words} words",
                )
            )
        return findings


__all__ = [
    "SEVERITY_BLOCK",
    "SEVERITY_WARN",
    "GuardFinding",
    "GuardReport",
    "OutreachQualityGuard",
]
