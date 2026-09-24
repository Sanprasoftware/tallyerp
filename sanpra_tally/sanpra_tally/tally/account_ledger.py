import frappe
from xml.sax.saxutils import escape

from sanpra_tally.sanpra_tally.tally_client import get_tally_settings, send_to_tally


def get_tally_parent(account):
    account_type = (account.account_type or "").strip()
    root_type = (account.root_type or "").strip()

    if account_type == "Tax":
        return "Duties & Taxes"

    if account_type == "Bank":
        return "Bank Accounts"

    if account_type == "Cash":
        return "Cash-in-Hand"

    if root_type == "Asset":
        return "Current Assets"

    if root_type == "Liability":
        return "Current Liabilities"

    if root_type == "Equity":
        return "Capital Account"

    if root_type == "Income":
        return "Indirect Incomes"

    if root_type == "Expense":
        return "Indirect Expenses"

    return "Current Assets"


def create_tally_account_ledger(account_name):
    account = frappe.get_doc("Account", account_name)

    if account.is_group:
        return {
            "success": False,
            "message": f"ERPNext Account {account_name} is a group account"
        }

    settings = get_tally_settings()
    tally_company = settings.tally_company

    if not tally_company:
        return {
            "success": False,
            "message": "Tally Company is not configured"
        }

    ledger_name = account.name
    tally_parent = get_tally_parent(account)

    company = escape(str(tally_company))
    ledger = escape(str(ledger_name))
    parent = escape(str(tally_parent))

    xml_data = f"""<?xml version="1.0" encoding="UTF-8"?>
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>All Masters</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVCURRENTCOMPANY>{company}</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
                <LEDGER NAME="{ledger}" ACTION="Create">
                    <NAME.LIST TYPE="String">
                        <NAME>{ledger}</NAME>
                    </NAME.LIST>
                    <PARENT>{parent}</PARENT>
                    <ISBILLWISEON>No</ISBILLWISEON>
                    <ISCOSTCENTRESON>No</ISCOSTCENTRESON>
                    <OPENINGBALANCE>0</OPENINGBALANCE>
                </LEDGER>
            </TALLYMESSAGE>
        </DATA>
    </BODY>
</ENVELOPE>"""

    result = send_to_tally(xml_data)
    response = result.get("response", "")

    if "<ERRORS>0</ERRORS>" not in response or "<EXCEPTIONS>0</EXCEPTIONS>" not in response:
        return {
            **result,
            "success": False,
            "message": response,
            "ledger_name": ledger_name,
            "tally_parent": tally_parent,
            "xml": xml_data,
        }

    return {
        **result,
        "success": True,
        "ledger_name": ledger_name,
        "tally_parent": tally_parent,
        "xml": xml_data,
    }
