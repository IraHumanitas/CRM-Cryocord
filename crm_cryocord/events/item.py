import frappe
from frappe import _

CELL_SERVICES = {
    "Stem Cell Banking",
    "Cell Therapy",
}

SOURCE_TISSUE_SERVICES = {
    "Stem Cell Banking",
    "Cell Therapy",
    "Biobanking",
}

LABORATORY_PROCESSING_NOT_APPLICABLE = {
    "Transportation",
    "Storage Extension",
    "Affiliate Product",
}

def validate(doc, method=None):
    """
    Server-side validation for CryoCord Item configuration.

    Service Category is treated as the primary driver for
    service-specific business rules.
    """
    validate_service_category(doc)
    validate_cell_category(doc)
    validate_storage(doc)
    validate_collection(doc)
    validate_laboratory(doc)


def validate_service_category(doc):
    """
    Every CryoCord Item must have a Service Category.

    Service Category determines which additional fields are
    applicable to the item.
    """
    if not doc.cc_service_category:
        frappe.throw(
            _("Service Category is required for CryoCord Items.")
        )

def validate_cell_category(doc):
    """
    Validate fields related to cell-based and biological-sample services.
    """

    service_category = doc.cc_service_category

    # Cell Category is only applicable to cell-based services.
    if service_category in CELL_SERVICES:
        if not doc.cc_cell_category:
            frappe.throw(
                _("Cell Category is required for {0}.").format(
                    service_category
                )
            )
    else:
        # Prevent stale/inapplicable data.
        doc.cc_cell_category = None

    # Source Tissue is required for services involving biological samples.
    if service_category in SOURCE_TISSUE_SERVICES:
        if not doc.cc_source_tissue:
            frappe.throw(
                _("Source Tissue is required for {0}.").format(
                    service_category
                )
            )
    else:
        # Prevent stale/inapplicable data.
        doc.cc_source_tissue = None


def validate_storage(doc):
    """
    Validate storage-related configuration.

    Storage classification is driven by Item Group, since Service
    Category ("Stem Cell Banking") is shared across collection,
    processing, add-on, AND storage items — it cannot be used to
    tell storage items apart from the rest. Storage Extension items
    are always storage services regardless of Item Group.
    """

    # Item Group is the source of truth for storage classification.
    if doc.item_group == "Storage Services" or doc.cc_service_category == "Storage Extension":
        doc.cc_is_storage_service = 1

    # Non-storage services must not carry storage configuration.
    if not doc.cc_is_storage_service:
        doc.cc_storage_segment = None
        doc.cc_default_billing_type = None
        doc.cc_default_storage_years = 0
        return

    # Storage Segment is required for storage services.
    if not doc.cc_storage_segment:
        frappe.throw(
            _("Storage Segment is required for storage services.")
        )

    # Billing model is required for storage services.
    if not doc.cc_default_billing_type:
        frappe.throw(
            _("Default Billing Type is required for storage services.")
        )

    # Recurring storage requires a positive storage duration.
    if doc.cc_default_billing_type == "Annual/Recurring":
        if not doc.cc_default_storage_years:
            frappe.throw(
                _(
                    "Default Storage Years is required for "
                    "Annual/Recurring billing."
                )
            )

        if doc.cc_default_storage_years < 1:
            frappe.throw(
                _(
                    "Default Storage Years must be greater than zero."
                )
            )

    # One-time services do not use a default storage duration.
    else:
        doc.cc_default_storage_years = 0


def validate_collection(doc):
    """
    Validate sample collection configuration.

    Sample collection requires a source tissue because the system
    needs to know what biological material is being collected.
    """

    if doc.cc_require_sample_collection:
        if not doc.cc_source_tissue:
            frappe.throw(
                _(
                    "Source Tissue is required when "
                    "Sample Collection is enabled."
                )
            )
    else:
        # Collection Kit has no meaning when sample collection is disabled.
        doc.cc_collection_kit_required = 0


def validate_laboratory(doc):
    """
    Normalize laboratory processing configuration for services
    where laboratory processing is not applicable.
    """

    service_category = doc.cc_service_category

    if service_category in LABORATORY_PROCESSING_NOT_APPLICABLE:
        doc.cc_require_laboratory_processing = 0