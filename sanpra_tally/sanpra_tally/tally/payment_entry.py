import re
import frappe

from sanpra_tally.sanpra_tally.tally_client import send_to_tally


# ============================================================
# GET PAYMENT ENTRY
# ============================================================

def get_payment_entry(payment_entry_name):
    return frappe.get_doc("Payment Entry", payment_entry_name)


# ============================================================
# TALLY LEDGER NAME
# ============================================================

def get_tally_ledger_name(account):
    """
    Convert ERPNext account names to corresponding
    Tally ledger names.
    """

    if not account:
        return ""

    account = str(account).strip()

    ledger_mapping = {
        "Cash - PEPL": "Cash",
        "HDFC Bank - PEPL": "HDFC Bank - PEPL",
    }

    return ledger_mapping.get(account, account)


# ============================================================
# XML ESCAPE
# ============================================================

def xml_escape(value):

    if value is None:
        return ""

    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


# ============================================================
# GET PAYMENT DATE
# ============================================================

def get_payment_date(doc):
    """
    New Tally vouchers use the ERPNext Payment Entry posting date.
    """

    return doc.posting_date.strftime("%Y%m%d")


# ============================================================
# CREATE PAYMENT ENTRY IN TALLY
# ============================================================

def create_tally_payment_entry(payment_entry_name):

    doc = get_payment_entry(payment_entry_name)
    
        # --------------------------------------------------------
    # Prevent duplicate Tally voucher
    # --------------------------------------------------------

    if doc.custom_tally_voucher_id:
        return {
            "success": False,
            "response": (
                f"Payment Entry {payment_entry_name} "
                f"is already synced to Tally. "
                f"Tally Voucher ID: {doc.custom_tally_voucher_id}"
            ),
            "xml": "",
            "tally_voucher_id": doc.custom_tally_voucher_id,
        }

    # --------------------------------------------------------
    # Determine voucher type
    # --------------------------------------------------------

    if doc.payment_type == "Pay":

        voucher_type = "Payment"

        amount = doc.paid_amount or doc.received_amount

        debit_account = doc.paid_to
        credit_account = doc.paid_from

    elif doc.payment_type == "Receive":

        voucher_type = "Receipt"

        amount = doc.received_amount or doc.paid_amount

        debit_account = doc.paid_to
        credit_account = doc.paid_from

    elif doc.payment_type == "Internal Transfer":

        voucher_type = "Contra"

        amount = doc.paid_amount or doc.received_amount

        debit_account = doc.paid_to
        credit_account = doc.paid_from

    else:

        return {
            "success": False,
            "response": (
                f"Unsupported Payment Type: {doc.payment_type}"
            ),
            "xml": "",
            "tally_voucher_id": None,
        }

    # --------------------------------------------------------
    # Validate amount
    # --------------------------------------------------------

    if not amount or float(amount) <= 0:

        return {
            "success": False,
            "response": (
                f"Invalid payment amount: {amount}"
            ),
            "xml": "",
            "tally_voucher_id": None,
        }

    amount = abs(float(amount))

    # --------------------------------------------------------
    # Ledger names
    # --------------------------------------------------------

    debit_ledger = get_tally_ledger_name(
        debit_account
    )

    credit_ledger = get_tally_ledger_name(
        credit_account
    )

    if not debit_ledger:

        return {
            "success": False,
            "response": "Debit ledger is missing.",
            "xml": "",
            "tally_voucher_id": None,
        }

    if not credit_ledger:

        return {
            "success": False,
            "response": "Credit ledger is missing.",
            "xml": "",
            "tally_voucher_id": None,
        }

    # --------------------------------------------------------
    # Date
    # --------------------------------------------------------

    date_value = get_payment_date(doc)

    # --------------------------------------------------------
    # XML values
    # --------------------------------------------------------

    voucher_type_xml = xml_escape(voucher_type)

    voucher_number_xml = xml_escape(
        doc.name
    )

    debit_ledger_xml = xml_escape(
        debit_ledger
    )

    credit_ledger_xml = xml_escape(
        credit_ledger
    )

    narration_xml = xml_escape(
        doc.remarks or doc.name
    )

    # --------------------------------------------------------
    # CREATE TALLY XML
    # --------------------------------------------------------

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
<SVCURRENTCOMPANY>Parshwa</SVCURRENTCOMPANY>
</STATICVARIABLES>
</DESC>

