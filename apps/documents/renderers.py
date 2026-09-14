from pathlib import Path

from django.conf import settings
from django.template.loader import render_to_string
from weasyprint import CSS, HTML


def render_pdf_v1(snapshot, *, signature_image_data_uri=None):
    if snapshot["document"]["template_version"] != "1":
        raise ValueError("Versi template PDF tidak didukung.")
    html = render_to_string(
        "documents/pdf_v1.html",
        {
            "document": snapshot,
            "signature_image_data_uri": signature_image_data_uri,
        },
    )
    stylesheet = Path(
        settings.BASE_DIR,
        "apps/documents/static/documents/css/pdf_v1.css",
    ).resolve()
    expected_root = Path(
        settings.BASE_DIR, "apps/documents/static"
    ).resolve()
    if expected_root not in stylesheet.parents:
        raise ValueError("Path stylesheet PDF tidak valid.")
    return HTML(string=html).write_pdf(
        stylesheets=[CSS(filename=str(stylesheet))]
    )
