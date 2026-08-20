"""Shared constants for CryoCord CRM."""

# CHILD TABLE
CHILD_TABLE_FIELD = "requested_packages"
 
CHILD_ITEM_FIELD = "service_item"
CHILD_QTY_FIELD = "qty"
CHILD_RATE_FIELD = "rate"
CHILD_DISCOUNT_PCT_FIELD = "discount_percentage"   
CHILD_AMOUNT_FIELD = "amount"                    
CHILD_DISCOUNT_AMOUNT_FIELD = "discount_amount"    
CHILD_NET_AMOUNT_FIELD = "net_amount"  


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
    STATE_OPERATIONS_APPROVED,
    STATE_READY_FOR_STORAGE_AGREEMENT,
)

CHILD_DERIVED_FIELDS = {
    CHILD_RATE_FIELD,
    CHILD_AMOUNT_FIELD,
    CHILD_DISCOUNT_AMOUNT_FIELD,
    CHILD_NET_AMOUNT_FIELD,
    "quotation_ref",
    "contract_ref"
}

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


# FIELD PROTECTION
# Frozen once the case leaves EDITABLE_CONTENT_STATES.
PROTECTED_FIELDS_WHEN_LOCKED = (
    "customer",
    "lead",
    "contact_person",
    "primary_address",
    "service_category",
    "sales_officer",
    CHILD_TABLE_FIELD,
    "currency",
    "total_amount",
    "total_discount",
    "grand_total_excl_tax",
    "discount_reason",
    "payment_terms",
)
 
# Managed exclusively by server-side workflow logic.
SERVER_MANAGED_FIELDS = (
    "submitted_by",
    "submitted_on",
    "decision_by",
    "decision_on",
    "onboarded_on",
)


# LEAD INTEGRATION
# Assigned sales owner field on Lead.
LEAD_OWNER_FIELD = "lead_owner"

# Lead status synchronized with onboarding workflow.
LEAD_STATUS_BY_CASE_STATE = {
    STATE_DRAFT: "Open",
    STATE_SALES_REVIEW: "Open",
    STATE_PENDING_OPERATIONS_APPROVAL: "Open",
    STATE_OPERATIONS_APPROVED: "Converted",
    STATE_READY_FOR_STORAGE_AGREEMENT: "Converted",
    STATE_COMPLETED: "Converted",
    STATE_CANCELLED: "Lost Quotation",
    STATE_REJECTED: "Open",
}