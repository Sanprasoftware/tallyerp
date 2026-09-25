"""Create the connector fields required to record Tally results."""
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

def ensure_fields():
    fields = {}
    for doctype in ("Sales Invoice", "Purchase Invoice", "Journal Entry", "Payment Entry"):
        fields[doctype] = [{"fieldname":"custom_tally_voucher_id","label":"Tally Voucher ID",
            "fieldtype":"Data","read_only":1,"no_copy":1,"allow_on_submit":1}]
    for doctype in fields:
        fields[doctype].extend([
            {"fieldname":"custom_tally_voucher_date","label":"Tally Voucher Date",
             "fieldtype":"Date","read_only":1,"no_copy":1,"allow_on_submit":1},
            {"fieldname":"custom_tally_sync_status","label":"Tally Sync Status","fieldtype":"Select",
             "options":"Pending\nQueued\nSyncing\nSynced\nFailed\nNeeds Review\nCancelled",
             "default":"Pending","read_only":1,"no_copy":1,"allow_on_submit":1,"in_list_view":1},
            {"fieldname":"custom_tally_sync_error","label":"Tally Sync Message","fieldtype":"Small Text",
             "read_only":1,"no_copy":1,"allow_on_submit":1},
            {"fieldname":"custom_tally_last_sync_attempt","label":"Last Tally Attempt","fieldtype":"Datetime",
             "read_only":1,"no_copy":1,"allow_on_submit":1},
            {"fieldname":"custom_tally_delivery_uncertain","label":"Tally Delivery Needs Verification",
             "fieldtype":"Check","read_only":1,"hidden":1,"no_copy":1,"allow_on_submit":1},
        ])
    fields["Purchase Invoice"].append({"fieldname":"custom_tally_cancel_voucher_id","label":"Tally Cancel Voucher ID",
        "fieldtype":"Data","read_only":1,"no_copy":1,"allow_on_submit":1})
    create_custom_fields(fields, update=True)
    frappe.db.add_unique("Tally Ledger Mapping", ["company", "reference_type", "reference_name"],
                         constraint_name="unique_tally_ledger_mapping")
