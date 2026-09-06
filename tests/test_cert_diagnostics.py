"""Unit tests for TLS certificate diagnostics (mocked - no real network calls)."""

from unittest.mock import MagicMock, patch

import pytest

from ki_core.cert_diagnostics import (
    CertDiagnosticResult,
    CertificateInfo,
    diagnose_certificate,
    parse_host_port,
)


class TestParseHostPort:
    def test_bare_host_defaults_to_443(self):
        assert parse_host_port("example.com") == ("example.com", 443)

    def test_host_with_port(self):
        assert parse_host_port("example.com:8443") == ("example.com", 8443)

    def test_https_url(self):
        assert parse_host_port("https://example.com/foo") == ("example.com", 443)

    def test_https_url_with_explicit_port(self):
        assert parse_host_port("https://internal.example.com:8443/v1") == (
            "internal.example.com",
            8443,
        )

    def test_invalid_url_raises(self):
        with pytest.raises(ValueError):
            parse_host_port("https:///no-host")


class TestCertificateInfo:
    def test_is_expired_false_when_no_not_after(self):
        cert = CertificateInfo(subject="s", issuer="i", not_before=None, not_after=None)
        assert cert.is_expired is False
        assert cert.days_until_expiry is None

    def test_is_expired_true_for_past_date(self):
        from datetime import datetime, timezone

        cert = CertificateInfo(
            subject="s",
            issuer="i",
            not_before=None,
            not_after=datetime(2000, 1, 1, tzinfo=timezone.utc),
        )
        assert cert.is_expired is True


class TestDiagnoseCertificate:
    @patch("ki_core.cert_diagnostics.socket.create_connection")
    @patch("ki_core.cert_diagnostics.ssl.create_default_context")
    def test_verified_connection_reports_success(self, mock_ctx_factory, mock_connect):
        mock_ctx = MagicMock()
        mock_ctx_factory.return_value = mock_ctx
        tls_sock = MagicMock()
        tls_sock.getpeercert.return_value = {
            "subject": ((("commonName", "example.com"),),),
            "issuer": ((("commonName", "Some CA"),),),
            "notBefore": "Jan  1 00:00:00 2026 GMT",
            "notAfter": "Jan  1 00:00:00 2030 GMT",
            "subjectAltName": (("DNS", "example.com"),),
            "serialNumber": "ABC123",
        }
        tls_sock.__enter__.return_value = tls_sock
        tls_sock.__exit__.return_value = False
        mock_ctx.wrap_socket.return_value = tls_sock

        sock_cm = MagicMock()
        sock_cm.__enter__.return_value = MagicMock()
        sock_cm.__exit__.return_value = False
        mock_connect.return_value = sock_cm

        result = diagnose_certificate("example.com")

        assert isinstance(result, CertDiagnosticResult)
        assert result.verified is True
        assert result.connect_error is None
        assert result.certificate.subject == "commonName=example.com"
        assert result.certificate.days_until_expiry is not None
        assert "trusted" in result.render()

    @patch("ki_core.cert_diagnostics.socket.create_connection")
    def test_connect_failure_is_reported(self, mock_connect):
        mock_connect.side_effect = OSError("Name or service not known")

        result = diagnose_certificate("nonexistent.invalid")

        assert result.connect_error is not None
        assert result.verified is False
        assert "Could not connect" in result.render()
