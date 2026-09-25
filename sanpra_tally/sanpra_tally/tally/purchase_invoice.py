from sanpra_tally.sanpra_tally.tally.account_ledger import create_tally_account_ledger
from xml.sax.saxutils import escape
from sanpra_tally.subscription_client import get_settings

def xml_escape(value):
    return escape(str(value or ""), {'"': "&quot;", "'": "&apos;"})

import re
import frappe
import calendar

from sanpra_tally.sanpra_tally.tally_client import get_tally_settings, send_to_tally
from sanpra_tally.sanpra_tally.tally.supplier import create_tally_supplier_ledger
from sanpra_tally.sanpra_tally.tally.item import create_tally_stock_item
from sanpra_tally.sanpra_tally.tally.tax_ledger import create_tally_tax_ledger

# ============================================================
# GET TALLY COMPANY
# ============================================================

def get_tally_company():
    return get_tally_settings().tally_company


# ============================================================
# CREATE PURCHASE INVOICE IN TALLY
# ============================================================

def create_tally_purchase_invoice(invoice_name):
    invoice = frappe.get_doc("Purchase Invoice", invoice_name)
    get_settings(invoice)

    # --------------------------------------------------------
    # Prevent duplicate Tally voucher
    # --------------------------------------------------------

    tally_voucher_id = invoice.get("custom_tally_voucher_id")

    if tally_voucher_id and str(tally_voucher_id) != "0":
        return {
            "success": False,
            "response": (
                f"Purchase Invoice {xml_escape(invoice_name)} "
                f"is already synced to Tally. "
                f"Tally Voucher ID: {tally_voucher_id}"
            ),
            "tally_voucher_id": tally_voucher_id,
        }

    # Ensure supplier ledger exists in Tally
    supplier_result = create_tally_supplier_ledger(invoice.supplier)

    if not supplier_result.get("success"):
        return {
            "success": False,
            "response": (
                f"Unable to create/ensure Tally supplier ledger "
                f"for {invoice.supplier}.\n\n"
                f"{supplier_result.get('response', supplier_result.get('message', 'Unknown error'))}"
            ),
        }
    
    supplier = supplier_result.get("ledger_name")

    if not supplier:
        return {
            "success": False,
            "response": (
                f"Tally supplier ledger name was not returned for "
                f"{invoice.supplier}."
            ),
        }
    # Ensure all Purchase Invoice Items exist in Tally
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

  # Ensure Purchase Invoice tax ledgers exist in Tally
    tax_ledgers = []

    for tax in invoice.taxes:
        if not tax.account_head or not tax.tax_amount:
            continue

        tax_result = create_tally_tax_ledger(tax.account_head)

        if not tax_result.get("success"):
            return {
                "success": False,
                "response": (
                    f"Unable to create/ensure Tally Tax Ledger "
                    f"for {tax.account_head}.\n\n"
                    f"{tax_result.get('response', tax_result.get('message', 'Unknown error'))}"
                ),
            }

        tax_ledgers.append({
            "ledger_name": tax_result.get("ledger_name"),
            "amount": -float(tax.tax_amount or 0) if tax.get("add_deduct_tax") == "Deduct" else float(tax.tax_amount or 0),
        })

    settings = get_tally_settings()
    tally_company = settings.tally_company

    if not tally_company:
        return {
            "success": False,
            "response": "Tally Company is not configured."
        }

    total_amount = invoice.grand_total

    posting_date = invoice.posting_date.strftime("%d-%b-%Y")

    inventory_entries = ""

    for invoice_item in invoice.items:

        if not invoice_item.item_code:
            continue

        item = frappe.get_doc("Item", invoice_item.item_code)

        account_result = create_tally_account_ledger(invoice_item.expense_account)
        if not account_result.get("success"):
            return account_result
        item_ledger = account_result["ledger_name"]
        stock_item_name = item.item_name
        uom = invoice_item.uom or invoice_item.stock_uom or item.stock_uom or "Nos"
        qty = float(invoice_item.qty or 0)
        rate = float(invoice_item.rate or 0)
        amount = float(invoice_item.amount or 0)

        inventory_entries += f"""
    <ALLINVENTORYENTRIES.LIST>

        <STOCKITEMNAME>{xml_escape(stock_item_name)}</STOCKITEMNAME>

        <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>

        <ISLASTDEEMEDPOSITIVE>Yes</ISLASTDEEMEDPOSITIVE>

        <ACTUALQTY>{qty:g} {xml_escape(uom)}</ACTUALQTY>

        <BILLEDQTY>{qty:g} {xml_escape(uom)}</BILLEDQTY>

        <RATE>{rate:g}/{xml_escape(uom)}</RATE>

        <AMOUNT>{-amount:.2f}</AMOUNT>

        <ACCOUNTINGALLOCATIONS.LIST>

            <LEDGERNAME>{xml_escape(item_ledger)}</LEDGERNAME>

            <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>

            <AMOUNT>{-amount:.2f}</AMOUNT>

        </ACCOUNTINGALLOCATIONS.LIST>

    </ALLINVENTORYENTRIES.LIST>
"""

    tax_entries = ""

    for tax in tax_ledgers:
        tax_amount = tax["amount"]
        ledger_name = tax["ledger_name"]

        tally_amount = -tax_amount
        tax_entries += f"<LEDGERENTRIES.LIST><LEDGERNAME>{xml_escape(ledger_name)}</LEDGERNAME><ISDEEMEDPOSITIVE>{'Yes' if tally_amount < 0 else 'No'}</ISDEEMEDPOSITIVE><ISPARTYLEDGER>No</ISPARTYLEDGER><AMOUNT>{tally_amount:.2f}</AMOUNT></LEDGERENTRIES.LIST>"

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
        <SVERRORS>Yes</SVERRORS>
    </STATICVARIABLES>
