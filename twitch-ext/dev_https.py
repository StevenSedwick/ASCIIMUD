"""Local HTTPS server for Twitch extension Local Test mode.

Generates a self-signed cert on first run (saved next to this script) and
serves the current directory over HTTPS on port 8080. Twitch's developer
rig expects exactly that.

Usage:
    python dev_https.py
    # then in Twitch dev console: Asset Hosting -> Testing Base URI =
    #   https://localhost:8080/
    # Open https://localhost:8080/viewer.html in your browser ONCE and
    # accept the self-signed certificate warning so the iframe inside
    # twitch.tv can load without the cert error blocking it.
"""
import datetime as dt
import http.server
import os
import ssl
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CERT = HERE / "_devcert.pem"
KEY = HERE / "_devkey.pem"
PORT = 8080


def ensure_cert() -> None:
    if CERT.exists() and KEY.exists():
        return
    print("[dev_https] generating self-signed cert...")
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "ASCIIMUD dev"),
    ])
    san = x509.SubjectAlternativeName([
        x509.DNSName("localhost"),
        x509.DNSName("127.0.0.1"),
    ])
    now = dt.datetime.now(dt.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(days=1))
        .not_valid_after(now + dt.timedelta(days=825))
        .add_extension(san, critical=False)
        .add_extension(
            x509.BasicConstraints(ca=True, path_length=None),
            critical=True,
        )
        .sign(key, hashes.SHA256())
    )
    KEY.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )
    CERT.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    print(f"[dev_https] cert: {CERT}")
    print(f"[dev_https] key:  {KEY}")


def main() -> int:
    os.chdir(HERE)
    ensure_cert()
    handler = http.server.SimpleHTTPRequestHandler
    httpd = http.server.ThreadingHTTPServer(("0.0.0.0", PORT), handler)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(certfile=str(CERT), keyfile=str(KEY))
    httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
    print(f"[dev_https] serving {HERE} on https://localhost:{PORT}/")
    print("[dev_https] open https://localhost:8080/viewer.html ONCE in your")
    print("[dev_https] browser and accept the cert warning. Then in the Twitch")
    print("[dev_https] dev console, set the test base URI to:")
    print("[dev_https]    https://localhost:8080/")
    print("[dev_https] Ctrl-C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
