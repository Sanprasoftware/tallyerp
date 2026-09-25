"""Sync Payment Entries using the amounts actually posted to the ERP ledger."""
from collections import defaultdict
from datetime import date
from decimal import Decimal
from xml.sax.saxutils import escape, quoteattr
from xml.etree.ElementTree import ParseError

import frappe
from defusedxml.ElementTree import fromstring
from defusedxml.common import DefusedXmlException

from sanpra_tally.subscription_client import get_settings
from sanpra_tally.sanpra_tally.tally_client import send_to_tally
from sanpra_tally.sanpra_tally.tally.account_ledger import create_tally_account_ledger
from sanpra_tally.sanpra_tally.tally.customer import create_tally_customer_ledger
from sanpra_tally.sanpra_tally.tally.supplier import create_tally_supplier_ledger

VOUCHER_TYPES = {"Pay": "Payment", "Receive": "Receipt", "Internal Transfer": "Contra"}


def get_payment_entry(name):
    return frappe.get_doc("Payment Entry", name)


def xml_escape(value):
    return escape(str(value or ""), {'"': '&quot;', "'": '&apos;'})


def get_payment_date(doc):
    return date.fromisoformat(str(doc.posting_date)[:10]).strftime("%Y%m%d")


def failure(message, **values):
    return {"success": False, "response": message, "xml": "", **values}


def response_ok(result, counter=None):
    if not result.get("success"):
        return False
    try:
        root = fromstring(result.get("response", ""), forbid_dtd=True)
        if any((n.text or "").strip() for n in root.iter("LINEERROR")):
            return False
        if any(int(n.text or 0) for tag in ("ERRORS", "EXCEPTIONS") for n in root.iter(tag)):
            return False
        if any((n.text or "").strip() == "0" for n in root.iter("STATUS")):
            return False
        return counter is None or int(root.findtext(".//" + counter, "0")) == 1
    except (ParseError, DefusedXmlException, ValueError, TypeError):
        # Malformed responses must never mark a voucher as synced.
        return False


def envelope(company, voucher):
    return f'''<ENVELOPE><HEADER><VERSION>1</VERSION><TALLYREQUEST>Import</TALLYREQUEST>
<TYPE>Data</TYPE><ID>Vouchers</ID></HEADER><BODY><DESC><STATICVARIABLES>
<SVCURRENTCOMPANY>{xml_escape(company)}</SVCURRENTCOMPANY>
</STATICVARIABLES></DESC><DATA><TALLYMESSAGE xmlns:UDF="TallyUDF">
{voucher}</TALLYMESSAGE></DATA></BODY></ENVELOPE>'''