</DESC>

<DATA>

<TALLYMESSAGE xmlns:UDF="TallyUDF">

<VOUCHER
    VCHTYPE="Purchase"
    ACTION="Create"
    OBJVIEW="Invoice Voucher View">

    <DATE>{posting_date}</DATE>

    <VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>

    <VOUCHERNUMBER>{xml_escape(invoice_name)}</VOUCHERNUMBER>

    <REFERENCE>{xml_escape(invoice_name)}</REFERENCE>

    <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>

    <ISINVOICE>Yes</ISINVOICE>

    <PARTYLEDGERNAME>{xml_escape(supplier)}</PARTYLEDGERNAME>

    <LEDGERENTRIES.LIST>

        <LEDGERNAME>{xml_escape(supplier)}</LEDGERNAME>

        <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>

        <ISPARTYLEDGER>Yes</ISPARTYLEDGER>

        <AMOUNT>{total_amount:.2f}</AMOUNT>

    </LEDGERENTRIES.LIST>

        {inventory_entries}

    {tax_entries}

</VOUCHER>

</TALLYMESSAGE>

</DATA>

</BODY>
</ENVELOPE>"""

    print("\n========== PURCHASE CREATE XML ==========")
    print(xml_data)
    print("=========================================\n")

    result = send_to_tally(xml_data)

    if not result.get("success"):
        return result

    response = result.get("response", "")

    # --------------------------------------------------------
    # CHECK CREATE FAILURE
    # --------------------------------------------------------

    if (
        "<STATUS>0</STATUS>" in response
        or "<ERRORS>1</ERRORS>" in response
        or "<CREATED>0</CREATED>" in response
    ):
        frappe.log_error(
            title=f"Tally Purchase Invoice Create Failed: {xml_escape(invoice_name)}",
            message=response
        )

        return {
            "success": False,
            "response": response
        }

    # --------------------------------------------------------
    # GET TALLY MASTER ID
    # --------------------------------------------------------

    match = re.search(
        r"<LASTVCHID>(\d+)</LASTVCHID>",
        response
    )

    if not match:

        frappe.log_error(
            title=f"Tally Purchase Invoice Master ID Missing: {xml_escape(invoice_name)}",
            message=response
        )

        return {
            "success": False,
            "response": response
        }

    tally_voucher_id = match.group(1)

    # --------------------------------------------------------
    # SAVE TALLY VOUCHER ID
    # --------------------------------------------------------

    frappe.db.set_value(
        "Purchase Invoice",
        invoice_name,
        "custom_tally_voucher_id",
        tally_voucher_id
    )


    frappe.db.commit()

    print("Tally Voucher ID:", tally_voucher_id)
    print("Tally Voucher Number:", invoice_name)

    return {
        "success": True,
        "response": response,
        "tally_voucher_id": tally_voucher_id,
        "tally_voucher_number": invoice_name
    }


# ============================================================
# CANCEL PURCHASE INVOICE IN TALLY
# ============================================================

def cancel_tally_purchase_invoice(invoice_name):
    import frappe
    from sanpra_tally.sanpra_tally.tally_client import get_tally_settings, send_to_tally

    invoice = frappe.get_doc("Purchase Invoice", invoice_name)
    get_settings(invoice)
    tally_company = get_tally_company()

    voucher_id = invoice.custom_tally_voucher_id

    if not voucher_id:
        return {
            "success": False,
            "response": "No Tally Voucher ID found."
        }

    posting_date = invoice.posting_date.strftime("%d-%b-%Y")

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
    </STATICVARIABLES>
</DESC>

<DATA>
<TALLYMESSAGE xmlns:UDF="TallyUDF">

<VOUCHER VCHTYPE="Purchase" ACTION="Alter">

    <DATE>{posting_date}</DATE>

    <VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>

    <VOUCHERNUMBER>{xml_escape(invoice.name)}</VOUCHERNUMBER>

    <REFERENCE>{xml_escape(invoice.name)}</REFERENCE>

    <MASTERID>{xml_escape(voucher_id)}</MASTERID>

    <ISCANCELLED>Yes</ISCANCELLED>

</VOUCHER>

</TALLYMESSAGE>
</DATA>
</BODY>
</ENVELOPE>"""

    print("\n========== PURCHASE CANCEL XML ==========")
    print(xml)
    print("========================================\n")

    result = send_to_tally(xml)

    response = result.get("response", "")

    import re

    if (
        ("<CREATED>1</CREATED>" in response or "<ALTERED>1</ALTERED>" in response)
        and "<ERRORS>0</ERRORS>" in response
        and "<EXCEPTIONS>0</EXCEPTIONS>" in response
    ):
        match = re.search(r"<LASTVCHID>(\d+)</LASTVCHID>", response)

        if match:
            cancel_voucher_id = match.group(1)

            frappe.db.set_value(
                "Purchase Invoice",
                invoice_name,
                "custom_tally_cancel_voucher_id",
                cancel_voucher_id,
                update_modified=False
            )

        return {
            "success": True,
            "response": response
        }

    frappe.log_error(
        title=f"Tally Purchase Cancel Failed: {xml_escape(invoice_name)}",
        message=response
    )

    return {"success": False, "response": response}
