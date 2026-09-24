import frappe


def execute(filters=None):

    columns = [
        {
            "label": "Purchase Invoice",
            "fieldname": "purchase_invoice",
            "fieldtype": "Link",
            "options": "Purchase Invoices",
            "width": 160
        },
        {
            "label": "Supplier",
            "fieldname": "supplier",
            "fieldtype": "Link",
            "options": "Party",
            "width": 150
        },
        {
            "label": "Posting Date",
            "fieldname": "posting_date",
            "fieldtype": "Date",
            "width": 110
        },
        {
            "label": "Payment Due Date",
            "fieldname": "payment_due_date",
            "fieldtype": "Date",
            "width": 130
        },
        {
            "label": "Item",
            "fieldname": "item",
            "fieldtype": "Link",
            "options": "Item",
            "width": 180
        },
        {
            "label": "Qty",
            "fieldname": "qty",
            "fieldtype": "Float",
            "width": 90
        },
        {
            "label": "Rate",
            "fieldname": "rate",
            "fieldtype": "Currency",
            "width": 110
        },
        {
            "label": "Amount",
            "fieldname": "amount",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": "Total Qty",
            "fieldname": "total_qty",
            "fieldtype": "Float",
            "width": 100
        },
        {
            "label": "Total Amount",
            "fieldname": "total_amount",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": "Credit To",
            "fieldname": "credit_to",
            "fieldtype": "Link",
            "options": "Accounts",
            "width": 180
        },
        {
            "label": "Expense Account",
            "fieldname": "expense_account",
            "fieldtype": "Link",
            "options": "Accounts",
            "width": 180
        }
    ]

    data = frappe.db.sql("""
        SELECT
            pi.name AS purchase_invoice,
            pi.supplier AS supplier,
            pi.posting_date AS posting_date,
            pi.payment_due_date AS payment_due_date,
            pii.item AS item,
            pii.qty AS qty,
            pii.rate AS rate,
            pii.amount AS amount,
            pi.total_qty AS total_qty,
            pi.total_amount AS total_amount,
            pi.credit_to AS credit_to,
            pi.expense_account AS expense_account

        FROM `tabPurchase Invoices` pi

        LEFT JOIN `tabPurchase Invoices Item` pii
            ON pii.parent = pi.name

        WHERE pi.docstatus < 2

        ORDER BY
            pi.posting_date DESC,
            pi.name DESC,
            pii.idx ASC
    """, as_dict=True)

    return columns, data