def create_tally_payment_entry(payment_entry_name):
    doc = get_payment_entry(payment_entry_name)
    if doc.get("custom_tally_voucher_id"):
        return failure(f"Payment Entry {doc.name} is already synced to Tally.",
                       tally_voucher_id=doc.custom_tally_voucher_id)
    if doc.docstatus != 1:
        return failure("Only submitted Payment Entries can be synced to Tally.")
    voucher_type = VOUCHER_TYPES.get(doc.payment_type)
    if not voucher_type:
        return failure(f"Unsupported Payment Type: {doc.payment_type}")
    settings = get_settings(doc)
    if not settings.tally_company:
        return failure("Tally Company is not configured.")

    # GL rows include deductions, taxes and exchange differences. Reconstructing
    # a two-line voucher from paid_amount would silently omit those postings.
    rows = frappe.get_all("GL Entry", filters={"voucher_type": "Payment Entry",
        "voucher_no": doc.name, "company": doc.company, "is_cancelled": 0},
        fields=["account", "party_type", "party", "debit", "credit"], order_by="name")
    amounts = defaultdict(Decimal)
    for row in rows:
        if not row.account:
            return failure("Payment Entry has a posting without an account.")
        if row.party_type and row.party_type not in ("Customer", "Supplier"):
            return failure(f"Payment Entry party type {row.party_type} is not supported by Tally sync.")
        if row.party_type and not row.party:
            return failure("Payment Entry party is missing.")
        amounts[(row.account, row.party_type or "", row.party or "")] += (
            Decimal(str(row.credit or 0)) - Decimal(str(row.debit or 0)))
    amounts = {key: amount.quantize(Decimal("0.01")) for key, amount in amounts.items() if amount}
    if not amounts or sum(amounts.values()) != 0:
        return failure("Payment Entry has no balanced posted GL entries; Tally sync was skipped.")

    ledgers = []
    party_ledger = ""
    for (account, party_type, party), amount in amounts.items():
        if party_type == "Customer":
            result = create_tally_customer_ledger(party)
        elif party_type == "Supplier":
            result = create_tally_supplier_ledger(party)
        else:
            result = create_tally_account_ledger(account)
        if not response_ok(result):
            return failure(result.get("message") or result.get("response") or f"Failed to sync ledger {account}.")
        ledger = result.get("ledger_name")
        if not ledger:
            return failure(f"Tally ledger name is missing for {account}.")
        if party_type:
            party_ledger = ledger
        ledgers.append(f'''<ALLLEDGERENTRIES.LIST><LEDGERNAME>{xml_escape(ledger)}</LEDGERNAME>
<ISDEEMEDPOSITIVE>{'Yes' if amount < 0 else 'No'}</ISDEEMEDPOSITIVE>
<ISPARTYLEDGER>{'Yes' if party_type else 'No'}</ISPARTYLEDGER>
<AMOUNT>{amount:.2f}</AMOUNT></ALLLEDGERENTRIES.LIST>''')
    posting_date = get_payment_date(doc)
    voucher = f'''<VOUCHER REMOTEID={quoteattr('ERPNext-Payment-' + doc.name)}
VCHTYPE={quoteattr(voucher_type)} ACTION="Create" OBJVIEW="Accounting Voucher View">
<DATE>{posting_date}</DATE><EFFECTIVEDATE>{posting_date}</EFFECTIVEDATE>
<VOUCHERNUMBER>{xml_escape(doc.name)}</VOUCHERNUMBER>
<VOUCHERTYPENAME>{voucher_type}</VOUCHERTYPENAME>
<PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
<PARTYLEDGERNAME>{xml_escape(party_ledger)}</PARTYLEDGERNAME>
<NARRATION>{xml_escape(doc.get('remarks') or doc.name)}</NARRATION>
{''.join(ledgers)}</VOUCHER>'''
    xml = envelope(settings.tally_company, voucher)
    result = send_to_tally(xml)
    success = response_ok(result, "CREATED")
    voucher_id = None
    if success:
        voucher_id = fromstring(result["response"], forbid_dtd=True).findtext(".//LASTVCHID")
        success = bool(voucher_id and voucher_id.strip().isdigit() and int(voucher_id) > 0)
    if success:
        frappe.db.set_value("Payment Entry", doc.name, {
            "custom_tally_voucher_id": voucher_id.strip(),
            "custom_tally_voucher_date": doc.posting_date,
        })
    response = result.get("response", "")
    if response_ok(result, "CREATED") and not success:
        response += "\nTally created the voucher but returned no valid voucher ID. Check Tally before retrying."
    return {"success": success, "response": response, "xml": xml, "tally_voucher_id": voucher_id}


def change_payment_entry(doc, action):
    voucher_id = str(doc.get("custom_tally_voucher_id") or "").strip()
    if not voucher_id or voucher_id == "0":
        # Drafts and entries that never synced have nothing to remove in Tally.
        return {"success": True, "skipped": True, "response": "No synced Tally voucher.", "xml": ""}
    voucher_type = VOUCHER_TYPES.get(doc.payment_type)
    if not voucher_type:
        return failure(f"Unsupported Payment Type: {doc.payment_type}")
    voucher_date = doc.get("custom_tally_voucher_date")
    if not voucher_date:
        return failure("Tally Voucher Date is missing; reconcile the voucher before proceeding.")
    date_value = date.fromisoformat(str(voucher_date)[:10]).strftime("%d-%b-%Y")
    settings = get_settings(doc)
    if not settings.tally_company:
        return failure("Tally Company is not configured.")
    voucher = f'''<VOUCHER DATE={quoteattr(date_value)} TAGNAME="MASTER ID"
TAGVALUE={quoteattr(voucher_id)} VCHTYPE={quoteattr(voucher_type)} ACTION={quoteattr(action)}>
</VOUCHER>'''
    xml = envelope(settings.tally_company, voucher)
    result = send_to_tally(xml)
    return {"success": response_ok(result, {"Cancel": "CANCELLED", "Delete": "DELETED"}[action]),
            "response": result.get("response", ""), "xml": xml, "tally_voucher_id": voucher_id}


def cancel_tally_payment_entry(payment_entry_name):
    return change_payment_entry(get_payment_entry(payment_entry_name), "Cancel")


def delete_tally_payment_entry(doc):
    if not doc:
        return failure("Payment Entry document is missing.")
    return change_payment_entry(doc, "Delete")
