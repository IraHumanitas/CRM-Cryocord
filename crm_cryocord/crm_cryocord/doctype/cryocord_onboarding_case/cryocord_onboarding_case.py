import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, nowdate, now_datetime, add_years

from crm_cryocord.utils import constants as c


class CryoCordOnboardingCase(Document):
    def validate(self):
        # --- ownership & assignment ---------------------------------------
        self.handle_sales_officer_assignment()

        # --- basic field validation (always runs, any state) ------------
        self.validate_naming_and_amendment()
        self.validate_customer_and_lead()
        self.validate_no_duplicate_active_case()
        self.validate_contact_and_address_belong_to_customer()
        self.validate_service_category_consistency()
        self.validate_delivery_information()
        self.validate_requested_packages()
        self.calculate_totals()
        self.validate_discount_reason()
        self.validate_payment_terms()

        # --- derived fields ------------------------------------------------
        self.set_next_renewal_date()

    # ------------------------------------------------------------------
    # OWNERSHIP & ASSIGNMENT
    # ------------------------------------------------------------------
    # sales_officer is never chosen by the user — it is derived from the
    # linked Lead's owner at creation, and frozen after that. This is what
    # makes row-level permission (get_permission_query_conditions /
    # has_permission, near the bottom of this file) trustworthy: a Sales
    # User can't grant themselves access by editing the field.

    def handle_sales_officer_assignment(self):
        if self.is_new():
            self._auto_assign_sales_officer()
            return

        before = self.get_doc_before_save()
        if before and self.sales_officer != before.sales_officer:
            frappe.throw(_("Sales Officer is assigned automatically and cannot be changed manually."))

    def _auto_assign_sales_officer(self):
        if self.lead:
            lead_owner = frappe.db.get_value("Lead", self.lead, c.LEAD_OWNER_FIELD)
            if lead_owner:
                self.sales_officer = lead_owner
                return

        # no Lead linked, or the Lead has no owner set — default to whoever
        # is creating the case rather than leave it blank
        if not self.sales_officer:
            self.sales_officer = frappe.session.user

    def validate_no_duplicate_active_case(self):
        if not self.customer:
            return

        # Rule A: a customer that already completed onboarding shouldn't
        # get a second case unless that first one is explicitly reopened.
        completed = frappe.db.get_value(
            "CryoCord Onboarding Case",
            {
                "customer": self.customer,
                "workflow_state": c.STATE_COMPLETED,
                "name": ["!=", self.name or ""],
            },
            "name",
        )
        if completed:
            frappe.throw(
                _("Customer {0} already has a completed Onboarding Case ({1}). A new case is not allowed.").format(
                    self.customer, completed
                )
            )

        # Rule B: at most one undecided ("in flight") case per customer at a time
        duplicate = frappe.db.get_value(
            "CryoCord Onboarding Case",
            {
                "customer": self.customer,
                "workflow_state": ["in", c.IN_FLIGHT_STATES],
                "name": ["!=", self.name or ""],
            },
            "name",
        )
        if duplicate:
            frappe.throw(
                _("Customer {0} already has an in-progress Onboarding Case ({1}). Continue that case instead of creating a new one.").format(
                    self.customer, duplicate
                )
            )

    # ------------------------------------------------------------------
    # BASIC FIELD VALIDATION
    # ------------------------------------------------------------------

    def validate_naming_and_amendment(self):
        # amended doc must restart at Draft, not inherit prior decision state
        if self.amended_from and self.workflow_state and self.workflow_state != c.STATE_DRAFT:
            frappe.throw(_("An amended Onboarding Case must start in '{0}' state.").format(c.STATE_DRAFT))

    def validate_customer_and_lead(self):
        if not self.customer:
            frappe.throw(_("Customer is mandatory."))
        if not frappe.db.exists("Customer", self.customer):
            frappe.throw(_("Customer {0} does not exist.").format(self.customer))

        if self.lead:
            lead_customer = frappe.db.get_value("Lead", self.lead, "customer")
            if lead_customer and lead_customer != self.customer:
                frappe.throw(
                    _("Lead {0} was converted to a different Customer ({1}), not {2}.").format(
                        self.lead, lead_customer, self.customer
                    )
                )

    def validate_contact_and_address_belong_to_customer(self):
        # Contact/Address are linked via Dynamic Link, not a direct field — verify ownership
        if self.contact_person and not frappe.db.exists(
            "Dynamic Link",
            {
                "parenttype": "Contact",
                "parent": self.contact_person,
                "link_doctype": "Customer",
                "link_name": self.customer,
            },
        ):
            frappe.throw(_("Contact {0} is not linked to Customer {1}.").format(self.contact_person, self.customer))

        if self.primary_address and not frappe.db.exists(
            "Dynamic Link",
            {
                "parenttype": "Address",
                "parent": self.primary_address,
                "link_doctype": "Customer",
                "link_name": self.customer,
            },
        ):
            frappe.throw(_("Address {0} is not linked to Customer {1}.").format(self.primary_address, self.customer))

    def validate_service_category_consistency(self):
        if not self.service_category:
            frappe.throw(_("Service Category is mandatory."))
        # Item Group vs Service Category match is now hard-enforced per
        # row in validate_requested_packages() — see cc_is_storage_service check.

    def validate_delivery_information(self):
        if self.service_category not in c.DELIVERY_REQUIRED_CATEGORIES:
            return

        if not self.expected_delivery_date:
            frappe.throw(_("Expected Delivery Date is mandatory for '{0}'.").format(self.service_category))

        # past dates only blocked while still editable
        state = self.workflow_state or c.STATE_DRAFT
        if state in c.EDITABLE_CONTENT_STATES and getdate(self.expected_delivery_date) < getdate(nowdate()):
            frappe.throw(_("Expected Delivery Date cannot be in the past."))

    def validate_requested_packages(self):
        rows = self.get(c.CHILD_TABLE_FIELD) or []
        if not rows:
            frappe.throw(_("At least one requested package/item is required."))

        for row in rows:
            service_item = row.get(c.CHILD_ITEM_FIELD)
            if not service_item:
                frappe.throw(_("Row {0}: Service Item is required.").format(row.idx))

            item = frappe.db.get_value(
                "Item",
                service_item,
                ["cc_is_storage_service", "item_group", "disabled"],
                as_dict=True,
            )
            if not item:
                frappe.throw(_("Row {0}: Item {1} does not exist.").format(row.idx, service_item))
            if not item.cc_is_storage_service:
                frappe.throw(
                    _("Row {0}: Item {1} is not a storage service item and cannot be requested here.").format(
                        row.idx, service_item
                    )
                )
            if item.disabled:
                frappe.throw(_("Row {0}: Item {1} is disabled.").format(row.idx, service_item))
            if item.item_group != self.service_category:
                frappe.throw(
                    _(
                        "Row {0}: Item {1} belongs to Item Group '{2}', which does not match "
                        "the case's Service Category '{3}'."
                    ).format(row.idx, service_item, item.item_group, self.service_category)
                )

            qty = flt(row.get(c.CHILD_QTY_FIELD))
            rate = flt(row.get(c.CHILD_RATE_FIELD))
            discount_pct = flt(row.get(c.CHILD_DISCOUNT_PCT_FIELD))

            if qty <= 0:
                frappe.throw(_("Row {0}: Quantity must be greater than zero.").format(row.idx))
            if rate < 0:
                frappe.throw(_("Row {0}: Rate cannot be negative.").format(row.idx))
            if discount_pct < 0 or discount_pct > 100:
                frappe.throw(_("Row {0}: Discount % must be between 0 and 100.").format(row.idx))
            if discount_pct > c.MAX_SINGLE_LINE_DISCOUNT_PERCENT:
                frappe.throw(
                    _("Row {0}: Discount {1}% exceeds the max allowed ({2}%).").format(
                        row.idx, discount_pct, c.MAX_SINGLE_LINE_DISCOUNT_PERCENT
                    )
                )

            # recompute server-side — field may be read-only in UI but that's not enforced at API level
            row.set(c.CHILD_AMOUNT_FIELD, flt(qty * rate * (1 - discount_pct / 100), 2))

    def calculate_totals(self):
        rows = self.get(c.CHILD_TABLE_FIELD) or []
        gross_total = discount_total = 0.0

        for row in rows:
            qty = flt(row.get(c.CHILD_QTY_FIELD))
            rate = flt(row.get(c.CHILD_RATE_FIELD))
            discount_pct = flt(row.get(c.CHILD_DISCOUNT_PCT_FIELD))
            row_gross = qty * rate
            gross_total += row_gross
            discount_total += row_gross * (discount_pct / 100)

        self.total_amount = flt(gross_total, 2)
        self.total_discount = flt(discount_total, 2)
        self.grand_total_excl_tax = flt(gross_total - discount_total, 2)

    def validate_discount_reason(self):
        if not (self.total_discount and self.total_amount):
            return

        ratio = self.total_discount / self.total_amount
        if ratio > c.DISCOUNT_REASON_REQUIRED_ABOVE_RATIO and (
            not self.discount_reason or len(self.discount_reason.strip()) < c.DISCOUNT_REASON_MIN_LENGTH
        ):
            frappe.throw(
                _("Discount exceeds {0:.0f}% of order value — provide a Discount Reason of at least {1} characters.").format(
                    c.DISCOUNT_REASON_REQUIRED_ABOVE_RATIO * 100, c.DISCOUNT_REASON_MIN_LENGTH
                )
            )

    def validate_payment_terms(self):
        if self.payment_terms == "Installment" and not (self.remarks or "").strip():
            frappe.msgprint(
                _("Installment plan selected — consider documenting the schedule in Remarks."),
                indicator="orange",
                alert=True,
            )


    # ------------------------------------------------------------------
    # DERIVED FIELDS
    # ------------------------------------------------------------------
    def set_next_renewal_date(self):
        if self.onboarded_on and self.service_category in c.DELIVERY_REQUIRED_CATEGORIES:
            # default storage term — ideally sourced from the Item/package master instead
            self.next_renewal_date = add_years(getdate(self.onboarded_on), c.DEFAULT_STORAGE_TERM_YEARS)