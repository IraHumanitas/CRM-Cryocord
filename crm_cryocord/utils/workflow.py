import frappe
from . import constants as c
from frappe.model.workflow import get_workflow_name

ALLOWED_TRANSITIONS = {
    c.STATE_DRAFT: {
        "Submit for Review": c.STATE_SALES_REVIEW,
        "Cancel": c.STATE_CANCELLED,
    },

    c.STATE_SALES_REVIEW: {
        "Submit for Operations Approval": c.STATE_PENDING_OPERATIONS_APPROVAL,
        "Request Revision": c.STATE_DRAFT,
        "Cancel": c.STATE_CANCELLED,
    },

    c.STATE_PENDING_OPERATIONS_APPROVAL: {
        "Approve": c.STATE_OPERATIONS_APPROVED,
        "Reject": c.STATE_REJECTED,
        "Cancel": c.STATE_CANCELLED,
    },

    c.STATE_REJECTED: {
        "Revise": c.STATE_DRAFT
    },

    c.STATE_OPERATIONS_APPROVED: {
        "Mark Ready for Storage Agreement": c.STATE_READY_FOR_STORAGE_AGREEMENT,
        "Return to Sales Review": c.STATE_SALES_REVIEW,
    },

    c.STATE_READY_FOR_STORAGE_AGREEMENT: {
        "Complete": c.STATE_COMPLETED,
    },

    c.STATE_COMPLETED: {},
    c.STATE_CANCELLED: {},
}

def is_valid_transition(from_state, to_state):
    return to_state in ALLOWED_TRANSITIONS.get(from_state, {}).values()


def get_action(from_state, to_state):
    for action, target in ALLOWED_TRANSITIONS.get(from_state, {}).items():
        if target == to_state:
            return action
    return None


def get_workflow_valid_states(doctype: str) -> set[str]:
    """Return the set of valid workflow_state values for the active Workflow of a doctype."""
    workflow_name = get_workflow_name(doctype)
    if not workflow_name:
        return set()

    workflow = frappe.get_cached_doc("Workflow", workflow_name)
    return {row.state for row in workflow.states}