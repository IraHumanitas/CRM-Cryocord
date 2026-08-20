import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, nowdate, now_datetime, add_years

from crm_cryocord.utils import constants as c
from crm_cryocord.utils.workflow import get_workflow_valid_states, is_valid_transition
from crm_cryocord.utils.pricing import get_item_price


class CryoCordOnboardingCase(Document):
    # ------------------------------------------------------------------
    # LIFECYCLE HOOKS
    # ------------------------------------------------------------------
    def after_insert(self):
        self._log_transition(from_state=None, to_state=self.workflow_state, action="Create")
        self._sync_lead_status(self.workflow_state)

    def on_update(self):
        transition = getattr(self, "_pending_transition", None)
        if not transition:
            return
        self._log_transition(**transition)
        self._sync_lead_status(transition["to_state"])
        del self._pending_transition

    def validate(self):
        self.handle_sales_officer_assignment()

        self.validate_naming_and_amendment()
        self.validate_customer_and_lead()
        self.validate_no_duplicate_active_case()
        self.validate_contact_and_address_belong_to_customer()
        self.validate_service_category_consistency()

        self.validate_delivery_information()

        self.validate_pricing()
        self.validate_requested_packages_and_totals()
        self.validate_discount_reason()
        self.validate_payment_terms()

        self.validate_handover_references()

        self.validate_rejection_reason_editability()
        self.enforce_server_managed_fields()
        self.validate_workflow_transition()
        self.validate_state_requirements()

        # runs after workflow processing so guard-set fields aren't flagged
        self.enforce_field_immutability()

        self.set_next_renewal_date()

    # ------------------------------------------------------------------
    # AUDIT LOG
    # ------------------------------------------------------------------
    def _sync_lead_status(self, state):
        if not self.lead:
            return
        lead_status = c.LEAD_STATUS_BY_CASE_STATE.get(state)
        if lead_status:
            frappe.db.set_value("Lead", self.lead, "status", lead_status, update_modified=False)

    def _log_transition(self, from_state, to_state, action, blocked=False, reason=None):
        frappe.get_doc(
            {
                "doctype": "CryoCord Approval Audit Log",
                "onboarding_case": self.name,
                "from_state": from_state,
                "to_state": to_state,
                "action": action,
                "actor": frappe.session.user,
                "timestamp": now_datetime(),
                "reason": reason,
                "is_blocked_attempt": 1 if blocked else 0,
                "ip_address": getattr(frappe.local, "request_ip", None),
            }
        ).insert(ignore_permissions=True)

    # ------------------------------------------------------------------
    # OWNERSHIP & ASSIGNMENT
    # ------------------------------------------------------------------
    # sales_officer drives row-level permissions below, so it must never
    # be settable by the client — always derived server-side.
    def handle_sales_officer_assignment(self):
        if self.is_new():
            self._auto_assign_sales_officer()
            return

        before = self.get_doc_before_save()
        if before and self.sales_officer != before.sales_officer:
            frappe.throw(_("Sales Officer is assigned automatically and cannot be changed manually."))

    def _auto_assign_sales_officer(self):
        lead_owner = self.lead and frappe.db.get_value("Lead", self.lead, c.LEAD_OWNER_FIELD)
        self.sales_officer = lead_owner or frappe.session.user

    def validate_no_duplicate_active_case(self):
        if not self.customer:
            return

        if self.is_new():
            # serialize concurrent creation for the same customer
            frappe.db.sql("SELECT name FROM `tabCustomer` WHERE name = %s FOR UPDATE", self.customer)

        completed = frappe.db.get_value(
            "CryoCord Onboarding Case",
            {"customer": self.customer, "workflow_state": c.STATE_COMPLETED, "name": ["!=", self.name or ""]},
            "name",
        )
        if completed:
            frappe.throw(
                _("Customer {0} already has a completed Onboarding Case ({1}).").format(self.customer, completed)
            )

        duplicate = frappe.db.get_value(
            "CryoCord Onboarding Case",
            {"customer": self.customer, "workflow_state": ["in", c.IN_FLIGHT_STATES], "name": ["!=", self.name or ""]},
            "name",
        )
        if duplicate:
            frappe.throw(
                _("Customer {0} already has an in-progress Onboarding Case ({1}).").format(self.customer, duplicate)
            )

    # ------------------------------------------------------------------
    # BASIC FIELD VALIDATION
    # ------------------------------------------------------------------
    def validate_naming_and_amendment(self):
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
        # Contact/Address are linked via Dynamic Link — verify ownership
        for doctype, name, label in (
            ("Contact", self.contact_person, "Contact"),
            ("Address", self.primary_address, "Address"),
        ):
            if name and not frappe.db.exists(
                "Dynamic Link",
                {"parenttype": doctype, "parent": name, "link_doctype": "Customer", "link_name": self.customer},
            ):
                frappe.throw(_("{0} {1} is not linked to Customer {2}.").format(label, name, self.customer))


    def validate_service_category_consistency(self):
        if not self.service_category:
            frappe.throw(_("Service Category is mandatory."))

    def validate_delivery_information(self):
        if self.service_category not in c.DELIVERY_REQUIRED_CATEGORIES:
            return

        if not self.expected_delivery_date:
            frappe.throw(_("Expected Delivery Date is mandatory for '{0}'.").format(self.service_category))

        state = self.workflow_state or c.STATE_DRAFT
        if state in c.EDITABLE_CONTENT_STATES and getdate(self.expected_delivery_date) < getdate(nowdate()):
            frappe.throw(_("Expected Delivery Date cannot be in the past."))


    def validate_requested_packages_and_totals(self):
        rows = self.get(c.CHILD_TABLE_FIELD) or []

        if not rows:
            frappe.throw(_("At least one requested package/item is required."))

        state = self.get("workflow_state") or c.STATE_DRAFT
        recalculate = self.is_new() or state in c.EDITABLE_CONTENT_STATES

        gross_total = net_total = 0.0
        seen_items = set()

        for row in rows:
            service_item = row.get(c.CHILD_ITEM_FIELD)
            if not service_item:
                frappe.throw(_("Row {0}: Service Item is required.").format(row.idx))

            item = frappe.db.get_value(
                "Item",
                service_item,
                ["item_name", "cc_is_storage_service", "item_group", "disabled"],
                as_dict=True,
            )

            if not item:
                frappe.throw(_("Row {0}: Item {1} does not exist.").format(row.idx, service_item))

            item_name = item.item_name

            if service_item in seen_items:
                frappe.throw(_("Row {0}: Item {1} is already requested in another row.").format(row.idx, item_name))

            seen_items.add(service_item)

            if not item.cc_is_storage_service:
                frappe.throw(_("Row {0}: Item {1} is not a storage service item.").format(row.idx, item_name))

            if item.disabled:
                frappe.throw(_("Row {0}: Item {1} is disabled.").format(row.idx, item_name))

            if self.service_category != "All Item Groups" and item.item_group != self.service_category:
                frappe.throw(_("Row {0}: Item {1} (Item Group '{2}') does not match Service Category '{3}'.").format(row.idx, item_name, item.item_group, self.service_category))

            qty = flt(row.get(c.CHILD_QTY_FIELD))
            discount_pct = flt(row.get(c.CHILD_DISCOUNT_PCT_FIELD))

            if qty <= 0:
                frappe.throw(_("Row {0}: Quantity must be greater than zero.").format(row.idx))

            if discount_pct < 0 or discount_pct > 100:
                frappe.throw(_("Row {0}: Discount % must be between 0 and 100.").format(row.idx))

            if discount_pct > c.MAX_SINGLE_LINE_DISCOUNT_PERCENT:
                frappe.throw(_("Row {0}: Discount {1}% exceeds the max allowed ({2}%).").format(row.idx, discount_pct, c.MAX_SINGLE_LINE_DISCOUNT_PERCENT))

            if recalculate:
                rate = get_item_price(service_item, self.selling_price_list)
                if rate <= 0:
                    frappe.throw(_("Row {0}: No valid price found for Item {1} in Price List {2}.").format(row.idx, item_name, self.selling_price_list))

                gross = flt(qty * rate, 2)
                discount_amount = flt(gross * discount_pct / 100, 2)
                net = flt(gross - discount_amount, 2)

                row.set(c.CHILD_RATE_FIELD, rate)
                row.set(c.CHILD_AMOUNT_FIELD, gross)
                row.set(c.CHILD_DISCOUNT_AMOUNT_FIELD, discount_amount)
                row.set(c.CHILD_NET_AMOUNT_FIELD, net)
            else:
                # locked state — use stored values, don't let price/rounding drift
                # trip the immutability check downstream
                gross = flt(row.get(c.CHILD_AMOUNT_FIELD))
                net = flt(row.get(c.CHILD_NET_AMOUNT_FIELD))

            gross_total += gross
            net_total += net

        self.total_amount = flt(gross_total, 2)
        self.grand_total_excl_tax = flt(net_total, 2)
        self.total_discount = flt(self.total_amount - self.grand_total_excl_tax, 2)


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

    def validate_pricing(self):
        if not self.selling_price_list:
            frappe.throw(_("Selling Price List is mandatory."))

        price_list = frappe.db.get_value(
            "Price List",
            self.selling_price_list,
            ["enabled", "selling", "currency"],
            as_dict=True,
        )

        if not price_list:
            frappe.throw(
                _("Selling Price List {0} does not exist.").format(
                    self.selling_price_list
                )
            )

        if not price_list.enabled:
            frappe.throw(
                _("Selling Price List {0} is disabled.").format(
                    self.selling_price_list
                )
            )

        if not price_list.selling:
            frappe.throw(
                _("Price List {0} is not configured as a Selling Price List.").format(
                    self.selling_price_list
                )
            )

        self.currency = price_list.currency


    def validate_handover_references(self):
        state = self.get("workflow_state")

        if self.contract_ref and state and state not in (c.STATE_READY_FOR_STORAGE_AGREEMENT, c.STATE_COMPLETED):
            frappe.throw(
                _("Contract Ref can only be set once the case reaches '{0}' or later.").format(
                    c.STATE_READY_FOR_STORAGE_AGREEMENT
                )
            )
        if self.quotation_ref and not frappe.db.exists("Quotation", self.quotation_ref):
            frappe.throw(_("Quotation {0} does not exist.").format(self.quotation_ref))
        if self.contract_ref and not frappe.db.exists("Contract", self.contract_ref):
            frappe.throw(_("Contract {0} does not exist.").format(self.contract_ref))

        self._lock_handover_refs_once_set()

    def _lock_handover_refs_once_set(self):
        # not state-locked (would deadlock, since contract_ref is only settable
        # from Ready for Storage Agreement onward, itself a non-editable state)
        if self.is_new():
            return
        before = self.get_doc_before_save()
        if not before:
            return
        for fieldname in ("quotation_ref", "contract_ref"):
            old_value = before.get(fieldname)
            if old_value and self.get(fieldname) != old_value:
                frappe.throw(_("Field '{0}' cannot be changed once it has been set.").format(fieldname))

    # ------------------------------------------------------------------
    # DERIVED FIELDS
    # ------------------------------------------------------------------
    def set_next_renewal_date(self):
        if self.onboarded_on and self.service_category in c.DELIVERY_REQUIRED_CATEGORIES:
            self.next_renewal_date = add_years(getdate(self.onboarded_on), c.DEFAULT_STORAGE_TERM_YEARS)

    # ------------------------------------------------------------------
    # STATE INVARIANTS — checked every save, not just on transition
    # ------------------------------------------------------------------
    def validate_state_requirements(self):
        state = self.get("workflow_state")
        if not state:
            return

        if state in (
            c.STATE_PENDING_OPERATIONS_APPROVAL,
            c.STATE_OPERATIONS_APPROVED,
            c.STATE_READY_FOR_STORAGE_AGREEMENT,
            c.STATE_COMPLETED,
        ) and flt(self.total_amount) <= 0:
            frappe.throw(_("Total Amount must be greater than zero while the case is in '{0}'.").format(state))

        if state == c.STATE_REJECTED and not (self.rejection_reason or "").strip():
            frappe.throw(_("A Rejected case must have a Rejection Reason."))

        if state == c.STATE_COMPLETED:
            if not self.contract_ref:
                frappe.throw(_("Contract Ref is required once the case is Completed."))
            if not self.onboarded_on:
                frappe.throw(_("Onboarded On must be set once the case is Completed."))


    def validate_rejection_reason_editability(self):
        if self.is_new():
            return

        before = self.get_doc_before_save()
        if not before:
            return

        if before.workflow_state not in (c.STATE_PENDING_OPERATIONS_APPROVAL,) and self.rejection_reason != before.rejection_reason:
            frappe.throw(_("Rejection Reason can only be edited while the case is Pending Operations Approval."))

    # ------------------------------------------------------------------
    # SERVER-MANAGED FIELDS
    # ------------------------------------------------------------------
    def enforce_server_managed_fields(self):
        if self.is_new():
            for fieldname in c.SERVER_MANAGED_FIELDS:
                self.set(fieldname, None)
            return

        before = self.get_doc_before_save()
        if not before:
            return

        # always revert; the guard for the active transition (if any) sets
        # the specific fields it legitimately owns further down in validate()
        for fieldname in c.SERVER_MANAGED_FIELDS:
            self.set(fieldname, before.get(fieldname))

    # ------------------------------------------------------------------
    # WORKFLOW TRANSITIONS
    # ------------------------------------------------------------------
    def validate_workflow_transition(self):
        state = self.get("workflow_state")
        if not state:
            return

        valid_states = get_workflow_valid_states(self.doctype)
        if valid_states and state not in valid_states:
            frappe.throw(_("Invalid workflow state: {0}").format(state))

        before = self.get_doc_before_save()
        previous_state = (before.get("workflow_state") if before else c.STATE_DRAFT) or c.STATE_DRAFT
        if state == previous_state:
            return

        if not is_valid_transition(previous_state, state):
            frappe.throw(_("Transition from '{0}' to '{1}' is not defined in the workflow.").format(previous_state, state))

        self._dispatch_transition_guard(previous_state, state)

        self._pending_transition = {
            "from_state": previous_state,
            "to_state": state,
            "action": c.TRANSITION_ACTIONS.get((previous_state, state), "Unknown Transition"),
            "reason": self.rejection_reason if state == c.STATE_REJECTED else None,
        }

    def _dispatch_transition_guard(self, previous_state, state):
        roles = set(frappe.get_roles())
        user = frappe.session.user
        transition = (previous_state, state)

        guards = {
            (c.STATE_DRAFT, c.STATE_SALES_REVIEW): lambda: self._guard_submit_for_review(roles),
            (c.STATE_SALES_REVIEW, c.STATE_PENDING_OPERATIONS_APPROVAL): lambda: self._guard_submit_for_operations_approval(roles),
            (c.STATE_SALES_REVIEW, c.STATE_DRAFT): lambda: self._require_role(roles, c.ROLE_SALES_MANAGER, target_state=c.STATE_DRAFT),
            (c.STATE_PENDING_OPERATIONS_APPROVAL, c.STATE_OPERATIONS_APPROVED): lambda: self._guard_operations_decision(state, user, roles),
            (c.STATE_PENDING_OPERATIONS_APPROVAL, c.STATE_REJECTED): lambda: self._guard_operations_decision(state, user, roles),
            (c.STATE_OPERATIONS_APPROVED, c.STATE_READY_FOR_STORAGE_AGREEMENT): lambda: self._require_role(
                roles, c.ROLE_OPERATIONS_MANAGER, target_state=c.STATE_READY_FOR_STORAGE_AGREEMENT
            ),
            (c.STATE_READY_FOR_STORAGE_AGREEMENT, c.STATE_COMPLETED): lambda: self._guard_complete(roles),
            (c.STATE_REJECTED, c.STATE_DRAFT): lambda: self._guard_revise(roles),
            (c.STATE_DRAFT, c.STATE_CANCELLED): lambda: self._guard_cancel(previous_state, roles),
            (c.STATE_SALES_REVIEW, c.STATE_CANCELLED): lambda: self._guard_cancel(previous_state, roles),
            (c.STATE_PENDING_OPERATIONS_APPROVAL, c.STATE_CANCELLED): lambda: self._guard_cancel(previous_state, roles),
        }

        guard = guards.get(transition)
        if not guard:
            frappe.throw(_("Transition from '{0}' to '{1}' is not allowed.").format(previous_state, state))
        guard()

    # -- individual guards ------------------------------------------------
    def _guard_submit_for_review(self, roles):
        self._require_role(roles, c.ROLE_SALES_USER, target_state=c.STATE_SALES_REVIEW)
        self._require_fields("customer", "sales_officer", "service_category", "contact_person", "primary_address", "payment_terms")
        if not self.get(c.CHILD_TABLE_FIELD):
            frappe.throw(_("At least one requested package is required."))
        if self.service_category in c.DELIVERY_REQUIRED_CATEGORIES and not self.expected_delivery_date:
            frappe.throw(_("Expected Delivery Date is required."))

    def _guard_submit_for_operations_approval(self, roles):
        self._require_role(roles, c.ROLE_SALES_MANAGER, target_state=c.STATE_PENDING_OPERATIONS_APPROVAL)
        if not self.get(c.CHILD_TABLE_FIELD):
            frappe.throw(_("At least one requested package is required."))
        self.submitted_by = frappe.session.user
        self.submitted_on = now_datetime()

    def _guard_operations_decision(self, state, user, roles):
        self._require_role(roles, c.ROLE_OPERATIONS_MANAGER, target_state=state)

        if user in (self.owner, self.sales_officer, self.submitted_by):
            frappe.throw(_("You cannot approve or reject a case you submitted yourself."))

        if state == c.STATE_REJECTED:
            # self.rejection_reason was already reverted by enforce_server_managed_fields();
            # use the snapshot taken at the top of validate() instead
            reason = (self.rejection_reason or "").strip()
            if not reason:
                frappe.throw(_("A Rejection Reason is required when rejecting a case."))
            self.rejection_reason = reason
        else:
            self.rejection_reason = None  # clear stale text from a prior cycle

        self.decision_by = user
        self.decision_on = now_datetime()

    def _guard_complete(self, roles):
        self._require_role(roles, c.ROLE_OPERATIONS_MANAGER, target_state=c.STATE_COMPLETED)
        if not self.contract_ref:
            frappe.throw(_("Contract Ref must be set before completing the case."))
        self.onboarded_on = now_datetime()

    def _guard_revise(self, roles):
        self._require_role(roles, c.ROLE_SALES_USER, target_state=c.STATE_DRAFT)
        self.rejection_reason = None

    def _guard_cancel(self, previous_state, roles):
        if previous_state in (c.STATE_DRAFT, c.STATE_SALES_REVIEW):
            self._require_role(roles, c.ROLE_SALES_MANAGER, target_state=c.STATE_CANCELLED)
        elif previous_state == c.STATE_PENDING_OPERATIONS_APPROVAL:
            self._require_role(roles, c.ROLE_OPERATIONS_MANAGER, target_state=c.STATE_CANCELLED)

    def _require_role(self, roles, *allowed_roles, target_state):
        if roles.isdisjoint({*allowed_roles, c.ROLE_SYSTEM_MANAGER}):
            frappe.throw(_("You do not have permission to move this case to '{0}'.").format(target_state))

    def _require_fields(self, *fieldnames):
        missing = [self.meta.get_label(f) or f for f in fieldnames if not self.get(f)]
        if missing:
            frappe.throw(_("The following fields are required: {0}").format(", ".join(missing)))

    # ------------------------------------------------------------------
    # IMMUTABILITY — content locked once workflow_state leaves Draft/Rejected
    # ------------------------------------------------------------------
    def enforce_field_immutability(self):
        if self.is_new():
            return

        before = self.get_doc_before_save()

        if not before:
            return

        prev_state = before.get("workflow_state")

        if prev_state in c.EDITABLE_CONTENT_STATES:
            return

        for fieldname in c.PROTECTED_FIELDS_WHEN_LOCKED:
            old_value = before.get(fieldname)
            new_value = self.get(fieldname)

            if fieldname == c.CHILD_TABLE_FIELD:
                if self._serialize_rows(old_value) != self._serialize_rows(new_value):
                    frappe.throw(
                        _(
                            "Requested Packages cannot be modified while the case is in '{0}'."
                        ).format(prev_state)
                    )

                continue

            if old_value != new_value:
                frappe.throw(
                    _("Field '{0}' cannot be changed while the case is in '{1}'.").format(
                        fieldname,
                        prev_state,
                    )
                )


    @staticmethod
    def _serialize_rows(rows):
        return frappe.as_json([
            {
                fieldname: row.get(fieldname)
                for fieldname in c.PROTECTED_CHILD_FIELDS
            }
            for row in (rows or [])
        ])


