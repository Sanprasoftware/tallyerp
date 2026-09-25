from sanpra_tally.mapping import ledger_name as mapped_ledger_name
import frappe
from xml.sax.saxutils import escape

from sanpra_tally.sanpra_tally.tally_client import get_tally_settings, send_to_tally


def create_tally_tax_ledger(ledger_name):
    settings = get_tally_settings()
    tally_company = settings.tally_company

    if not tally_company:
        return {
            "success": False,
            "message": "Tally Company is not configured"
        }

    ledger_name = mapped_ledger_name('Account', ledger_name, ledger_name)
    company = escape(str(tally_company))
    ledger = escape(str(ledger_name), {'"': '&quot;'})

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
                    <PARENT>Duties &amp; Taxes</PARENT>
                    <ISBILLWISEON>No</ISBILLWISEON>
                    <ISCOSTCENTRESON>No</ISCOSTCENTRESON>
                    <OPENINGBALANCE>0</OPENINGBALANCE>
                </LEDGER>
            </TALLYMESSAGE>
        </DATA>
    </BODY>
</ENVELOPE>"""

    frappe.logger("tally").info(
        f"Creating Tally Tax Ledger: {ledger_name}\n"
        f"XML:\n{xml_data}"
    )

    result = send_to_tally(xml_data)

    return {
        **result,
        "ledger_name": ledger_name,
        "xml": xml_data,
    }
