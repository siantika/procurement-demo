from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.policies import require_manager
from apps.bids.choices import BidStatus
from apps.bids.models import BidProposalRevision
from apps.core.exceptions import ConcurrencyConflict, InvalidTransition

from .forms import SignBidForm
from .services import sign_bid


@login_required
def signature_sign(request, revision_id):
    require_manager(request.user)
    revision = get_object_or_404(
        BidProposalRevision.objects.select_related(
            "bid_proposal", "approval_decision__decided_by"
        ).prefetch_related("items"),
        pk=revision_id,
    )
    if revision.status != BidStatus.APPROVED:
        return redirect(
            "bids:revision-detail", revision_id=revision.pk
        )
    if revision.approval_decision.decided_by_id != request.user.pk:
        raise PermissionDenied(
            "Hanya approving Manager yang dapat sign."
        )
    form = SignBidForm(
        request.POST or None,
        request.FILES or None,
        initial={"expected_version": revision.version},
    )
    response_status = 200
    if request.method == "POST" and form.is_valid():
        try:
            sign_bid(
                actor=request.user,
                revision_id=revision.pk,
                expected_version=form.cleaned_data["expected_version"],
                correlation_id=request.correlation_id,
                signature_image=form.cleaned_data["signature_image"],
            )
        except PermissionDenied:
            raise
        except ValidationError as error:
            form.add_error(None, " ".join(error.messages))
            if isinstance(error, (ConcurrencyConflict, InvalidTransition)):
                response_status = 409
        else:
            messages.success(request, "Bid berhasil ditandatangani.")
            return redirect(
                "bids:revision-detail", revision_id=revision.pk
            )
    return render(
        request,
        "signatures/sign.html",
        {"revision": revision, "form": form},
        status=response_status,
    )
