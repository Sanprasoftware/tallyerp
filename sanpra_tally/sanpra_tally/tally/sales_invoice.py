from sanpra_tally.sanpra_tally.tally.account_ledger import create_tally_account_ledger
from xml.sax.saxutils import escape
from sanpra_tally.subscription_client import get_settings

def xml_escape(value):
    return escape(str(value or ""), {'"': "&quot;", "'": "&apos;"})

import frappe

from sanpra_tally.sanpra_tally.tally_client import get_tally_settings, send_to_tally
from sanpra_tally.sanpra_tally.tally.customer import create_tally_customer_ledger

from sanpra_tally.sanpra_tally.tally.item import create_tally_stock_item


def get_tally_company():
    return get_tally_settings().tally_company


def send_sales_invoice_to_tally(invoice_name):
    invoice = frappe.get_doc("Sales Invoice", invoice_name)
    get_settings(invoice)
    
        # Ensure the customer's Tally ledger exists before creating the voucher.
    customer_result = create_tally_customer_ledger(invoice.customer)

    if not customer_result.get("success"):
        return {
            "success": False,
            "response": (
                f"Unable to create/ensure Tally customer ledger "
                f"for {invoice.customer}.\n\n"
                f"{customer_result.get('response', customer_result.get('message', 'Unknown error'))}"
            ),
        }

    # --------------------------------------------------------
    # Ensure all invoice Items exist in Tally
    # --------------------------------------------------------

    for invoice_item in invoice.items:
        if not invoice_item.item_code:
            continue

        item_result = create_tally_stock_item(invoice_item.item_code)

        if not item_result.get("success"):
            return {
                "success": False,
                "response": (
                    f"Unable to create/ensure Tally Item "
                    f"for {invoice_item.item_code}.\n\n"
                    f"{item_result.get('response', item_result.get('message', 'Unknown error'))}"
                ),
            }

    # --------------------------------------------------------
    # Prevent duplicate Tally voucher
    # --------------------------------------------------------

    tally_voucher_id = invoice.get("custom_tally_voucher_id")

    if tally_voucher_id and str(tally_voucher_id) != "0":
        return {
            "success": False,
            "response": (
                f"Sales Invoice {xml_escape(invoice_name)} "
                f"is already synced to Tally. "
                f"Tally Voucher ID: {tally_voucher_id}"
            ),
            "tally_voucher_id": tally_voucher_id,
        }

    posting_date = invoice.posting_date.strftime("%Y%m%d")

    customer = str(customer_result.get("ledger_name") or "")
    total_amount = float(invoice.grand_total or 0)
    tally_company = get_tally_company()

    # --------------------------------------------------------
    # Calculate Sales / CGST / SGST amounts
    # --------------------------------------------------------

    sales_amount = 0.0
    cgst_amount = 0.0
    sgst_amount = 0.0
    igst_amount = 0.0

    for item in invoice.items:
        sales_amount += float(item.amount or 0)

    for tax in invoice.taxes:
        account_head = str(tax.account_head or "").strip()
        tax_amount = float(tax.tax_amount or 0)

        if "IGST" in account_head.upper():
            igst_amount += tax_amount

        elif "CGST" in account_head.upper():
            cgst_amount += tax_amount

        elif "SGST" in account_head.upper():
            sgst_amount += tax_amount

    # --------------------------------------------------------
    # Build Tally inventory entries for Sales Invoice items
    # --------------------------------------------------------

    inventory_entries = ""

    for invoice_item in invoice.items:
        if not invoice_item.item_code:
            continue

        item = frappe.get_doc("Item", invoice_item.item_code)

        account_result = create_tally_account_ledger(invoice_item.income_account)
        if not account_result.get("success"):
            return account_result
        item_ledger = account_result["ledger_name"]
        stock_item_name = item.item_name
        uom = (
            invoice_item.uom
            or invoice_item.stock_uom
            or item.stock_uom
            or "Nos"
        )

        qty = float(invoice_item.qty or 0)
        rate = float(invoice_item.rate or 0)
        amount = float(invoice_item.amount or 0)

        inventory_entries += f"""
    <ALLINVENTORYENTRIES.LIST>

        <STOCKITEMNAME>{xml_escape(stock_item_name)}</STOCKITEMNAME>

        <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>

        <ISLASTDEEMEDPOSITIVE>No</ISLASTDEEMEDPOSITIVE>

        <ACTUALQTY>{qty:g} {xml_escape(uom)}</ACTUALQTY>

        <BILLEDQTY>{qty:g} {xml_escape(uom)}</BILLEDQTY>

        <RATE>{rate:g}/{xml_escape(uom)}</RATE>

        <AMOUNT>{amount:.2f}</AMOUNT>

        <ACCOUNTINGALLOCATIONS.LIST>

            <LEDGERNAME>{xml_escape(item_ledger)}</LEDGERNAME>

            <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>

            <AMOUNT>{amount:.2f}</AMOUNT>

        </ACCOUNTINGALLOCATIONS.LIST>

    </ALLINVENTORYENTRIES.LIST>
"""

    tax_entries = ""
    for tax in invoice.taxes:
        amount = float(tax.tax_amount or 0)
        if not amount:
            continue
        tax_result = create_tally_account_ledger(tax.account_head)
        if not tax_result.get("success"):
            return tax_result
        if tax.get("add_deduct_tax") == "Deduct":
            amount = -amount
        tax_entries += f"<LEDGERENTRIES.LIST><LEDGERNAME>{xml_escape(tax_result['ledger_name'])}</LEDGERNAME><ISDEEMEDPOSITIVE>{'Yes' if amount < 0 else 'No'}</ISDEEMEDPOSITIVE><AMOUNT>{amount:.2f}</AMOUNT></LEDGERENTRIES.LIST>"

    xml = f"""<ENVELOPE>
<HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Import</TALLYREQUEST>
    <TYPE>Data</TYPE>
    <ID>Vouchers</ID>
</HEADER>

<BODY>
<DESC>
    <STATICVARIABLES>
        <SVCURRENTCOMPANY>{xml_escape(tally_company)}</SVCURRENTCOMPANY>
        <SVERRORS>Yes</SVERRORS>
    </STATICVARIABLES>
</DESC>

<DATA>
<TALLYMESSAGE xmlns:UDF="TallyUDF">

<VOUCHER
    VCHTYPE="Sales"
    ACTION="Create"
    OBJVIEW="Invoice Voucher View">

    <DATE>{posting_date}</DATE>

    <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>

    <VOUCHERNUMBER>{xml_escape(invoice.name)}</VOUCHERNUMBER>

    <REFERENCE>{xml_escape(invoice.name)}</REFERENCE>

    <NUMBERINGSTYLE>Manual</NUMBERINGSTYLE>

    <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>

    <VOUCHERNUMBERSERIES>Default</VOUCHERNUMBERSERIES>

    <ISINVOICE>Yes</ISINVOICE>

    <PARTYLEDGERNAME>{xml_escape(customer)}</PARTYLEDGERNAME>

    <LEDGERENTRIES.LIST>

        <LEDGERNAME>{xml_escape(customer)}</LEDGERNAME>

        <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>

        <ISPARTYLEDGER>Yes</ISPARTYLEDGER>

        <AMOUNT>-{total_amount:.3f}</AMOUNT>

    </LEDGERENTRIES.LIST>

    {inventory_entries}

    {tax_entries}

</VOUCHER>

</TALLYMESSAGE>
</DATA>
</BODY>
</ENVELOPE>"""

    print("\n========== SALES INVOICE XML SENT TO TALLY ==========")
    print(xml)
    print("========== END XML ==========\n")

    result = send_to_tally(xml)

    # Save Tally internal Voucher ID in ERPNext.
    if result.get("success"):

        response = result.get("response", "")

        import re

        match = re.search(
            r"<LASTVCHID>(\d+)</LASTVCHID>",
            response
        )

        if match:

            tally_voucher_id = match.group(1)

            if tally_voucher_id != "0":

                frappe.db.set_value(
                    "Sales Invoice",
                    invoice_name,
                    "custom_tally_voucher_id",
                    tally_voucher_id
                )

                frappe.db.commit()

    return result


