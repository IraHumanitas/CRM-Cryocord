import frappe
from frappe.utils import getdate, today


def validate(doc, method=None):
    # Automatically update lead status based on Expected Delivery Date (EDD).
    validate_expected_delivery_date(doc)


def validate_expected_delivery_date(doc):
    """
    Automatically close inactive Leads after the Expected Delivery Date (EDD).

    Rules:
    - EDD must exist.
    - Today's date must be later than EDD.
    - Skip if already Converted, Do Not Contact, or Lost Quotation.
    - Skip if a CryoCord Service Request already exists.
    - Otherwise set Status = Lost Quotation.
    - Set Lost Reason to "Delivery Completed" only if it is still empty.
    """

    if not doc.cc_expected_delivery_date:
        return

    if getdate(today()) <= getdate(doc.cc_expected_delivery_date):
        return

    if doc.status in (
        "Converted",
        "Do Not Contact",
        "Lost Quotation",
    ):
        return

    # Skip if a service request has already been created.
    if frappe.db.exists(
        "CryoCord Service Request",
        {
            "lead": doc.name,
            "docstatus": ["!=", 2],
        },
    ):
        return

    doc.status = "Lost Quotation"

    if not doc.cc_lost_reason:
        doc.cc_lost_reason = "Delivery Completed"