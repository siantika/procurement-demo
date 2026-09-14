from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.policies import require_manager
from apps.bids.choices import BidStatus
from apps.bids.models import BidProposalRevision
from apps.core.exceptions import ConcurrencyConflict, InvalidTransition
from apps.core.forms import ExpectedVersionForm

from .forms import RejectBidForm
from .services import approve_bid, reject_bid


def _queue_queryset(user=None):
    queryset = BidProposalRevision.objects.select_related(
        "bid_proposal__tender_request",
        "submitted_by",
        "selected_result",
        "approval_decision__decided_by",
        "signature__signed_by",
    )
    if user is None:
        return queryset.filter(status=BidStatus.WAITING_APPROVAL)
    return queryset.filter(
        Q(status=BidStatus.WAITING_APPROVAL)
        | Q(
            status__in=(
                BidStatus.APPROVED,
                BidStatus.SIGNED,
                BidStatus.FINALIZED,
            ),
            approval_decision__decided_by=user,
        )
    )


@login_required
def approval_queue(request):
    require_manager(request.user)
    return render(
        request,
        "approval/queue.html",
        {"revisions": _queue_queryset(request.user)},
    )


@login_required
def approval_detail(request, revision_id):
    require_manager(request.user)
    revision = get_object_or_404(
        BidProposalRevision.objects.select_related("bid_proposal"),
        pk=revision_id,
    )
    return redirect("bids:revision-detail", revision_id=revision.pk)


@require_POST
@login_required
def approval_approve(request, revision_id):
    require_manager(request.user)
    revision = get_object_or_404(BidProposalRevision, pk=revision_id)
    form = ExpectedVersionForm(request.POST)
    if not form.is_valid():
        return HttpResponse("Versi Bid tidak valid.", status=400)
    try:
        approve_bid(
            actor=request.user,
            revision_id=revision.pk,
            expected_version=form.cleaned_data["expected_version"],
            correlation_id=request.correlation_id,
        )
    except (ConcurrencyConflict, InvalidTransition) as error:
        return HttpResponse(error.messages[0], status=409)
    messages.success(request, "Bid Proposal disetujui.")
    return redirect("bids:detail", proposal_id=revision.bid_proposal_id)


@require_POST
@login_required
def approval_reject(request, revision_id):
    require_manager(request.user)
    revision = get_object_or_404(BidProposalRevision, pk=revision_id)
    form = RejectBidForm(request.POST)
    if not form.is_valid():
        return render(
            request,
            "approval/reject.html",
            {"revision": revision, "form": form},
            status=400,
        )
    try:
        reject_bid(
            actor=request.user,
            revision_id=revision.pk,
            expected_version=form.cleaned_data["expected_version"],
            reason=form.cleaned_data["reason"],
            correlation_id=request.correlation_id,
        )
    except ValidationError as error:
        form.add_error(None, " ".join(error.messages))
        return render(
            request,
            "approval/reject.html",
            {"revision": revision, "form": form},
            status=(
                409
                if isinstance(
                    error, (ConcurrencyConflict, InvalidTransition)
                )
                else 400
            ),
        )
    messages.success(request, "Bid Proposal ditolak.")
    return redirect("bids:detail", proposal_id=revision.bid_proposal_id)


@login_required
def approval_reject_form(request, revision_id):
    require_manager(request.user)
    revision = get_object_or_404(
        _queue_queryset().prefetch_related("items"), pk=revision_id
    )
    form = RejectBidForm(initial={"expected_version": revision.version})
    return render(
        request,
        "approval/reject.html",
        {"revision": revision, "form": form},
    )
