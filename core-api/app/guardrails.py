from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from app.privacy import redact_pii

DISCLAIMER = "Informasi ini bukan diagnosis atau pengganti konsultasi tenaga kesehatan."

ABSTENTION_ANSWER = (
    "Informasi yang tersedia belum cukup untuk menjawab pertanyaan itu. "
    "Silakan periksa informasi fasilitas atau hubungi petugas untuk memastikan."
)

MEDICAL_ANSWER = (
    "Saya tidak dapat memberikan diagnosis, menafsirkan hasil tes, atau "
    "menyarankan obat dan dosis. Silakan konsultasikan dengan tenaga kesehatan "
    "atau layanan fasilitas kesehatan terdekat."
)

INJECTION_ANSWER = (
    "Saya tidak dapat mengubah aturan sistem atau membagikan instruksi internal. "
    "Saya dapat membantu informasi umum tentang layanan dan persiapan kunjungan."
)

WAYFINDING_ANSWER = (
    "Informasi rute internal belum tersedia atau belum diverifikasi. "
    "Silakan minta bantuan petugas dan gunakan denah resmi bila tersedia."
)

PROVIDER_ANSWER = (
    "Layanan AI sedang tidak tersedia. Informasi fasilitas, artikel, dan "
    "persiapan kunjungan tetap dapat diakses."
)

FALLBACK_ANSWER = (
    "Maaf, jawaban belum dapat diberikan dengan aman. Silakan coba lagi atau "
    "hubungi petugas untuk informasi yang terverifikasi."
)

_CRISIS = re.compile(
    r"\b("
    r"bunuh diri|mengakhiri hidup|menyakiti diri|melukai diri|ingin mati|"
    r"tidak ingin hidup|overdosis|suicide|kill myself|end my life|self[- ]harm"
    r")\b",
    re.IGNORECASE,
)
_MEDICAL = (
    re.compile(
        r"\b(apakah|apa)\s+(saya|aku)\s+(positif|terinfeksi|menderita|hiv)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(hasil|tes)\s+(hiv\s+)?(saya|aku|ini|tersebut)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bdiagnosis\s+(saya|aku|untuk saya)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(obat|dosis|tablet|kapsul|mg|miligram)\b.*"
        r"\b(apa|berapa|harus|boleh|minum|konsumsi|pilih|rekomendasi|saya)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(apa|berapa|harus|boleh|minum|konsumsi|pilih|rekomendasi)\b.*"
        r"\b(obat|dosis|tablet|kapsul|mg|miligram)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(minum|konsumsi|gunakan|pakai)\s+obat\b", re.IGNORECASE),
    re.compile(
        r"\b(pep|prep|arv)\b.*\b(perlu|harus|minum|konsumsi|dosis|mulai)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bberapa\s+(dosis|tablet|mg)\b", re.IGNORECASE),
    re.compile(r"\b(tafsirkan|interpretasi)\s+hasil\b", re.IGNORECASE),
)
_INJECTION = (
    re.compile(
        r"\b(abaikan|ignore)\b.*\b(instruksi|instruction|prompt|aturan|rules)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(system prompt|prompt sistem|instruksi sistem|instruksi internal|"
        r"internal prompt)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(tampilkan|bocorkan|reveal|show)\b.*"
        r"\b(prompt|instruksi|aturan|secret|api key)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(jailbreak|developer mode|act as|role\s*=\s*system)\b",
        re.IGNORECASE,
    ),
)
_LEAK = re.compile(
    r"\b(system prompt|prompt sistem|instruksi sistem|instruksi internal|"
    r"groq_api_key|api[_ ]?key|sk-[a-z0-9]+|anda adalah rangkul)\b",
    re.IGNORECASE,
)
_UNSAFE_MEDICAL = (
    re.compile(r"\b(anda|kamu)\s+(positif|terinfeksi|menderita)\b", re.IGNORECASE),
    re.compile(r"\bdiagnosis\s+(anda|kamu|adalah)\b", re.IGNORECASE),
    re.compile(
        r"\b(hasil tes|tes)\s+(anda|kamu)\s+(positif|negatif)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b\d+\s*(mg|miligram|tablet|kapsul)\b", re.IGNORECASE),
    re.compile(
        r"\b(dosis|minum obat|konsumsi obat|gunakan obat|terapi obat)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(sebaiknya|saya sarankan)\s+(minum|konsumsi|gunakan)\b",
        re.IGNORECASE,
    ),
)
_UNSAFE_WAYFINDING = re.compile(
    r"\b(lantai\s+\d+|gedung\s+[a-z0-9]+|belok\s+(ke\s+)?(kiri|kanan)|"
    r"naik\s+(lift|tangga)|turun\s+(lift|tangga))\b",
    re.IGNORECASE,
)
_CITATION = re.compile(r"\b(sumber|referensi)\b", re.IGNORECASE)


class InputCategory(str, Enum):
    NORMAL = "normal"
    CRISIS = "crisis"
    MEDICAL = "medical"
    INJECTION = "injection"


@dataclass(frozen=True, slots=True)
class OutputGuardrailResult:
    text: str
    safety_state: str
    replaced: bool


def classify_input(message: str) -> InputCategory:
    if _CRISIS.search(message):
        return InputCategory.CRISIS
    if any(pattern.search(message) for pattern in _MEDICAL):
        return InputCategory.MEDICAL
    if any(pattern.search(message) for pattern in _INJECTION):
        return InputCategory.INJECTION
    return InputCategory.NORMAL


def crisis_answer(contact: str = "") -> str:
    answer = (
        "Saya turut prihatin dengan yang Anda rasakan. Jika Anda dalam bahaya "
        "atau memiliki pikiran untuk menyakiti diri, segera hubungi layanan "
        "darurat setempat atau orang yang Anda percaya untuk mendapatkan "
        "pendampingan langsung."
    )
    if contact:
        answer += f" Kontak yang telah diverifikasi: {contact}."
    return answer


def apply_output_guardrail(
    text: str, *, sources_present: bool
) -> OutputGuardrailResult:
    redacted = redact_pii(text)
    cleaned = redacted.text.strip()
    if not cleaned:
        return OutputGuardrailResult(ABSTENTION_ANSWER, "abstained", True)
    if _LEAK.search(cleaned):
        return OutputGuardrailResult(FALLBACK_ANSWER, "fallback", True)
    if any(pattern.search(cleaned) for pattern in _UNSAFE_MEDICAL):
        return OutputGuardrailResult(MEDICAL_ANSWER, "medical_guardrail", True)
    if _UNSAFE_WAYFINDING.search(cleaned):
        return OutputGuardrailResult(WAYFINDING_ANSWER, "wayfinding_guardrail", True)
    if not sources_present:
        return OutputGuardrailResult(ABSTENTION_ANSWER, "abstained", True)
    if not _CITATION.search(cleaned):
        return OutputGuardrailResult(FALLBACK_ANSWER, "fallback", True)
    return OutputGuardrailResult(cleaned, "grounded", False)
