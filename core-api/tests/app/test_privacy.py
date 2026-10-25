from __future__ import annotations

from app.privacy import redact_pii


def test_redacts_nik_email_and_phone():
    result = redact_pii(
        "NIK 3273010101010001, email budi@example.com, telepon 0812-3456-7890."
    )

    assert "3273010101010001" not in result.text
    assert "budi@example.com" not in result.text
    assert "0812-3456-7890" not in result.text
    assert "[NIK]" in result.text
    assert "[EMAIL]" in result.text
    assert "[TELEPON]" in result.text
    assert result.categories == ("nik", "email", "telepon")
    assert result.changed


def test_keeps_text_without_pii():
    result = redact_pii("Apa persiapan tes HIV?")

    assert result.text == "Apa persiapan tes HIV?"
    assert result.categories == ()
    assert not result.changed


def test_does_not_redact_short_numbers():
    result = redact_pii("Tahun 2026 dan kode 12345.")

    assert result.text == "Tahun 2026 dan kode 12345."
    assert not result.changed
