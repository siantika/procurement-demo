from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.choices import UserRole
from apps.accounts.policies import (
    require_procurement_staff,
    require_valid_role,
)
from apps.core.exceptions import ConcurrencyConflict, InvalidTransition
from apps.core.forms import ExpectedVersionForm

from .choices import BidStatus
from .forms import TargetMarginForm
from .models import BidProposal, BidProposalRevision
from .services import (
    create_bid_proposal,
    revise_rejected_bid,
    set_target_margin,
    submit_bid,
)


def _require_viewer(user):
    require_valid_role(user)
    if user.role not in {
        UserRole.PROCUREMENT_STAFF,
        UserRole.MANAGER,
    }:
        raise PermissionDenied(
            "Anda tidak memiliki akses ke Bid Proposal."
        )


def _proposal_queryset():
    return BidProposal.objects.select_related(
        "tender_request", "created_by"
    ).prefetch_related(
        "revisions__created_by",
        "revisions__submitted_by",
        "revisions__selected_result",
        "revisions__items",
        "revisions__approval_decision__decided_by",
        "revisions__signature__signed_by",
        "revisions__generation_jobs__final_document",
    )


def _current_revision(proposal):
    return proposal.revisions.get(
        revision_number=proposal.current_revision_number
    )


@login_required
def bid_list(request):
    require_procurement_staff(request.user)
    proposals = _proposal_queryset()
    rows = [
        {"proposal": proposal, "revision": _current_revision(proposal)}
        for proposal in proposals
    ]
    return render(request, "bids/bid_list.html", {"rows": rows})


@login_required
def bid_detail(request, proposal_id):
    _require_viewer(request.user)
    proposal = get_object_or_404(_proposal_queryset(), pk=proposal_id)
    revision = _current_revision(proposal)
    return render(
        request,
        "bids/bid_detail.html",
        {
            "proposal": proposal,
            "revision": revision,
            "revisions": proposal.revisions.all(),
            "is_current": True,
        },
    )


@login_required
def bid_revision_detail(request, revision_id):
    _require_viewer(request.user)
    revision = get_object_or_404(
        BidProposalRevision.objects.select_related(
            "bid_proposal__tender_request",
            "tender_revision",
            "selected_result",
            "submitted_by",
            "approval_decision__decided_by",
            "signature__signed_by",
        ).prefetch_related(
            "items", "generation_jobs__final_document"
        ),
        pk=revision_id,
    )
    proposal = revision.bid_proposal
    return render(
        request,
        "bids/bid_detail.html",
        {
            "proposal": proposal,
            "revision": revision,
            "revisions": proposal.revisions.all(),
            "is_current": (
                proposal.current_revision_number
                == revision.revision_number
            ),
        },
    )


@require_POST
@login_required
def bid_create(request, tender_id):
    require_procurement_staff(request.user)
    try:
        proposal, _revision = create_bid_proposal(
            actor=request.user,
            tender_request_id=tender_id,
            correlation_id=request.correlation_id,
        )
    except (ValidationError, InvalidTransition) as error:
        messages.error(request, " ".join(error.messages))
        return redirect("tender:detail", tender_id=tender_id)
    return redirect("bids:detail", proposal_id=proposal.pk)


@login_required
def bid_price(request, proposal_id):
    require_procurement_staff(request.user)
    proposal = get_object_or_404(_proposal_queryset(), pk=proposal_id)
    revision = _current_revision(proposal)
    if revision.status != BidStatus.DRAFT:
        return HttpResponse(
            "Hanya Bid DRAFT yang dapat diberi pricing.", status=409
        )
    form = TargetMarginForm(
        request.POST or None,
        initial={
            "expected_version": revision.version,
            "target_margin_percent": revision.target_margin_percent,
        },
    )
    response_status = 200
    if request.method == "POST" and form.is_valid():
        try:
            set_target_margin(
                actor=request.user,
                revision_id=revision.pk,
                expected_version=form.cleaned_data["expected_version"],
                target_margin_percent=form.cleaned_data[
                    "target_margin_percent"
                ],
                correlation_id=request.correlation_id,
            )
        except ValidationError as error:
            form.add_error(None, " ".join(error.messages))
            if isinstance(error, (ConcurrencyConflict, InvalidTransition)):
                response_status = 409
        else:
            messages.success(request, "Pricing Bid berhasil dihitung.")
            return redirect("bids:detail", proposal_id=proposal.pk)
    return render(
        request,
        "bids/bid_price.html",
        {"proposal": proposal, "revision": revision, "form": form},
        status=response_status,
    )


@require_POST
@login_required
def bid_submit(request, proposal_id):
    require_procurement_staff(request.user)
    proposal = get_object_or_404(_proposal_queryset(), pk=proposal_id)
    revision = _current_revision(proposal)
    form = ExpectedVersionForm(request.POST)
    if not form.is_valid():
        return HttpResponse("Versi Bid tidak valid.", status=400)
    try:
        submit_bid(
            actor=request.user,
            revision_id=revision.pk,
            expected_version=form.cleaned_data["expected_version"],
            correlation_id=request.correlation_id,
        )
    except (ConcurrencyConflict, InvalidTransition) as error:
        return HttpResponse(error.messages[0], status=409)
    messages.success(request, "Bid dikirim untuk approval Manager.")
    return redirect("bids:detail", proposal_id=proposal.pk)


@require_POST
@login_required
def bid_revise(request, proposal_id):
    require_procurement_staff(request.user)
    proposal = get_object_or_404(BidProposal, pk=proposal_id)
    form = ExpectedVersionForm(request.POST)
    if not form.is_valid():
        return HttpResponse("Versi Bid tidak valid.", status=400)
    try:
        revise_rejected_bid(
            actor=request.user,
            proposal_id=proposal.pk,
            expected_version=form.cleaned_data["expected_version"],
            correlation_id=request.correlation_id,
        )
    except (ConcurrencyConflict, InvalidTransition) as error:
        return HttpResponse(error.messages[0], status=409)
    messages.success(request, "Revision Bid baru berhasil dibuat.")
    return redirect("bids:detail", proposal_id=proposal.pk)
