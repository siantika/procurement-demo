from apps.sourcing.snapshots import timestamp_string

SNAPSHOT_SCHEMA_VERSION = 1


def build_submission_snapshot(*, revision, captured_at):
    proposal = revision.bid_proposal
    return {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "snapshot_type": "bid_submission",
        "captured_at": timestamp_string(captured_at),
        "source": {
            "bid_proposal_id": str(proposal.pk),
            "proposal_number": proposal.proposal_number,
            "bid_revision_id": str(revision.pk),
            "bid_revision_number": revision.revision_number,
            "tender_request_id": str(proposal.tender_request_id),
            "tender_revision_id": str(revision.tender_revision_id),
            "selected_result_id": str(revision.selected_result_id),
            "selected_result_hash": revision.selected_result.result_hash,
        },
        "data": {
            "currency": revision.currency,
            "calculation_version": revision.calculation_version,
            "target_margin_percent": format(
                revision.target_margin_percent, ".4f"
            ),
            "total_purchase": format(revision.total_purchase, ".2f"),
            "total_bid_value": format(revision.total_bid_value, ".2f"),
            "gross_profit": format(revision.gross_profit, ".2f"),
            "actual_margin_percent": format(
                revision.actual_margin_percent, ".4f"
            ),
            "max_margin_percent": (
                format(revision.max_margin_percent, ".4f")
                if revision.max_margin_percent is not None
                else None
            ),
            "is_hps_feasible": revision.is_hps_feasible,
            "items": [
                {
                    "tender_item_id": str(item.tender_request_item_id),
                    "line_number": item.line_number,
                    "product": item.product_snapshot,
                    "requested_quantity": format(
                        item.requested_quantity, ".3f"
                    ),
                    "unit": item.unit,
                    "item_purchase_total": format(
                        item.item_purchase_total, ".2f"
                    ),
                    "unit_purchase_cost": format(
                        item.unit_purchase_cost, ".4f"
                    ),
                    "bid_unit_price": format(item.bid_unit_price, ".4f"),
                    "item_bid_total": format(item.item_bid_total, ".2f"),
                    "currency": item.currency,
                }
                for item in revision.items.all()
            ],
        },
    }
