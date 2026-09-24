import frappe
from frappe.model.document import Document


class PaymentEntrys(Document):

    def validate(self):
        self.calculate_amount()

    def calculate_amount(self):
        # Your calculation code here
        pass