# ============================================================
# DELETE PURCHASE INVOICE FROM TALLY
# ============================================================

def delete_tally_purchase_invoice(invoice):

    invoice_name = invoice.name

    tally_company = get_tally_company()

    tally_voucher_number = invoice.name

    if not tally_voucher_number:

        message = (
            f"No Tally Voucher Number found for "
            f"Purchase Invoice {xml_escape(invoice_name)}"
        )

        frappe.log_error(
            title="Tally Purchase Invoice Delete Skipped",
            message=message
        )

        return {
            "success": False,
            "response": message
        }

    voucher_date = invoice.posting_date.strftime("%d-%b-%Y")

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

<TALLYMESSAGE>

<VOUCHER
    DATE="{voucher_date}"
    TAGNAME="VoucherNumber"
    TAGVALUE="{xml_escape(tally_voucher_number)}"
    VCHTYPE="Purchase"
    ACTION="Delete">
</VOUCHER>

</TALLYMESSAGE>

</DATA>

</BODY>
</ENVELOPE>"""

    print("\n========== PURCHASE DELETE XML ==========")
    print(xml_data)
    print("=========================================\n")

    result = send_to_tally(xml_data)

    response = result.get("response", "")

    if (
        "<DELETED>1</DELETED>" in response
        and "<LINEERROR>" not in response
        and "<STATUS>0</STATUS>" not in response
    ):

        return {
            "success": True,
            "response": response
        }

    frappe.log_error(
        title=f"Tally Purchase Invoice Delete Failed: {xml_escape(invoice_name)}",
        message=response
    )

    return {
        "success": False,
        "response": response
    }
