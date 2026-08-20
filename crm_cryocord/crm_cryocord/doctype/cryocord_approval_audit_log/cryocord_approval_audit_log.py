import frappe
from frappe.model.document import Document


class CryoCordApprovalAuditLog(Document):
    def validate(self):
        # belt-and-braces: even though the field this controller writes to
        # is never touched by client code, refuse a save that somehow lacks
        # an actor/timestamp rather than silently accepting a blank log row.
        if not self.actor:
            frappe.throw("Audit log entry must have an actor.")
        if not self.timestamp:
            self.timestamp = frappe.utils.now_datetime()
        if not self.is_new():
            frappe.throw(_("Audit log cannot be modified."))
    
    def on_update(self):
        # on_update also fires right after insert — only block edits to a
        # row that already existed before this save.
        if not self.flags.in_insert:
            frappe.throw("Audit log entries are append-only and cannot be modified.")

    def on_trash(self):
        frappe.throw(_("Audit log cannot be deleted."))