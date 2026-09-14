"""Load and verify a frozen private signature image for rendering."""

import base64
import hashlib
from io import BytesIO

from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError

from .storage import read_private_object, stat_private_object


def load_signature_image_data_uri(snapshot):
    metadata = snapshot.get("signature", {})
    if not metadata.get("has_image"):
        return None
    required = {
        "image_object_key",
        "image_mime_type",
        "image_size_bytes",
        "image_sha256",
    }
    if any(metadata.get(field) in (None, "") for field in required):
        raise ValidationError(
            "Metadata gambar signature tidak lengkap."
        )
    object_key = metadata["image_object_key"]
    stored = stat_private_object(object_key)
    content = read_private_object(object_key)
    mime_type = metadata["image_mime_type"]
    expected_format = {
        "image/png": "PNG",
        "image/jpeg": "JPEG",
    }.get(mime_type)
    if expected_format is None:
        raise ValidationError("MIME gambar signature tidak didukung.")
    if (
        stored.content_type != mime_type
        or stored.size != metadata["image_size_bytes"]
        or len(content) != metadata["image_size_bytes"]
        or len(content) > 1_048_576
        or hashlib.sha256(content).hexdigest()
        != metadata["image_sha256"]
    ):
        raise ValidationError(
            "Integritas gambar signature tidak valid."
        )
    expected_version = metadata.get("image_version_id")
    if (
        expected_version
        and stored.version_id
        and stored.version_id != expected_version
    ):
        raise ValidationError("Versi object signature tidak valid.")
    try:
        with Image.open(BytesIO(content)) as image:
            image.verify()
            if image.format != expected_format:
                raise ValidationError(
                    "Format gambar signature tidak sesuai MIME."
                )
    except (UnidentifiedImageError, OSError) as error:
        raise ValidationError(
            "Object signature bukan gambar yang valid."
        ) from error
    encoded = base64.b64encode(content).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"
