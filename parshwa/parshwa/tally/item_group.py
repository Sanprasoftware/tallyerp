import frappe
from xml.sax.saxutils import escape

from parshwa.parshwa.tally_client import (
    get_tally_settings,
    send_to_tally
)


def create_tally_stock_group(item_group_name):

    # Get ERPNext Item Group
    item_group = frappe.get_doc("Item Group", item_group_name)

    if item_group.name == "All Item Groups":
        return {
            "success": True,
            "message": "Root Item Group does not need a Tally Stock Group"
        }

    group_name = item_group.name

    # Get Tally Settings
    settings = get_tally_settings()
    tally_company = settings.tally_company

    if not tally_company:
        return {
            "success": False,
            "message": "Tally Company is not configured"
        }

    company = escape(str(tally_company))
    group = escape(str(group_name))

    # For the current Tally company, Finished Goods is the
    # existing parent Stock Group.
    parent_group = "Finished Goods"

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

                <STOCKGROUP NAME="{group}" ACTION="Create">

                    <NAME.LIST TYPE="String">
                        <NAME>{group}</NAME>
                    </NAME.LIST>

                    <PARENT>{parent_group}</PARENT>

                </STOCKGROUP>

            </TALLYMESSAGE>
        </DATA>
    </BODY>
</ENVELOPE>
"""

    frappe.logger("tally").info(
        f"Creating Tally Stock Group: {group_name}\n"
        f"Parent: {parent_group}\n"
        f"XML:\n{xml_data}"
    )

    result = send_to_tally(xml_data)

    response = result.get("response", "")

    if not result.get("success"):
        frappe.log_error(
            title=f"Tally Stock Group Connection Failed - {item_group_name}",
            message=str(result)
        )

        return {
            "success": False,
            "item_group": item_group_name,
            "response": response
        }

    if (
        "<EXCEPTIONS>0</EXCEPTIONS>" in response
        and "<ERRORS>0</ERRORS>" in response
    ):
        return {
            "success": True,
            "item_group": item_group_name,
            "stock_group_name": group_name,
            "response": response
        }

    frappe.log_error(
        title=f"Tally Stock Group Creation Failed - {item_group_name}",
        message=response
    )

    return {
        "success": False,
        "item_group": item_group_name,
        "stock_group_name": group_name,
        "response": response
    }


def on_item_group_after_insert(doc, method=None):

    try:

        if doc.name == "All Item Groups":
            return

        result = create_tally_stock_group(doc.name)

        if not result.get("success"):
            frappe.log_error(
                title=f"Tally Item Group Creation Failed - {doc.name}",
                message=str(result)
            )

    except Exception:

        frappe.log_error(
            title=f"Tally Item Group Hook Error - {doc.name}",
            message=frappe.get_traceback()
        )
