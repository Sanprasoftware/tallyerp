import re
import frappe
import calendar

from parshwa.parshwa.tally_client import send_to_tally
from parshwa.parshwa.tally.supplier import create_tally_supplier_ledger
from parshwa.parshwa.tally.item import create_tally_stock_item
from parshwa.parshwa.tally.tax_ledger import create_tally_tax_ledger

# ============================================================
# GET TALLY COMPANY
# ============================================================

def get_tally_company():
    settings = frappe.get_all(
        "Tally Settings",
        filters={"enabled": 1},
        fields=["tally_company"],
        limit=1
    )

    if not settings:
        frappe.throw("No enabled Tally Settings found.")

    return settings[0].tally_company


# ============================================================
# CREATE PURCHASE INVOICE IN TALLY
# ============================================================

def create_tally_purchase_invoice(invoice_name):
    invoice = frappe.get_doc("Purchase Invoice", invoice_name)

    # --------------------------------------------------------
    # Prevent duplicate Tally voucher
    # --------------------------------------------------------

    tally_voucher_id = invoice.get("custom_tally_voucher_id")

    if tally_voucher_id and str(tally_voucher_id) != "0":
        return {
            "success": False,
            "response": (
                f"Purchase Invoice {invoice_name} "
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
            "amount": float(tax.tax_amount or 0),
        })

    settings = frappe.get_doc(
        "Tally Settings",
        frappe.db.get_value(
            "Tally Settings",
            {"enabled": 1},
            "name"
        )
    )

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

        stock_item_name = item.item_name
        uom = invoice_item.uom or invoice_item.stock_uom or item.stock_uom or "Nos"
        qty = float(invoice_item.qty or 0)
        rate = float(invoice_item.rate or 0)
        amount = float(invoice_item.amount or 0)

        inventory_entries += f"""
    <ALLINVENTORYENTRIES.LIST>

        <STOCKITEMNAME>{stock_item_name}</STOCKITEMNAME>

        <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>

        <ISLASTDEEMEDPOSITIVE>Yes</ISLASTDEEMEDPOSITIVE>

        <ACTUALQTY>{qty:g} {uom}</ACTUALQTY>

        <BILLEDQTY>{qty:g} {uom}</BILLEDQTY>

        <RATE>{rate:g}/{uom}</RATE>

        <AMOUNT>{amount:.2f}</AMOUNT>

        <ACCOUNTINGALLOCATIONS.LIST>

            <LEDGERNAME>Purchase</LEDGERNAME>

            <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>

            <AMOUNT>{amount:.2f}</AMOUNT>

        </ACCOUNTINGALLOCATIONS.LIST>

    </ALLINVENTORYENTRIES.LIST>
"""

    tax_entries = ""

    for tax in tax_ledgers:
        tax_amount = tax["amount"]
        ledger_name = tax["ledger_name"]

        # TDS is a liability and must be credited.
        is_tds = "TDS" in ledger_name.upper()

        if is_tds and tax_amount > 0:
            tax_entries += f"""
    <LEDGERENTRIES.LIST>
        <LEDGERNAME>{ledger_name}</LEDGERNAME>
        <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
        <ISPARTYLEDGER>No</ISPARTYLEDGER>
        <AMOUNT>-{tax_amount:.2f}</AMOUNT>
    </LEDGERENTRIES.LIST>
"""
        elif tax_amount > 0:
            tax_entries += f"""
    <LEDGERENTRIES.LIST>
        <LEDGERNAME>{ledger_name}</LEDGERNAME>
        <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
        <ISPARTYLEDGER>No</ISPARTYLEDGER>
        <AMOUNT>{tax_amount:.2f}</AMOUNT>
    </LEDGERENTRIES.LIST>
"""
        elif tax_amount < 0:
            tax_entries += f"""
    <LEDGERENTRIES.LIST>
        <LEDGERNAME>{ledger_name}</LEDGERNAME>
        <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
        <ISPARTYLEDGER>No</ISPARTYLEDGER>
        <AMOUNT>{tax_amount:.2f}</AMOUNT>
    </LEDGERENTRIES.LIST>
"""

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
        <SVCURRENTCOMPANY>{tally_company}</SVCURRENTCOMPANY>
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

    <VOUCHERNUMBER>{invoice_name}</VOUCHERNUMBER>

    <REFERENCE>{invoice_name}</REFERENCE>

    <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>

    <ISINVOICE>Yes</ISINVOICE>

    <PARTYLEDGERNAME>{supplier}</PARTYLEDGERNAME>

    <LEDGERENTRIES.LIST>

        <LEDGERNAME>{supplier}</LEDGERNAME>

        <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>

        <ISPARTYLEDGER>Yes</ISPARTYLEDGER>

        <AMOUNT>-{total_amount:.2f}</AMOUNT>

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
            title=f"Tally Purchase Invoice Create Failed: {invoice_name}",
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
            title=f"Tally Purchase Invoice Master ID Missing: {invoice_name}",
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
    from parshwa.parshwa.tally_client import send_to_tally

    invoice = frappe.get_doc("Purchase Invoice", invoice_name)
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
        <SVCURRENTCOMPANY>{tally_company}</SVCURRENTCOMPANY>
    </STATICVARIABLES>
</DESC>

<DATA>
<TALLYMESSAGE xmlns:UDF="TallyUDF">

<VOUCHER VCHTYPE="Purchase" ACTION="Alter">

    <DATE>{posting_date}</DATE>

    <VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>

    <VOUCHERNUMBER>{invoice.name}</VOUCHERNUMBER>

    <REFERENCE>{invoice.name}</REFERENCE>

    <MASTERID>{voucher_id}</MASTERID>

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
        match = re.search(r"<LASTVCHID>(\\d+)</LASTVCHID>", response)

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
        title=f"Tally Purchase Cancel Failed: {invoice_name}",
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
            f"Purchase Invoice {invoice_name}"
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
        <SVCURRENTCOMPANY>{tally_company}</SVCURRENTCOMPANY>
    </STATICVARIABLES>
</DESC>

<DATA>

<TALLYMESSAGE>

<VOUCHER
    DATE="{voucher_date}"
    TAGNAME="VoucherNumber"
    TAGVALUE="{tally_voucher_number}"
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
        title=f"Tally Purchase Invoice Delete Failed: {invoice_name}",
        message=response
    )

    return {
        "success": False,
        "response": response
    }
