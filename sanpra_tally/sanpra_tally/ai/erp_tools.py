import frappe


def get_erp_status():
    return {
        "success": True,
        "message": "ERPNext connection is working",
        "site": frappe.local.site
    }
