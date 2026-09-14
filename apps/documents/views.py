from io import BytesIO

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.choices import UserRole
from apps.accounts.policies import (
    require_procurement_staff,
    require_valid_role,
)
from apps.bids.models import BidProposalRevision
from apps.core.exceptions import InvalidTransition

from .choices import GenerationJobStatus
from .models import DocumentGenerationJob
from .services import get_authorized_document, request_finalization


def _require_document_viewer(user):
    require_valid_role(user)
    if user.role not in {
        UserRole.PROCUREMENT_STAFF,
        UserRole.MANAGER,
    }:
        raise PermissionDenied("Anda tidak memiliki akses ke dokumen.")


def _job_queryset():
    return DocumentGenerationJob.objects.select_related(
        "bid_revision__bid_proposal",
        "requested_by",
        "final_document",
    )


@require_POST
@login_required
def document_finalize(request, revision_id):
    require_procurement_staff(request.user)
    revision = get_object_or_404(BidProposalRevision, pk=revision_id)
    try:
        job = request_finalization(
            actor=request.user,
            revision_id=revision.pk,
            correlation_id=request.correlation_id,
        )
    except InvalidTransition as error:
        return HttpResponse(error.messages[0], status=409)
    messages.success(request, "Pembuatan dokumen final dijadwalkan.")
    return redirect("documents:job-detail", job_id=job.pk)


@login_required
def job_detail(request, job_id):
    _require_document_viewer(request.user)
    job = get_object_or_404(_job_queryset(), pk=job_id)
    return render(request, "documents/job_detail.html", {"job": job})


@login_required
def job_status(request, job_id):
    _require_document_viewer(request.user)
    job = get_object_or_404(_job_queryset(), pk=job_id)
    terminal = job.status in {
        GenerationJobStatus.COMPLETED,
        GenerationJobStatus.FAILED,
    }
    return JsonResponse(
        {
            "status": job.status,
            "status_label": job.get_status_display(),
            "terminal": terminal,
            "safe_message": job.safe_error_message,
            "detail_url": request.build_absolute_uri(
                redirect("documents:job-detail", job_id=job.pk).url
            ),
        }
    )


@login_required
def document_download(request, document_id):
    _require_document_viewer(request.user)
    try:
        document, content = get_authorized_document(
            actor=request.user, document_id=document_id
        )
    except InvalidTransition as error:
        return HttpResponse(error.messages[0], status=409)
    except ValidationError as error:
        raise Http404("Dokumen tidak ditemukan.") from error
    filename = (
        f"{document.bid_revision.bid_proposal.proposal_number}-"
        f"R{document.bid_revision.revision_number}-"
        f"V{document.document_version}.pdf"
    )
    response = FileResponse(
        BytesIO(content),
        content_type="application/pdf",
        as_attachment=True,
        filename=filename,
    )
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response