<DATA>

<TALLYMESSAGE xmlns:UDF="TallyUDF">

<VOUCHER
REMOTEID="ERPNext-Payment-{xml_escape(doc.name)}"
VCHTYPE="{voucher_type_xml}"
ACTION="Create"
OBJVIEW="Accounting Voucher View">

<DATE>{date_value}</DATE>

<EFFECTIVEDATE>{date_value}</EFFECTIVEDATE>

<VOUCHERNUMBER>{voucher_number_xml}</VOUCHERNUMBER>

<VOUCHERTYPENAME>{voucher_type_xml}</VOUCHERTYPENAME>

<PARTYLEDGERNAME>{debit_ledger_xml}</PARTYLEDGERNAME>

<ALLLEDGERENTRIES.LIST>

<LEDGERNAME>{debit_ledger_xml}</LEDGERNAME>

<ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>

<ISPARTYLEDGER>No</ISPARTYLEDGER>

<AMOUNT>-{amount:.2f}</AMOUNT>

</ALLLEDGERENTRIES.LIST>

<ALLLEDGERENTRIES.LIST>

<LEDGERNAME>{credit_ledger_xml}</LEDGERNAME>

<ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>

<ISPARTYLEDGER>Yes</ISPARTYLEDGER>

<AMOUNT>{amount:.2f}</AMOUNT>

</ALLLEDGERENTRIES.LIST>

<NARRATION>{narration_xml}</NARRATION>

</VOUCHER>

</TALLYMESSAGE>

</DATA>

</BODY>

