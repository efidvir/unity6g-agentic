"""The signed snapshot of the catalog: its index and every entry in one archive, for the toolchain offline.

The archive is reproducible: the same catalog gives the same bytes, so that its digest identifies the
catalog's content. The signature is Ed25519 over the SHA-256 digest of the archive. Publication as an OCI
artifact, with the snapshot and its signature as referrers, comes with the lab's registry (guide 11.4)."""

import base64
import gzip
import hashlib
import io
import json
import tarfile
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from u6g_catalog.build import Catalog

ALGORITHM = "Ed25519"


def archive(catalog: Catalog, index: dict[str, Any]) -> bytes:
    """index.json and every entry file, in a gzip-compressed tar with fixed metadata."""
    members: list[tuple[str, bytes]] = [
        ("index.json", (json.dumps(index, indent=2, sort_keys=True) + "\n").encode())
    ]
    for name in sorted(set(catalog.files.values()) | {f"{a}/area.yaml" for a in catalog.areas}):
        members.append((f"catalog/{name}", (catalog.root / name).read_bytes()))
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for name, content in members:
            info = tarfile.TarInfo(name)
            info.size, info.mtime, info.mode = len(content), 0, 0o644
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            tar.addfile(info, io.BytesIO(content))
    packed = io.BytesIO()
    with gzip.GzipFile(fileobj=packed, mode="wb", mtime=0) as gz:
        gz.write(raw.getvalue())
    return packed.getvalue()


def sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def key_id(public: Ed25519PublicKey) -> str:
    raw = public.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return hashlib.sha256(raw).hexdigest()[:16]


def keygen() -> tuple[bytes, bytes]:
    """A new key pair, as PEM: the private key, then the public key."""
    private = Ed25519PrivateKey.generate()
    private_pem = private.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    public_pem = private.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return private_pem, public_pem


def sign(snapshot: bytes, private_pem: bytes) -> dict[str, str]:
    private = serialization.load_pem_private_key(private_pem, password=None)
    if not isinstance(private, Ed25519PrivateKey):
        raise ValueError("the signing key is an Ed25519 key")
    signed = sha256(snapshot)
    signature = private.sign(signed.encode())
    return {
        "algorithm": ALGORITHM,
        "key": key_id(private.public_key()),
        "digest": signed,
        "signature": base64.b64encode(signature).decode(),
    }


def verify(snapshot: bytes, signature: dict[str, str], public_pem: bytes) -> None:
    """Return when the signature holds for this snapshot and key; raise ValueError otherwise."""
    public = serialization.load_pem_public_key(public_pem)
    if not isinstance(public, Ed25519PublicKey):
        raise ValueError("the verification key is an Ed25519 key")
    if signature.get("algorithm") != ALGORITHM:
        raise ValueError(f"the algorithm is {ALGORITHM}")
    if signature.get("key") != key_id(public):
        raise ValueError("the signature was made with another key")
    if signature.get("digest") != sha256(snapshot):
        raise ValueError("the snapshot differs from the one signed")
    try:
        public.verify(base64.b64decode(signature["signature"]), signature["digest"].encode())
    except (InvalidSignature, KeyError, ValueError) as err:
        raise ValueError("the signature does not verify") from err
