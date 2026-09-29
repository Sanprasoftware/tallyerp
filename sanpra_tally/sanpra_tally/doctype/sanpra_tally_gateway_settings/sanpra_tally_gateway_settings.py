import frappe
from frappe.model.document import Document


class SanpraTallyGatewaySettings(Document):
    def validate(self):
        for fieldname in ("gateway_url", "erp_site_url"):
            value = (self.get(fieldname) or "").strip().rstrip("/")
            if value:
                self.set(fieldname, value)
