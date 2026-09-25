import frappe
from xml.sax.saxutils import escape

from sanpra_tally.sanpra_tally.tally_client import (
    get_tally_settings,
    send_to_tally
)

from sanpra_tally.sanpra_tally.tally.item_group import create_tally_stock_group
from sanpra_tally.sanpra_tally.tally.uom import create_tally_uom


def create_tally_stock_item(item_name):

    # ---------------------------------------------------------
    # Get ERPNext Item
    # ---------------------------------------------------------

    item = frappe.get_doc("Item", item_name)

    if not item.item_name:
        return {
            "success": False,
            "message": "Item Name is empty"
        }

    stock_item_name = item.item_name

    # ---------------------------------------------------------
    # Get Item Group and UOM
    # ---------------------------------------------------------

    item_group = item.item_group or "Primary"
    uom = item.stock_uom or "Nos"

    # ---------------------------------------------------------
    # Ensure Tally Stock Group Exists
    # ---------------------------------------------------------

    if item_group != "All Item Groups":
        group_result = create_tally_stock_group(item_group)

        if not group_result.get("success"):
            return {
                "success": False,
                "item_name": item_name,
                "message": (
                    f"Unable to create/ensure Tally Stock Group "
                    f"'{item_group}'."
                ),
                "response": group_result.get(
                    "response",
                    group_result.get("message", "Unknown error")
                )
            }

    # ---------------------------------------------------------
    # Ensure Tally UOM Exists
    # ---------------------------------------------------------

    uom_result = create_tally_uom(uom)

    if not uom_result.get("success"):
        return {
            "success": False,
            "item_name": item_name,
            "message": (
                f"Unable to create/ensure Tally Unit "
                f"'{uom}'."
            ),
            "response": uom_result.get(
                "response",
                uom_result.get("message", "Unknown error")
            )
        }

    # ---------------------------------------------------------
    # Get Existing Tally Settings
    # ---------------------------------------------------------

    settings = get_tally_settings()

    tally_company = settings.tally_company

    if not tally_company:
        return {
            "success": False,
            "message": "Tally Company is not configured"
        }

    # ---------------------------------------------------------
    # Escape XML values
    # ---------------------------------------------------------

    company = escape(str(tally_company), {'"': '&quot;'})
    stock_item = escape(str(stock_item_name), {'"': '&quot;'})
    stock_group = escape(str(item_group), {'"': '&quot;'})
    base_uom = escape(str(uom), {'"': '&quot;'})

    # ---------------------------------------------------------
    # Tally Stock Item XML
    # ---------------------------------------------------------

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

                <STOCKITEM NAME="{stock_item}" ACTION="Create">

                    <NAME.LIST TYPE="String">
                        <NAME>{stock_item}</NAME>
                    </NAME.LIST>

                    <PARENT>{stock_group}</PARENT>

                    <BASEUNITS>{base_uom}</BASEUNITS>

                    <GSTAPPLICABLE>No</GSTAPPLICABLE>

                    <ISBATCHWISEON>No</ISBATCHWISEON>

                    <ISPERISHABLE>No</ISPERISHABLE>

                    <OPENINGBALANCE>0</OPENINGBALANCE>

                    <OPENINGVALUE>0</OPENINGVALUE>

                </STOCKITEM>

            </TALLYMESSAGE>

        </DATA>

    </BODY>

</ENVELOPE>
"""

    # ---------------------------------------------------------
    # Print XML in Error Log / Console Logger
    # ---------------------------------------------------------

    frappe.logger("tally").info(
        f"Creating Tally Stock Item: {stock_item_name}\n"
        f"Item Group: {item_group}\n"
        f"UOM: {uom}\n"
        f"XML:\n{xml_data}"
    )

    # ---------------------------------------------------------
    # Send to Tally
    # ---------------------------------------------------------

    result = send_to_tally(xml_data)

    response = result.get("response", "")

    # ---------------------------------------------------------
    # Check Connection
    # ---------------------------------------------------------

    if not result.get("success"):

        frappe.log_error(
            title=f"Tally Stock Item Connection Failed - {item_name}",
            message=str(result)
        )

        return {
            "success": False,
            "item_name": item_name,
            "response": response
        }

    # ---------------------------------------------------------
    # Tally Success
    # ---------------------------------------------------------

    if any(tag in response for tag in ("<STATUS>1</STATUS>", "<CREATED>1</CREATED>",
                                          "<ALTERED>1</ALTERED>", "<IGNORED>1</IGNORED>")):

        frappe.logger("tally").info(
            f"Tally Stock Item Created Successfully: "
            f"{stock_item_name}"
        )

        return {
            "success": True,
            "item_name": item_name,
            "stock_item_name": stock_item_name,
            "response": response
        }

    # ---------------------------------------------------------
    # Tally Error
    # ---------------------------------------------------------

    frappe.log_error(
        title=f"Tally Stock Item Creation Failed - {item_name}",
        message=response
    )

    return {
        "success": False,
        "item_name": item_name,
        "stock_item_name": stock_item_name,
        "response": response
    }


def on_item_after_insert(doc, method=None):

    try:

        if doc.disabled:
            return

        result = create_tally_stock_item(doc.name)

        if not result.get("success"):

            frappe.log_error(
                title=f"Tally Item Creation Failed - {doc.name}",
                message=str(result)
            )

    except Exception:

        frappe.log_error(
            title=f"Tally Item Hook Error - {doc.name}",
            message=frappe.get_traceback()
        )