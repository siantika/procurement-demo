from django.db import migrations


def backfill_bid_waiting_approval(apps, schema_editor):
    AuditEvent = apps.get_model("audit", "AuditEvent")
    BidProposalRevision = apps.get_model("bids", "BidProposalRevision")
    Notification = apps.get_model("notifications", "Notification")
    User = apps.get_model("accounts", "User")

    managers = list(
        User.objects.filter(role="MANAGER", is_active=True).values_list(
            "id", flat=True
        )
    )
    if not managers:
        return

    revisions = BidProposalRevision.objects.filter(
        status="WAITING_APPROVAL"
    ).select_related("bid_proposal")
    for revision in revisions.iterator():
        event = (
            AuditEvent.objects.filter(
                entity_type="BidProposalRevision",
                entity_id=revision.pk,
                action="BID_SUBMITTED",
            )
            .order_by("-occurred_at", "-id")
            .first()
        )
        if event is None:
            continue

        for manager_id in managers:
            Notification.objects.get_or_create(
                recipient_id=manager_id,
                source_event_id=event.pk,
                type="BID_WAITING_APPROVAL",
                defaults={
                    "source_entity_type": "BidProposalRevision",
                    "source_entity_id": revision.pk,
                    "title": "Bid menunggu persetujuan",
                    "message": (
                        f"{revision.bid_proposal.proposal_number} telah "
                        "dikirim dan menunggu keputusan Anda."
                    ),
                },
            )


class Migration(migrations.Migration):
    dependencies = [
        (
            "accounts",
            "0002_alter_user_managers_user_accounts_user_role_valid_and_more",
        ),
        ("audit", "0002_auditevent_audit_entity_timeline_idx_and_more"),
        ("bids", "0001_initial"),
        ("notifications", "0003_alter_notification_type"),
    ]

    operations = [
        migrations.RunPython(
            backfill_bid_waiting_approval,
            migrations.RunPython.noop,
        ),
    ]
