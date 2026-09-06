"""TLS certificate diagnostics for ki-core's HTTP(S) providers.

When a provider request to a self-hosted or corporate-proxied endpoint
fails with an SSL/TLS error, it's rarely obvious *why* from the raw
exception message alone. This module inspects the certificate chain a
given host actually presents, checks it against the trust store requests
would use, and reports validity/expiry - so users can diagnose things
like expired certs, wrong hostnames, or missing internal CA certs without
reaching for `openssl s_client` by hand.
"""

from __future__ import annotations

import os
import socket
import ssl
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse


@dataclass
class CertificateInfo:
    """Details about the leaf certificate presented by a host."""

    subject: str
    issuer: str
    not_before: Optional[datetime]
    not_after: Optional[datetime]
    san: list = field(default_factory=list)
    serial_number: Optional[str] = None

    @property
    def is_expired(self) -> bool:
        if self.not_after is None:
            return False
        return datetime.now(timezone.utc) > self.not_after

    @property
    def days_until_expiry(self) -> Optional[int]:
        if self.not_after is None:
            return None
        return (self.not_after - datetime.now(timezone.utc)).days


@dataclass
class CertDiagnosticResult:
    """Full diagnostic result for one host:port."""

    host: str
    port: int
    verified: bool
    verify_error: Optional[str] = None
    certificate: Optional[CertificateInfo] = None
    ca_bundle_paths: dict = field(default_factory=dict)
    connect_error: Optional[str] = None

    def render(self) -> str:
        """Human-readable diagnostic report."""
        lines = [f"Certificate diagnostics for {self.host}:{self.port}", "=" * 50]

        if self.connect_error:
            lines.append(f"❌ Could not connect: {self.connect_error}")
            return "\n".join(lines)

        cert = self.certificate
        if cert:
            lines.append(f"Subject:      {cert.subject}")
            lines.append(f"Issuer:       {cert.issuer}")
            if cert.san:
                lines.append(f"SAN:          {', '.join(cert.san)}")
            if cert.not_before:
                lines.append(f"Valid from:   {cert.not_before.isoformat()}")
            if cert.not_after:
                status = "EXPIRED" if cert.is_expired else f"{cert.days_until_expiry} days left"
                lines.append(f"Valid until:  {cert.not_after.isoformat()} ({status})")
            if cert.serial_number:
                lines.append(f"Serial:       {cert.serial_number}")

        lines.append("")
        if self.verified:
            lines.append("✅ Verification: trusted by the system/requests CA bundle")
        else:
            lines.append("❌ Verification FAILED against the system/requests CA bundle")
            if self.verify_error:
                lines.append(f"   Reason: {self.verify_error}")
            lines.append(
                "   Hint: if this is an internal/self-signed CA, add its cert to your"
            )
            lines.append(
                "   trust store, set SSL_CERT_FILE / REQUESTS_CA_BUNDLE to its path, or"
            )
            lines.append(
                "   set http.verify_ssl: false in your ki.yaml (not recommended for prod)."
            )

        lines.append("")
        lines.append("CA bundle resolution:")
        for key, value in self.ca_bundle_paths.items():
            lines.append(f"  {key}: {value}")

        return "\n".join(lines)


def _resolve_ca_bundle_paths() -> dict:
    """Report every source that determines which CA bundle requests/ssl will use."""
    paths: dict = {}
    paths["SSL_CERT_FILE (env)"] = os.environ.get("SSL_CERT_FILE", "(not set)")
    paths["REQUESTS_CA_BUNDLE (env)"] = os.environ.get("REQUESTS_CA_BUNDLE", "(not set)")
    paths["CURL_CA_BUNDLE (env)"] = os.environ.get("CURL_CA_BUNDLE", "(not set)")
    try:
        default_paths = ssl.get_default_verify_paths()
        paths["OpenSSL default cafile"] = default_paths.cafile or "(none)"
        paths["OpenSSL default capath"] = default_paths.capath or "(none)"
    except Exception as e:  # pragma: no cover - defensive
        paths["OpenSSL default paths"] = f"(error: {e})"
    try:
        import certifi

        paths["certifi bundle (requests default)"] = certifi.where()
    except ImportError:
        paths["certifi bundle (requests default)"] = "(certifi not installed)"
    return paths


