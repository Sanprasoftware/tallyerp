import frappe


def execute(filters=None):
    filters = filters or {}

    columns = get_columns()
    data = get_data(filters)

    return columns, data


def get_columns():
    return [
        {
            "label": "Payment Entry",
            "fieldname": "name",
            "fieldtype": "Link",
            "options": "Payment Entrys",
            "width": 180
        },
        {
            "label": "Posting Date",
            "fieldname": "posting_date",
            "fieldtype": "Date",
            "width": 120
        },
        {
            "label": "Payment Type",
            "fieldname": "payment_type",
            "fieldtype": "Data",
            "width": 120
        },
        {
            "label": "Party Type",
            "fieldname": "party_type",
            "fieldtype": "Data",
            "width": 120
        },
        {
            "label": "Party",
            "fieldname": "party",
            "fieldtype": "Link",
            "options": "Party",
            "width": 180
        },
        {
            "label": "Account Paid From",
            "fieldname": "account_paid_from",
            "fieldtype": "Link",
            "options": "Accounts",
            "width": 180
        },
        {
            "label": "Account Paid To",
            "fieldname": "account_paid_to",
            "fieldtype": "Link",
            "options": "Accounts",
            "width": 180
        },
        {
            "label": "Amount",
            "fieldname": "amount",
            "fieldtype": "Currency",
            "width": 120
        }
    ]


def get_data(filters):
    conditions = []
    values = {}

    if filters.get("posting_date"):
        conditions.append("pe.posting_date = %(posting_date)s")
        values["posting_date"] = filters["posting_date"]

    if filters.get("payment_type"):
        conditions.append("pe.payment_type = %(payment_type)s")
        values["payment_type"] = filters["payment_type"]

    if filters.get("party_type"):
        conditions.append("pe.party_type = %(party_type)s")
        values["party_type"] = filters["party_type"]

    if filters.get("party"):
        conditions.append("pe.party = %(party)s")
        values["party"] = filters["party"]

    if filters.get("name"):
        conditions.append("pe.name = %(name)s")
        values["name"] = filters["name"]

    where_clause = ""

    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    data = frappe.db.sql(
        f"""
        SELECT
            pe.name,
            pe.posting_date,
            pe.payment_type,
            pe.party_type,
            pe.party,
            pe.account_paid_from,
            pe.account_paid_to,
            pe.amount
        FROM `tabPayment Entrys` pe
        {where_clause}
        ORDER BY pe.posting_date DESC, pe.creation DESC
        """,
        values,
        as_dict=True
    )

    return data