"""Shared constants for CryoCord CRM."""

# CHILD TABLE
CHILD_TABLE_FIELD = "requested_packages"

CHILD_ITEM_FIELD = "service_item"
CHILD_QTY_FIELD = "qty"
CHILD_RATE_FIELD = "rate"
CHILD_DISCOUNT_PCT_FIELD = "discount_percent"
CHILD_AMOUNT_FIELD = "amount"


# ROLES
ROLE_SALES_USER = "Sales User"
ROLE_SALES_MANAGER = "Sales Manager"
ROLE_OPERATIONS_MANAGER = "Operations Manager"
ROLE_SYSTEM_MANAGER = "System Manager"


# WORKFLOW STATES
STATE_DRAFT = "Draft"
STATE_SALES_REVIEW = "Sales Review"
STATE_PENDING_OPERATIONS_APPROVAL = "Pending Operations Approval"
STATE_OPERATIONS_APPROVED = "Operations Approved"
STATE_REJECTED = "Rejected"
STATE_READY_FOR_STORAGE_AGREEMENT = "Ready for Storage Agreement"
STATE_COMPLETED = "Completed"
STATE_CANCELLED = "Cancelled"


# States where business data remains editable.
EDITABLE_CONTENT_STATES = (
    STATE_DRAFT,
    STATE_REJECTED,
)

# Prevent multiple active onboarding cases for one customer.
IN_FLIGHT_STATES = (
    STATE_DRAFT,
    STATE_SALES_REVIEW,
    STATE_PENDING_OPERATIONS_APPROVAL,
)


# LEAD INTEGRATION
# Assigned sales owner field on Lead.
LEAD_OWNER_FIELD = "sales_owner"


# BUSINESS RULES
# Service categories requiring delivery information.
DELIVERY_REQUIRED_CATEGORIES = {
    "Cord Blood Banking",
    "Cord Tissue Banking",
    "Stem Cell Banking",
    "Biobanking",
}

MAX_SINGLE_LINE_DISCOUNT_PERCENT = 50
DISCOUNT_REASON_REQUIRED_ABOVE_RATIO = 0.20
DISCOUNT_REASON_MIN_LENGTH = 20

DEFAULT_STORAGE_TERM_YEARS = 21