# ============================================================================
# ROW-LEVEL PERMISSIONS
# Sales User -> own cases only | Sales/System Manager -> all
# Operations Manager -> all except Draft/Sales Review
# (narrows Role Permission access, doesn't grant it)
# ============================================================================
def get_permission_query_conditions(user=None):
    user = user or frappe.session.user
    roles = set(frappe.get_roles(user))

    if roles & {c.ROLE_SYSTEM_MANAGER, c.ROLE_SALES_MANAGER}:
        return ""
    if c.ROLE_OPERATIONS_MANAGER in roles:
        excluded = ", ".join(frappe.db.escape(s) for s in (c.STATE_DRAFT, c.STATE_SALES_REVIEW))
        return f"(`tabCryoCord Onboarding Case`.workflow_state not in ({excluded}))"
    if c.ROLE_SALES_USER in roles:
        return f"(`tabCryoCord Onboarding Case`.sales_officer = {frappe.db.escape(user)})"
    return "1=0"


def has_permission(doc, ptype="read", user=None):
    user = user or frappe.session.user
    roles = set(frappe.get_roles(user))

    if ptype == "create":
        return None
    if roles & {c.ROLE_SYSTEM_MANAGER, c.ROLE_SALES_MANAGER}:
        return True
    if c.ROLE_OPERATIONS_MANAGER in roles:
        return doc.workflow_state not in (c.STATE_DRAFT, c.STATE_SALES_REVIEW)
    if c.ROLE_SALES_USER in roles:
        return doc.sales_officer == user
    return False
