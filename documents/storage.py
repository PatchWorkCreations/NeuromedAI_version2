"""
Encrypted storage for patients' original files (lab PDFs, photos of prescriptions).

Why encrypt before storing: these are health records. Iceberg
(cdn.katalyst-crm.com) serves every asset at a public, unauthenticated URL
with no private or signed-URL option. Encrypting with Fernet (AES-128-CBC +
HMAC) before upload means that URL only ever returns unreadable bytes.
Patients see their files through documents.views.document_file, which checks
ownership and decrypts on the way out.

Keys never contain names, file names or anything identifying:
    <prefix>/<uuid>.bin
"""
from __future__ import annotations

import base64
import hashlib
import logging
import uuid

import requests
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

logger = logging.getLogger(__name__)


class StorageError(Exception):
    pass


def _fernet() -> Fernet | None:
    key = settings.DOCUMENT_ENCRYPTION_KEY
    if key:
        return Fernet(key.encode() if isinstance(key, str) else key)
    if settings.DEBUG:
        derived = hashlib.sha256(("aira-dev-files:" + settings.SECRET_KEY).encode()).digest()
        return Fernet(base64.urlsafe_b64encode(derived))
    return None


def is_enabled() -> bool:
    if _fernet() is None:
        return False
    if settings.DOCUMENT_STORAGE == "iceberg":
        return bool(settings.ICEBERG_TOKEN)
    return True


def _new_key() -> str:
    prefix = settings.ICEBERG_KEY_PREFIX.strip("/")
    return f"{prefix}/{uuid.uuid4().hex}.bin"


# ---------------------------------------------------------------- backends

class LocalBackend:
    """Encrypted files on local disk. Fine for dev; Railway's disk is wiped on deploy."""

    def _path(self, key):
        root = settings.PRIVATE_MEDIA_ROOT
        path = (root / key).resolve()
        if root.resolve() not in path.parents:
            raise StorageError("Invalid key")
        return path

    def put(self, key: str, blob: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(blob)

    def get(self, key: str) -> bytes:
        try:
            return self._path(key).read_bytes()
        except FileNotFoundError as exc:
            raise StorageError("File not found") from exc

    def delete(self, key: str) -> None:
        try:
            self._path(key).unlink()
        except FileNotFoundError:
            pass


class IcebergBackend:
    """
    cdn.katalyst-crm.com via its API (https://cdn.katalyst-crm.com/llms.txt):
    init-upload -> PUT to presigned R2 URL -> complete. Stores ciphertext only.
    """
    TIMEOUT = 30

    def _headers(self):
        return {"Authorization": f"Bearer {settings.ICEBERG_TOKEN}", "Content-Type": "application/json"}

    def _api(self, path):
        return settings.ICEBERG_API_BASE.rstrip("/") + path

    def put(self, key: str, blob: bytes) -> str:
        init = requests.post(
            self._api("/assets/init-upload"),
            json={"key": key, "content_type": "application/octet-stream"},
            headers=self._headers(), timeout=self.TIMEOUT,
        )
        if init.status_code >= 300:
            raise StorageError(f"Iceberg init-upload failed ({init.status_code})")
        info = init.json()
        put = requests.put(
            info["upload_url"], data=blob,
            headers={"Content-Type": "application/octet-stream"}, timeout=120,
        )
        if put.status_code >= 300:
            raise StorageError(f"Iceberg upload failed ({put.status_code})")
        done = requests.post(
            self._api("/assets/complete"), json={"key": key},
            headers=self._headers(), timeout=self.TIMEOUT,
        )
        if done.status_code >= 300:
            raise StorageError(f"Iceberg complete failed ({done.status_code})")
        return info.get("delivery_url") or ""

    def get(self, key: str, delivery_url: str = "") -> bytes:
        if not delivery_url:
            raise StorageError("No delivery URL recorded for this file")
        res = requests.get(delivery_url, timeout=60)
        if res.status_code != 200:
            raise StorageError(f"Iceberg fetch failed ({res.status_code})")
        return res.content

    def delete(self, key: str) -> None:
        # Soft delete: Iceberg keeps trashed assets 30 days, then purges.
        # Even while trashed, the bytes are ciphertext.
        res = requests.post(self._api("/assets/trash"), json={"key": key},
                            headers=self._headers(), timeout=self.TIMEOUT)
        if res.status_code >= 300:
            logger.warning("Iceberg trash failed for %s (%s)", key, res.status_code)


def _backend():
    return IcebergBackend() if settings.DOCUMENT_STORAGE == "iceberg" else LocalBackend()


# ---------------------------------------------------------------- public API

def save(data: bytes) -> str:
    """Encrypt and store. Returns the stored reference to keep on the document."""
    f = _fernet()
    if f is None:
        raise StorageError("DOCUMENT_ENCRYPTION_KEY is not set")
    key = _new_key()
    backend = _backend()
    delivery = backend.put(key, f.encrypt(data))
    # Iceberg needs the delivery URL to read the file back; keep it with the key.
    return f"{key}|{delivery}" if delivery else key


def load(ref: str) -> bytes:
    f = _fernet()
    if f is None:
        raise StorageError("DOCUMENT_ENCRYPTION_KEY is not set")
    key, _, delivery = ref.partition("|")
    backend = _backend()
    blob = backend.get(key, delivery) if isinstance(backend, IcebergBackend) else backend.get(key)
    try:
        return f.decrypt(blob)
    except InvalidToken as exc:
        raise StorageError("File could not be decrypted (wrong DOCUMENT_ENCRYPTION_KEY?)") from exc


def remove(ref: str) -> None:
    if not ref:
        return
    key = ref.partition("|")[0]
    try:
        _backend().delete(key)
    except Exception:
        logger.exception("Could not delete stored file %s", key)
