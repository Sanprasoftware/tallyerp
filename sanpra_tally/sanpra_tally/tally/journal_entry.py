import re
import frappe

from sanpra_tally.sanpra_tally.tally_client import send_to_tally
from sanpra_tally.sanpra_tally.tally.supplier import create_tally_supplier_ledger
from sanpra_tally.sanpra_tally.tally.customer import create_tally_customer_ledger
from sanpra_tally.sanpra_tally.tally.account_ledger import create_tally_account_ledger

# ============================================================
# GET JOURNAL ENTRY
# ============================================================

def get_journal_entry(journal_entry_name):
    return frappe.get_doc("Journal Entry", journal_entry_name)


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
# CREATE TALLY JOURNAL ENTRY
# ============================================================

def create_tally_journal_entry(journal_entry_name):

    doc = get_journal_entry(journal_entry_name)
    
        # ========================================================
    # PREVENT DUPLICATE TALLY VOUCHER
    # ========================================================

    if doc.custom_tally_voucher_id:
        return {
            "success": False,
            "response": (
                f"Journal Entry {journal_entry_name} "
                f"is already synced to Tally. "
                f"Tally Voucher ID: "
                f"{doc.custom_tally_voucher_id}"
            ),
            "tally_voucher_id": doc.custom_tally_voucher_id
        }

    tally_company = get_tally_company()

    voucher_date = doc.posting_date.strftime("%Y%m%d")

    # ========================================================
    # BUILD LEDGER ENTRIES
    # ========================================================

    ledger_entries = ""

    for row in doc.accounts:

        account_name = row.account.strip()

        # Use the actual Tally party ledger for Supplier/Customer rows.
        if row.party_type == "Supplier" and row.party:
            supplier_result = create_tally_supplier_ledger(row.party)

            if not supplier_result.get("success"):
                return {
                    "success": False,
                    "response": supplier_result.get(
                        "message",
                        f"Failed to sync Supplier {row.party}"
                    )
                }

            account_name = supplier_result.get("ledger_name") or account_name

        elif row.party_type == "Customer" and row.party:
            customer_result = create_tally_customer_ledger(row.party)

            if not customer_result.get("success"):
                return {
                    "success": False,
                    "response": customer_result.get(
                        "message",
                        f"Failed to sync Customer {row.party}"
                    )
                }

            account_name = customer_result.get("ledger_name") or account_name

        elif not row.party_type and row.account:
            account_result = create_tally_account_ledger(row.account)

            if not account_result.get("success"):
                return {
                    "success": False,
                    "response": account_result.get(
                        "message",
                        f"Failed to sync Account {row.account}"
                    )
                }

            account_name = account_result.get("ledger_name") or account_name

        debit = float(row.debit or 0)
        credit = float(row.credit or 0)

        if debit:
            amount = -debit
            is_deemed_positive = "Yes"
        else:
            amount = credit
            is_deemed_positive = "No"

        ledger_entries += f"""
        <ALLLEDGERENTRIES.LIST>

            <LEDGERNAME>{account_name}</LEDGERNAME>

            <ISDEEMEDPOSITIVE>{is_deemed_positive}</ISDEEMEDPOSITIVE>

            <AMOUNT>{amount}</AMOUNT>

        </ALLLEDGERENTRIES.LIST>
        """

    # ========================================================
    # TALLY CREATE XML
    # ========================================================

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

<TALLYMESSAGE>

<VOUCHER
    VCHTYPE="Journal"
    ACTION="Create"
    OBJVIEW="Accounting Voucher View">

    <DATE>{voucher_date}</DATE>

    <VOUCHERTYPENAME>Journal</VOUCHERTYPENAME>
    
    <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>

    <VOUCHERNUMBER>{journal_entry_name}</VOUCHERNUMBER>

    <NARRATION>{doc.remark or ""}</NARRATION>

    {ledger_entries}

</VOUCHER>

</TALLYMESSAGE>

</DATA>

</BODY>

