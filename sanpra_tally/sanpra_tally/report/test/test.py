import frappe


def execute(filters=None):
    filters = filters or {}

    columns = get_columns()
    data = get_data(filters)

    return columns, data


def get_columns():
    return [
        {
            "label": "Invoice No",
            "fieldname": "invoice_no",
            "fieldtype": "Link",
            "options": "Sales Invoices",
            "width": 150
        },
        {
            "label": "Customer",
            "fieldname": "customer",
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
            "width": 120
        },
        {
            "label": "Item",
            "fieldname": "item",
            "fieldtype": "Data",
            "width": 150
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
            "label": "Debit To",
            "fieldname": "debit_to",
            "fieldtype": "Link",
            "options": "Accounts",
            "width": 150
        },
        {
            "label": "Income Account",
            "fieldname": "income_account",
            "fieldtype": "Link",
            "options": "Accounts",
            "width": 150
        }
    ]


def get_data(filters):
    conditions = []
    values = {}

    if filters.get("customer"):
        conditions.append("si.customer = %(customer)s")
        values["customer"] = filters["customer"]

    if filters.get("from_date"):
        conditions.append("si.posting_date >= %(from_date)s")
        values["from_date"] = filters["from_date"]

    if filters.get("to_date"):
        conditions.append("si.posting_date <= %(to_date)s")
        values["to_date"] = filters["to_date"]

    if filters.get("invoice_no"):
        conditions.append("si.name = %(invoice_no)s")
        values["invoice_no"] = filters["invoice_no"]

    where_clause = ""

    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    data = frappe.db.sql(
        f"""
        SELECT
            si.name AS invoice_no,
            si.customer,
            si.posting_date,
            si.payment_due_date,

            sii.item,
            sii.qty,
            sii.rate,
            sii.amount,

            si.total_qty,
            si.total_amount,

            si.debit_to,
            si.income_account

        FROM `tabSales Invoices` si

        LEFT JOIN `tabSales Invoice Items` sii
            ON sii.parent = si.name

        {where_clause}

        ORDER BY
            si.posting_date DESC,
            si.name DESC,
            sii.idx ASC
        """,
        values,
        as_dict=True
    )

    return data