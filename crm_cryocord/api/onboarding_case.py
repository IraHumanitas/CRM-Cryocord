import frappe
from frappe import _
from frappe.utils import get_datetime


@frappe.whitelist()
def get_onboarding_case_status(name: str | None = None):
    """
    Return the current state and audit history of an onboarding case.

    Access is restricted to users with read permission on the case.
    """

    if not name:
        frappe.throw(_("Onboarding Case ID is required."))

    onboarding_case = _get_onboarding_case(name)

    return {
        "onboarding_case": {
            "name": onboarding_case.name,
            "customer": onboarding_case.customer,
            "workflow_state": onboarding_case.workflow_state,
            "docstatus": onboarding_case.docstatus,
            "submitted_on": onboarding_case.submitted_on,
            "decision_by": onboarding_case.decision_by,
            "decision_on": onboarding_case.decision_on,
        },
        "audit_history": _get_audit_history(onboarding_case.name),
    }


def _get_onboarding_case(name: str):
    if not frappe.db.exists("CryoCord Onboarding Case", name):
        frappe.throw(
            _("Onboarding Case {0} does not exist.").format(name),
            frappe.DoesNotExistError,
        )

    doc = frappe.get_doc("CryoCord Onboarding Case", name)

    if not doc.has_permission("read"):
        frappe.throw(
            _("You are not permitted to access this Onboarding Case."),
            frappe.PermissionError,
        )

    return doc


def _get_audit_history(onboarding_case: str):
    rows = frappe.get_all(
        "CryoCord Approval Audit Log",
        filters={"onboarding_case": onboarding_case},
        fields=[
            "timestamp",
            "from_state",
            "to_state",
            "action",
            "actor",
            "reason",
            "is_blocked_attempt",
        ],
        order_by="timestamp asc",
    )

    return [
        {
            "performed_at": get_datetime(row.timestamp).isoformat() if row.timestamp else None,
            "from_state": row.from_state,
            "to_state": row.to_state,
            "action": row.action,
            "performed_by": row.actor,
            "remarks": row.reason,
            "is_blocked_attempt": row.is_blocked_attempt,
        }
        for row in rows
    ]