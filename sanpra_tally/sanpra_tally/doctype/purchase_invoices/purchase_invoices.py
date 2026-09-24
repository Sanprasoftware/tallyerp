import frappe
from frappe.model.document import Document
from frappe.utils import flt


class PurchaseInvoices(Document):

    def validate(self):
        total_qty = 0
        total_amount = 0

        for row in self.items:
            qty = flt(row.qty)
            rate = flt(row.rate)

            row.amount = qty * rate

            total_qty += qty
            total_amount += row.amount

        self.total_qty = total_qty
        self.total_amount = total_amount