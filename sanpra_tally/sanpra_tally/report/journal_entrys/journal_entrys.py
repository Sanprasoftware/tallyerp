import frappe


def execute(filters=None):
    filters = filters or {}

    columns = [
        {
            "label": "Journal Entry",
            "fieldname": "journal_entry",
            "fieldtype": "Link",
            "options": "Journal Entrys",
            "width": 150
        },
        {
            "label": "Party",
            "fieldname": "party",
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
            "label": "Account",
            "fieldname": "account",
            "width": 180
        },
        {
            "label": "Debit",
            "fieldname": "debit",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": "Credit",
            "fieldname": "credit",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": "Total Debit",
            "fieldname": "total_debit",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": "Total Credit",
            "fieldname": "total_credit",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": "Difference",
            "fieldname": "difference",
            "fieldtype": "Currency",
            "width": 120
        }
    ]

    conditions = []
    values = {}

    if filters.get("from_date"):
        conditions.append("je.posting_date >= %(from_date)s")
        values["from_date"] = filters.get("from_date")

    if filters.get("to_date"):
        conditions.append("je.posting_date <= %(to_date)s")
        values["to_date"] = filters.get("to_date")

    if filters.get("party"):
        conditions.append("je.party = %(party)s")
        values["party"] = filters.get("party")

    condition_string = ""

    if conditions:
        condition_string = "WHERE " + " AND ".join(conditions)

    data = frappe.db.sql(
        f"""
        SELECT
            je.name AS journal_entry,
            je.party AS party,
            je.posting_date AS posting_date,

            jea.account AS account,
            jea.debit AS debit,
            jea.credit AS credit,

            je.total_debit AS total_debit,
            je.total_credit AS total_credit,
            je.difference AS difference

        FROM `tabJournal Entrys` je

        LEFT JOIN `tabJournal Entry Accounts` jea
            ON jea.parent = je.name

        {condition_string}

        ORDER BY
            je.posting_date DESC,
            je.name DESC,
            jea.idx ASC
        """,
        values,
        as_dict=True
    )

    return columns, data