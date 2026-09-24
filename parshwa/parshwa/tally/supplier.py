import frappe
from xml.sax.saxutils import escape

from parshwa.parshwa.tally_client import get_tally_settings, send_to_tally


def create_tally_supplier_ledger(supplier_name):
    supplier = frappe.get_doc("Supplier", supplier_name)

    ledger_name = supplier.supplier_name or supplier.name

    settings = get_tally_settings()
    tally_company = settings.tally_company

    if not tally_company:
        return {
            "success": False,
            "message": "Tally Company is not configured"
        }

    company = escape(str(tally_company))
    ledger = escape(str(ledger_name))

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
                    <PARENT>Sundry Creditors</PARENT>
                    <ISBILLWISEON>Yes</ISBILLWISEON>
                    <ISCOSTCENTRESON>No</ISCOSTCENTRESON>
                    <OPENINGBALANCE>0</OPENINGBALANCE>
                </LEDGER>
            </TALLYMESSAGE>
        </DATA>
    </BODY>
</ENVELOPE>"""

    frappe.logger("tally").info(
        f"Creating Tally Supplier Ledger: {ledger_name}\n"
        f"XML:\n{xml_data}"
    )

    result = send_to_tally(xml_data)

    return {
        **result,
        "supplier_name": supplier_name,
        "ledger_name": ledger_name,
        "xml": xml_data,
    }


def on_supplier_after_insert(doc, method=None):
    try:
        result = create_tally_supplier_ledger(doc.name)

        if not result.get("success"):
            frappe.log_error(
                title=f"Tally Supplier Ledger Failed - {doc.name}",
                message=str(result)
            )

    except Exception:
        frappe.log_error(
            title=f"Tally Supplier Hook Error - {doc.name}",
            message=frappe.get_traceback()
        )
