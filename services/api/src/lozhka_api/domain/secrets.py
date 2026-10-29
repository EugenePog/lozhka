"""Write-only supplier secrets: sealed with a PUBLIC key (RSA-OAEP). The staff console can store a secret but never
read it back; only the purchasing worker holds the private key (docs 02 s.4.6, 06 s.7)."""
from __future__ import annotations

from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from django.conf import settings

KEY_VERSION = "v1"


def _public_key():
    pem = (getattr(settings, "SUPPLIER_SECRET_PUBLIC_KEY", "") or "").strip()
    if not pem:
        dev = Path(settings.REPO_ROOT) / ".secrets"
        pub = dev / "supplier_secret_public.pem"
        if not getattr(settings, "IS_LOCAL", False):
            raise RuntimeError("SUPPLIER_SECRET_PUBLIC_KEY is not configured")
        if not pub.exists():  # local development only: create a key pair, keep the private half next to it
            dev.mkdir(exist_ok=True)
            key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
            (dev / "supplier_secret_private.pem").write_bytes(key.private_bytes(
                serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
            pub.write_bytes(key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
        pem = pub.read_text()
    return serialization.load_pem_public_key(pem.encode())


def seal(plaintext: str) -> bytes:
    return _public_key().encrypt(
        plaintext.encode(), padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
