import frappe
from frappe.model.document import Document


class JournalEntrys(Document):

    def validate(self):
        total_debit = 0
        total_credit = 0

        for row in self.accounting_entries:
            total_debit += row.debit or 0
            total_credit += row.credit or 0

        self.total_debit = total_debit
        self.total_credit = total_credit
        self.difference = total_debit - total_credit

    def on_submit(self):
        self.make_gl_entries()

    def on_cancel(self):
        self.make_reverse_gl_entries()