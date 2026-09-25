import frappe
from frappe.model.document import Document


class TallyLedgerMapping(Document):
    def validate(self):
        self.tally_ledger = (self.tally_ledger or "").strip()
        if not self.tally_ledger:
            frappe.throw("Tally Ledger Name is required.")
        if self.reference_type not in ("Account", "Customer", "Supplier"):
            frappe.throw("Select Account, Customer or Supplier.")
        ref = frappe.get_doc(self.reference_type, self.reference_name)
        if self.reference_type == "Account" and (ref.company != self.company or ref.is_group):
            frappe.throw("Select a ledger account belonging to this company.")
        existing = frappe.db.exists("Tally Ledger Mapping", {
            "company": self.company, "reference_type": self.reference_type,
            "reference_name": self.reference_name, "name": ["!=", self.name or ""]})
        if existing:
            frappe.throw("A mapping already exists for this company and ERP record.")
