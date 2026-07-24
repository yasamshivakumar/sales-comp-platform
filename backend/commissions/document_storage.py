"""
Compensation document storage — local media today, S3-ready metadata.

Database stores metadata only; binary content lives in object storage
(FileField / MEDIA_ROOT locally, or AWS S3 when configured).
"""
from __future__ import annotations

import os
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage


ALLOWED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".csv"}
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/csv",
    "application/vnd.ms-excel",
    "application/octet-stream",
}
MAX_DOCUMENT_BYTES = int(getattr(settings, "COMPENSATION_DOC_MAX_BYTES", 25 * 1024 * 1024))


def storage_backend_name():
    """Return active backend label for metadata (local | s3)."""
    if getattr(settings, "USE_S3_DOCUMENT_STORAGE", False):
        return "s3"
    return "local"


def validate_upload(uploaded):
    """Raise ValueError if file is missing or not an allowed type/size."""
    if uploaded is None:
        raise ValueError("File is required.")
    name = getattr(uploaded, "name", "") or "upload.bin"
    _, ext = os.path.splitext(name.lower())
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError("Allowed formats: PDF, DOCX, XLSX, CSV.")
    size = int(getattr(uploaded, "size", 0) or 0)
    if size <= 0:
        raise ValueError("Empty file.")
    if size > MAX_DOCUMENT_BYTES:
        raise ValueError("File exceeds maximum size of 25 MB.")
    content_type = (getattr(uploaded, "content_type", None) or "").lower()
    if content_type and content_type not in ALLOWED_CONTENT_TYPES:
        # Allow generic octet-stream / empty; block obviously wrong types
        if content_type.startswith("image/") or content_type.startswith("audio/"):
            raise ValueError("Unsupported content type.")
    return name, ext, size, content_type or "application/octet-stream"


def save_document_file(organization_id, document_id, version_number, uploaded):
    """
    Persist uploaded bytes and return storage metadata dict.
    Uses Django default storage (local MEDIA or S3 when configured).
    """
    name, _ext, size, content_type = validate_upload(uploaded)
    safe_name = os.path.basename(name).replace(" ", "_")
    key = (
        f"compensation_docs/org_{organization_id}/doc_{document_id}/"
        f"v{version_number}_{safe_name}"
    )
    data = uploaded.read()
    if hasattr(uploaded, "seek"):
        try:
            uploaded.seek(0)
        except Exception:
            pass
    saved_name = default_storage.save(key, ContentFile(data))
    try:
        url = default_storage.url(saved_name)
    except Exception:
        url = f"{settings.MEDIA_URL}{saved_name}"
    return {
        "storage_backend": storage_backend_name(),
        "storage_key": saved_name,
        "file_name": safe_name,
        "content_type": content_type,
        "file_size": size or len(data),
        "file_url": url,
    }


def open_document_file(version):
    """Return (file_handle, filename, content_type) for download."""
    key = (version.storage_key or "").strip()
    if not key and version.file:
        key = version.file.name
    if not key:
        raise FileNotFoundError("Document file not found.")
    handle = default_storage.open(key, "rb")
    filename = version.file_name or os.path.basename(key)
    content_type = version.content_type or "application/octet-stream"
    return handle, filename, content_type