</ENVELOPE>"""

    # --------------------------------------------------------
    # SEND TO TALLY
    # --------------------------------------------------------

    result = send_to_tally(xml_data)

    response = result.get(
        "response",
        ""
    )

    # --------------------------------------------------------
    # CHECK SUCCESS
    # --------------------------------------------------------

    success = (
        "<CREATED>1</CREATED>" in response
        and "<EXCEPTIONS>0</EXCEPTIONS>" in response
    )

    # --------------------------------------------------------
    # GET TALLY MASTER ID
    # --------------------------------------------------------

    tally_voucher_id = None

    if success:

        match = re.search(
            r"<LASTVCHID>(\d+)</LASTVCHID>",
            response
        )

        if match:

            tally_voucher_id = match.group(1)

            # ------------------------------------------------
            # Save Tally Master ID
            # ------------------------------------------------

            frappe.db.set_value(
                "Payment Entry",
                doc.name,
                "custom_tally_voucher_id",
                tally_voucher_id
            )

            # ------------------------------------------------
            # Save Tally Voucher Date
            # ------------------------------------------------

            frappe.db.set_value(
                "Payment Entry",
                doc.name,
                "custom_tally_voucher_date",
                doc.posting_date
            )

            frappe.db.commit()

    return {
        "success": success,
        "response": response,
        "xml": xml_data,
        "tally_voucher_id": tally_voucher_id,
    }


# ============================================================
# CANCEL PAYMENT ENTRY IN TALLY
# ============================================================

# ============================================================
# CANCEL PAYMENT ENTRY IN TALLY
# ============================================================

def cancel_tally_payment_entry(payment_entry_name):

    doc = get_payment_entry(payment_entry_name)

    # --------------------------------------------------------
    # Get Tally Master ID
    # --------------------------------------------------------

    tally_master_id = doc.custom_tally_voucher_id

    if not tally_master_id:
        return {
            "success": False,
            "response": (
                f"No Tally Voucher ID found for Payment Entry "
                f"{payment_entry_name}"
            ),
            "xml": "",
            "tally_voucher_id": None,
        }

    # --------------------------------------------------------
    # Determine Voucher Type
    # --------------------------------------------------------

    if doc.payment_type == "Pay":
        voucher_type = "Payment"

    elif doc.payment_type == "Receive":
        voucher_type = "Receipt"

    elif doc.payment_type == "Internal Transfer":
        voucher_type = "Contra"

    else:
        return {
            "success": False,
            "response": (
                f"Unsupported Payment Type: {doc.payment_type}"
            ),
            "xml": "",
            "tally_voucher_id": tally_master_id,
        }

    # --------------------------------------------------------
    # Get Tally Voucher Date
    # --------------------------------------------------------

    tally_voucher_date = doc.custom_tally_voucher_date

    if not tally_voucher_date:
        return {
            "success": False,
            "response": (
                f"No Tally Voucher Date found for Payment Entry "
                f"{payment_entry_name}"
            ),
            "xml": "",
            "tally_voucher_id": tally_master_id,
        }

    # --------------------------------------------------------
    # Date formats
    # --------------------------------------------------------

    date_value = tally_voucher_date.strftime("%Y%m%d")
    date_display = tally_voucher_date.strftime("%d-%b-%Y")

    # --------------------------------------------------------
    # CANCEL TALLY XML
    # --------------------------------------------------------

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
    DATE="{date_display}"
    TAGNAME="MASTER ID"
    TAGVALUE="{xml_escape(tally_master_id)}"
    ACTION="Cancel"
    VCHTYPE="{xml_escape(voucher_type)}">

    <NARRATION>
        Cancelled from ERPNext Payment Entry {xml_escape(payment_entry_name)}
    </NARRATION>

</VOUCHER>

</TALLYMESSAGE>

</DATA>

</BODY>
</ENVELOPE>"""

    # --------------------------------------------------------
    # SEND TO TALLY
    # --------------------------------------------------------

    result = send_to_tally(xml_data)

    response = result.get("response", "")

    # --------------------------------------------------------
    # CHECK RESULT
    # --------------------------------------------------------

    success = (
        "<CANCELLED>1</CANCELLED>" in response
        and "<EXCEPTIONS>0</EXCEPTIONS>" in response
        and "<ERRORS>0</ERRORS>" in response
    )

    return {
        "success": success,
        "response": response,
        "xml": xml_data,
        "tally_voucher_id": tally_master_id,
    }

# ============================================================
# DELETE PAYMENT ENTRY FROM TALLY
# ============================================================

def delete_tally_payment_entry(doc):
    """
    Delete the corresponding Tally voucher using ERPNext Payment Entry REMOTEID.
    """

    if not doc:
        return {
            "success": False,
            "response": "Payment Entry document is missing."
        }

    payment_entry_name = doc.name

    remote_id = f"ERPNext-Payment-{payment_entry_name}"

    xml = f"""
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>Vouchers</ID>
    </HEADER>

    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVCURRENTCOMPANY>Parshwa</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>

        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">

                <VOUCHER
                    REMOTEID="{xml_escape(remote_id)}"
                    ACTION="Delete">
                </VOUCHER>

            </TALLYMESSAGE>
        </DATA>
    </BODY>
</ENVELOPE>
"""

    result = send_to_tally(xml)

    if not result.get("success"):
        return {
            "success": False,
            "response": result.get("response", ""),
            "remote_id": remote_id
        }

    response = result.get("response", "")

    deleted = re.search(r"<DELETED>(\d+)</DELETED>", response)
    errors = re.search(r"<ERRORS>(\d+)</ERRORS>", response)

    deleted_count = int(deleted.group(1)) if deleted else 0
    error_count = int(errors.group(1)) if errors else 0

    success = deleted_count == 1 and error_count == 0

    return {
        "success": success,
        "remote_id": remote_id,
        "deleted": deleted_count,
        "errors": error_count,
        "response": response
    }