</ENVELOPE>"""

    # ========================================================
    # SEND TO TALLY
    # ========================================================

    result = send_to_tally(xml_data)

    response = result.get("response", "")

    # ========================================================
    # CHECK RESPONSE
    # ========================================================

    if (
        "<CREATED>1</CREATED>" not in response
        or "<LINEERROR>" in response
        or "<STATUS>0</STATUS>" in response
    ):
        frappe.log_error(
            title=f"Tally Journal Create Failed: {journal_entry_name}",
            message=response
        )

        return {
            "success": False,
            "response": response
        }

    # ========================================================
    # GET TALLY VOUCHER ID
    # ========================================================

    match = re.search(r"<LASTVCHID>(\d+)</LASTVCHID>", response)

    if not match:
        frappe.log_error(
            title=f"Tally Voucher ID Missing: {journal_entry_name}",
            message=response
        )

        return {
            "success": False,
            "response": response
        }

    tally_voucher_id = match.group(1)

    # ========================================================
    # SAVE TALLY VOUCHER ID IN ERPNEXT
    # ========================================================

    frappe.db.set_value(
        "Journal Entry",
        journal_entry_name,
        "custom_tally_voucher_id",
        tally_voucher_id
    )

    frappe.db.commit()

    return {
        "success": True,
        "tally_voucher_id": tally_voucher_id,
        "response": response
    }
    
    
# ============================================================
# CANCEL TALLY JOURNAL ENTRY
# ============================================================

def cancel_tally_journal_entry(journal_entry_name):

    doc = get_journal_entry(journal_entry_name)

    tally_voucher_id = doc.get("custom_tally_voucher_id")

    if not tally_voucher_id or str(tally_voucher_id) == "0":
        message = (
            f"No valid Tally Voucher ID found for "
            f"Journal Entry {journal_entry_name}"
        )

        frappe.log_error(
            title="Tally Journal Cancel Skipped",
            message=message
        )

        return {
            "success": False,
            "response": message
        }

    voucher_date = doc.posting_date.strftime("%d-%b-%Y")

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
    TAGNAME="VoucherNumber"
    TAGVALUE="{journal_entry_name}"
    VCHTYPE="Journal"
    ACTION="Cancel">

    <NARRATION>Cancelled from ERPNext</NARRATION>

</VOUCHER>

</TALLYMESSAGE>

</DATA>

</BODY>

</ENVELOPE>"""

    result = send_to_tally(xml_data)

    response = result.get("response", "")

    if (
        "<CANCELLED>1</CANCELLED>" not in response
        or "<LINEERROR>" in response
        or "<STATUS>0</STATUS>" in response
    ):
        frappe.log_error(
            title=f"Tally Journal Cancel Failed: {journal_entry_name}",
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
    
    
    
def delete_tally_journal_entry(doc):

    journal_entry_name = doc.name

    tally_company = get_tally_company()

    tally_voucher_id = doc.get("custom_tally_voucher_id")

    # ========================================================
    # VALIDATE TALLY VOUCHER ID
    # ========================================================

    if not tally_voucher_id or str(tally_voucher_id) == "0":

        message = (
            f"No valid Tally Voucher ID found for "
            f"Journal Entry {journal_entry_name}"
        )

        frappe.log_error(
            title="Tally Journal Delete Skipped",
            message=message
        )

        return {
            "success": False,
            "response": message
        }

    # ========================================================
    # VOUCHER DATE
    # ========================================================

    voucher_date = doc.posting_date.strftime("%d-%b-%Y")

    # ========================================================
    # TALLY DELETE XML
    #
    # IMPORTANT:
    # For Delete, use the documented Tally structure:
    #
    # <DESC></DESC>
    # <DATA>
    #
    # Do NOT use REQUESTDESC / REQUESTDATA here.
    # ========================================================

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
    TAGVALUE="{journal_entry_name}"
    VCHTYPE="Journal"
    ACTION="Delete">
</VOUCHER>

</TALLYMESSAGE>

</DATA>

</BODY>

</ENVELOPE>"""

    # ========================================================
    # SEND TO TALLY
    # ========================================================

    result = send_to_tally(xml_data)

    response = result.get("response", "")

    # ========================================================
    # CHECK TALLY RESPONSE
    # ========================================================

    if (
        "<DELETED>1</DELETED>" not in response
        or "<LINEERROR>" in response
        or "<STATUS>0</STATUS>" in response
    ):

        frappe.log_error(
            title=f"Tally Journal Delete Failed: {journal_entry_name}",
            message=response
        )

        return {
            "success": False,
            "response": response
        }

    # ========================================================
    # SUCCESS
    # ========================================================

    return {
        "success": True,
        "response": response
    }