def parse_host_port(target: str, default_port: int = 443) -> tuple:
    """Parse a bare "host", "host:port", or full URL into (host, port)."""
    if "://" in target:
        parsed = urlparse(target)
        host = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == "https" else default_port)
        if not host:
            raise ValueError(f"Could not parse host from: {target}")
        return host, port

    if ":" in target and not target.count(":") > 1:
        host, _, port_str = target.rpartition(":")
        return host, int(port_str)

    return target, default_port


def _extract_cert_info(cert_dict: dict, cert_der: Optional[bytes] = None) -> CertificateInfo:
    def _join_name(name_tuples) -> str:
        parts = []
        for rdn in name_tuples:
            for key, value in rdn:
                parts.append(f"{key}={value}")
        return ", ".join(parts)

    def _parse_time(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        # ssl module format: 'Jun  1 12:00:00 2030 GMT'
        return datetime.strptime(value, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)

    san = [v for k, v in cert_dict.get("subjectAltName", []) if k == "DNS"]

    return CertificateInfo(
        subject=_join_name(cert_dict.get("subject", ())),
        issuer=_join_name(cert_dict.get("issuer", ())),
        not_before=_parse_time(cert_dict.get("notBefore")),
        not_after=_parse_time(cert_dict.get("notAfter")),
        san=san,
        serial_number=cert_dict.get("serialNumber"),
    )


def _decode_der_certificate(der_cert: Optional[bytes]) -> Optional[CertificateInfo]:
    """Parse a DER-encoded certificate's fields without validating it.

    ssl.SSLSocket.getpeercert() only populates its dict when the handshake
    was verified (verify_mode != CERT_NONE), so an unverified connection
    can't use it directly. This writes the cert to a temp PEM file and
    reuses the same decoder the ssl module itself relies on internally.
    """
    if not der_cert:
        return None

    import os
    import tempfile

    pem = ssl.DER_cert_to_PEM_cert(der_cert)
    fd, path = tempfile.mkstemp(suffix=".pem")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(pem)
        cert_dict = ssl._ssl._test_decode_cert(path)
    finally:
        os.unlink(path)

    return _extract_cert_info(cert_dict)


def diagnose_certificate(target: str, timeout: float = 10.0) -> CertDiagnosticResult:
    """Connect to `target` (host, host:port, or https:// URL) and report on its certificate.

    Performs two connections: one with full verification (using the same
    trust store `requests`/`ssl` would use by default) to determine
    whether the cert is trusted, and one without verification purely to
    read and display the certificate's own details even when the first
    connection fails.
    """
    host, port = parse_host_port(target)
    ca_bundle_paths = _resolve_ca_bundle_paths()

    verified = False
    verify_error: Optional[str] = None
    cert_info: Optional[CertificateInfo] = None

    # Attempt 1: default verifying context (mirrors what `requests` does).
    try:
        verifying_ctx = ssl.create_default_context()
        with socket.create_connection((host, port), timeout=timeout) as sock:
            with verifying_ctx.wrap_socket(sock, server_hostname=host) as tls_sock:
                cert_info = _extract_cert_info(tls_sock.getpeercert())
                verified = True
    except ssl.SSLCertVerificationError as e:
        verify_error = str(e)
    except Exception as e:
        verify_error = str(e)

    if cert_info is None:
        # Attempt 2: connect without verification just to read the cert that's
        # actually presented. getpeercert() only returns a populated dict when
        # the handshake was verified, so decode the raw DER via the (private
        # but stable) ssl._test_decode_cert helper instead.
        try:
            noverify_ctx = ssl._create_unverified_context()
            with socket.create_connection((host, port), timeout=timeout) as sock:
                with noverify_ctx.wrap_socket(sock, server_hostname=host) as tls_sock:
                    der_cert = tls_sock.getpeercert(binary_form=True)
            cert_info = _decode_der_certificate(der_cert)
        except Exception as e:
            return CertDiagnosticResult(
                host=host,
                port=port,
                verified=False,
                verify_error=verify_error,
                ca_bundle_paths=ca_bundle_paths,
                connect_error=str(e),
            )

    return CertDiagnosticResult(
        host=host,
        port=port,
        verified=verified,
        verify_error=verify_error,
        certificate=cert_info,
        ca_bundle_paths=ca_bundle_paths,
    )