def cancel_tally_sales_invoice(invoice_name):
    """
    Cancel the same Sales Invoice voucher in TallyPrime.

    The Tally internal Voucher ID is stored in ERPNext in:
        custom_tally_voucher_id
    """

    invoice = frappe.get_doc("Sales Invoice", invoice_name)
    get_settings(invoice)

    tally_company = get_tally_company()

    tally_voucher_id = invoice.get("custom_tally_voucher_id")

    if not tally_voucher_id:

        frappe.throw(
            f"No Tally Voucher ID found for Sales Invoice "
            f"{xml_escape(invoice_name)}"
        )

    voucher_date = invoice.posting_date.strftime("%Y%m%d")

    xml_data = f"""<ENVELOPE>
<HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Import</TALLYREQUEST>
    <TYPE>Data</TYPE>
    <ID>Vouchers</ID>
</HEADER>

<BODY>
<DESC>
    <STATICVARIABLES>
        <SVCURRENTCOMPANY>{xml_escape(tally_company)}</SVCURRENTCOMPANY>
    </STATICVARIABLES>
</DESC>

<DATA>
<TALLYMESSAGE xmlns:UDF="TallyUDF">

<VOUCHER
    VCHTYPE="Sales"
    ACTION="Alter"
    OBJVIEW="Accounting Voucher View">

    <DATE>{voucher_date}</DATE>

    <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>

    <VOUCHERNUMBER>{xml_escape(invoice.name)}</VOUCHERNUMBER>

    <REFERENCE>{xml_escape(invoice.name)}</REFERENCE>

    <MASTERID>{tally_voucher_id}</MASTERID>

    <ISCANCELLED>Yes</ISCANCELLED>

</VOUCHER>

</TALLYMESSAGE>
</DATA>
</BODY>
</ENVELOPE>"""

    print("\n========== SALES INVOICE CANCEL XML ==========")
    print(xml_data)
    print("========== END XML ==========\n")

    return send_to_tally(xml_data)

