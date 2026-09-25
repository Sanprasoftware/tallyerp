import frappe
from xml.sax.saxutils import escape

from sanpra_tally.sanpra_tally.tally_client import (
    get_tally_settings,
    send_to_tally
)


def create_tally_uom(uom_name):
    """Create/ensure an ERPNext UOM exists as a Tally Unit."""

    if not uom_name:
        return {
            "success": False,
            "message": "UOM name is empty"
        }

    uom = frappe.get_doc("UOM", uom_name)

    if not uom.enabled:
        return {
            "success": False,
            "message": f"UOM '{uom_name}' is disabled in ERPNext"
        }

    settings = get_tally_settings()
    tally_company = settings.tally_company

    if not tally_company:
        return {
            "success": False,
            "message": "Tally Company is not configured"
        }

    company = escape(str(tally_company), {'"': '&quot;'})
    unit = escape(str(uom_name), {'"': '&quot;'})

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
                <UNIT NAME="{unit}" ACTION="Create">
                    <NAME>{unit}</NAME>
                    <ISUPDATINGTARGETID>No</ISUPDATINGTARGETID>
                    <ISSIMPLEUNIT>Yes</ISSIMPLEUNIT>
                    <DECIMALPLACES>3</DECIMALPLACES>
                </UNIT>
            </TALLYMESSAGE>
        </DATA>
    </BODY>
</ENVELOPE>"""

    result = send_to_tally(xml_data)
    response = result.get("response", "")

    if not result.get("success"):
        return {
            "success": False,
            "uom": uom_name,
            "message": "Failed to communicate with Tally",
            "response": response
        }

    if (
        "<EXCEPTIONS>0</EXCEPTIONS>" in response
        and "<ERRORS>0</ERRORS>" in response
    ):
        return {
            "success": True,
            "uom": uom_name,
            "response": response
        }

    return {
        "success": False,
        "uom": uom_name,
        "message": f"Unable to create/ensure Tally Unit '{uom_name}'",
        "response": response
    }


def on_uom_after_insert(doc, method=None):
    """Automatically create new ERPNext UOM in Tally."""

    try:
        result = create_tally_uom(doc.name)

        if not result.get("success"):
            frappe.log_error(
                title=f"Tally UOM Sync Failed: {doc.name}",
                message=result.get(
                    "response",
                    result.get("message", "Unknown error")
                )
            )

    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            f"Tally UOM Sync Error: {doc.name}"
        )
