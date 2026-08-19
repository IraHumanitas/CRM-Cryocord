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