# ============================================================
# DELETE TALLY SALES INVOICE
# ============================================================

def delete_tally_sales_invoice(invoice):

    invoice_name = invoice.name

    tally_voucher_id = invoice.get("custom_tally_voucher_id")

    if not tally_voucher_id or str(tally_voucher_id) == "0":

        message = (
            f"No valid Tally Voucher ID found for "
            f"Sales Invoice {xml_escape(invoice_name)}"
        )

        frappe.log_error(
            title="Tally Sales Invoice Delete Skipped",
            message=message
        )

        return {
            "success": False,
            "response": message
        }

    voucher_date = invoice.posting_date.strftime("%Y%m%d")

    xml_data = f"""<ENVELOPE>

<HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Import</TALLYREQUEST>
    <TYPE>Data</TYPE>
    <ID>Vouchers</ID>
</HEADER>

<BODY>

<DESC>
</DESC>

<DATA>

<TALLYMESSAGE>

<VOUCHER
    DATE="{voucher_date}"
    TAGNAME="Voucher Number"
    TAGVALUE="{xml_escape(invoice_name)}"
    VCHTYPE="Sales"
    ACTION="Delete">
</VOUCHER>

</TALLYMESSAGE>

</DATA>

</BODY>

</ENVELOPE>"""

    result = send_to_tally(xml_data)

    response = result.get("response", "")

    if (
        "<DELETED>1</DELETED>" not in response
        or "<LINEERROR>" in response
        or "<STATUS>0</STATUS>" in response
    ):

        frappe.log_error(
            title=f"Tally Sales Invoice Delete Failed: {xml_escape(invoice_name)}",
            message=response
        )

        return {
            "success": False,
            "response": response
        }

    return {
        "success": True,
        "response": response
    }
