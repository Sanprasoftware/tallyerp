import frappe


@frappe.whitelist()
def get_purchase_item_summary(item_code):
    if not item_code:
        return {
            "item_code": "",
            "purchased_qty": 0,
            "available_qty": 0,
        }

    # Total purchased quantity
    purchased_qty = frappe.db.sql("""
        SELECT COALESCE(SUM(pii.qty), 0)
        FROM `tabPurchase Invoice Item` pii
        INNER JOIN `tabPurchase Invoice` pi
            ON pi.name = pii.parent
        WHERE pii.item_code = %s
          AND pi.docstatus = 1
    """, (item_code,))[0][0]

    # Current available stock
    available_qty = frappe.db.sql("""
        SELECT COALESCE(SUM(actual_qty), 0)
        FROM `tabBin`
        WHERE item_code = %s
    """, (item_code,))[0][0]

    # Item name
    item_name = frappe.db.get_value(
        "Item",
        item_code,
        "item_name"
    )

    return {
        "item_code": item_code,
        "item_name": item_name,
        "purchased_qty": float(purchased_qty or 0),
        "available_qty": float(available_qty or 0),
    }