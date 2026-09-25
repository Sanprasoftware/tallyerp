"""Queued voucher sync with per-document locking and conservative reconciliation."""
from contextvars import ContextVar
from hashlib import sha256
from datetime import date

import frappe
from frappe.utils import now_datetime
from sanpra_tally.subscription_client import get_settings, lookup_vouchers
from sanpra_tally.xml_utils import parse_response

DOCTYPES = ('Sales Invoice','Purchase Invoice','Journal Entry','Payment Entry')
active_document = ContextVar('tally_active_document', default=None)


def remote_id(doc):
    # Retain the historic PE identity; new invoice identities include site/company.
    if doc.doctype == 'Payment Entry':
        return 'ERPNext-Payment-' + doc.name
    return 'ERPNext-' + sha256(f'{frappe.local.site}|{doc.company}|{doc.doctype}|{doc.name}'.encode()).hexdigest()


def voucher_type(doc):
    if doc.doctype == 'Payment Entry':
        return {'Pay':'Payment','Receive':'Receipt','Internal Transfer':'Contra'}[doc.payment_type]
    return {'Sales Invoice':'Sales','Purchase Invoice':'Purchase','Journal Entry':'Journal'}[doc.doctype]


def set_status(doc, status, message=''):
    frappe.db.set_value(doc.doctype,doc.name,{
        'custom_tally_sync_status':status,'custom_tally_sync_error':str(message)[:2000],
        'custom_tally_last_sync_attempt':now_datetime()},update_modified=False)


def lookup_result(doc, result):
    if not result.get('success'):
        raise ValueError(result.get('response') or 'Tally check failed.')
    root = parse_response(result.get('response'))
    # An HTTP 200 or an empty RESPONSE is not evidence that a voucher is absent.
    if root.tag != 'ENVELOPE' or root.find('.//COLLECTION') is None:
        raise ValueError('Tally did not return a voucher collection. No retry was sent.')
    expected_date = date.fromisoformat(str(doc.get('custom_tally_voucher_date') or doc.posting_date)[:10]).strftime('%Y%m%d')
    matches = []
    for node in root.iter('VOUCHER'):
        if (node.findtext('VOUCHERNUMBER') or '').strip() != doc.name:
            continue
        if (node.findtext('VOUCHERTYPENAME') or node.get('VCHTYPE') or '').strip() != voucher_type(doc):
            continue
        if (node.findtext('DATE') or '').strip() != expected_date:
            continue
        matches.append(node)
    if len(matches) > 1:
        raise ValueError('Multiple matching Tally vouchers exist. Reconcile them before retrying.')
    if not matches:
        return None
    node = matches[0]
    master = (node.findtext('MASTERID') or '').strip()
    identity = (node.get('REMOTEID') or node.findtext('REMOTEID') or '').strip()
    known = str(doc.get('custom_tally_voucher_id') or '')
    if not master.isdigit() or int(master) <= 0:
        raise ValueError('The matching voucher has no valid Tally ID.')
    if master != known and identity != remote_id(doc):
        raise ValueError('A matching voucher number exists without a verified ERP identity. Check it manually.')
    return {'id':master,'cancelled':(node.findtext('ISCANCELLED') or '').strip().lower() == 'yes'}


def enqueue_sync(doc, method=None, check_only=False):
    if doc.doctype not in DOCTYPES or doc.docstatus not in (1,2):
        return
    set_status(doc,'Queued')
    frappe.enqueue('sanpra_tally.sync.run_sync',queue='long',timeout=600,
        enqueue_after_commit=True,doctype=doc.doctype,name=doc.name,check_only=check_only)


def on_submit(doc, method=None):
    enqueue_sync(doc)


def on_cancel(doc, method=None):
    enqueue_sync(doc)


def on_trash(doc, method=None):
    # Keep the ERP identity available for reconciliation and prevent an async
    # cancel task from losing its source document.
    if doc.get('custom_tally_voucher_id') or doc.get('custom_tally_delivery_uncertain'):
        frappe.throw('This document has Tally history. Keep the cancelled ERP document for reconciliation.')
    if doc.get('custom_tally_sync_status') in ('Queued','Syncing'):
        frappe.throw('Wait for the Tally check to finish before deleting this document.')


@frappe.whitelist(methods=['POST'])
def check_and_retry(doctype, name, check_only=False):
    if doctype not in DOCTYPES:
        frappe.throw('Unsupported document type.')
    doc = frappe.get_doc(doctype,name)
    doc.check_permission('write')
    if not set(frappe.get_roles()).intersection({'System Manager','Accounts Manager','Accounts User'}):
        frappe.throw('An accounts role is required.',frappe.PermissionError)
    if doc.docstatus not in (1,2):
        frappe.throw('Submit this document before syncing to Tally.')
    get_settings(doc)
    enqueue_sync(doc,check_only=frappe.utils.cint(check_only))
    return {'status':'Queued'}


def create_voucher(doc):
    from sanpra_tally.sanpra_tally.tally.sales_invoice import send_sales_invoice_to_tally
    from sanpra_tally.sanpra_tally.tally.purchase_invoice import create_tally_purchase_invoice
    from sanpra_tally.sanpra_tally.tally.journal_entry import create_tally_journal_entry
    from sanpra_tally.sanpra_tally.tally.payment_entry import create_tally_payment_entry
    return dict(zip(DOCTYPES,(send_sales_invoice_to_tally,create_tally_purchase_invoice,
                             create_tally_journal_entry,create_tally_payment_entry)))[doc.doctype](doc.name)


def cancel_voucher(doc, settings):
    import xml.etree.ElementTree as ET
    from sanpra_tally.sanpra_tally.tally_client import send_to_tally
    root=ET.Element('ENVELOPE'); header=ET.SubElement(root,'HEADER')
    for k,v in [('VERSION','1'),('TALLYREQUEST','Import'),('TYPE','Data'),('ID','Vouchers')]:
        ET.SubElement(header,k).text=v
    body=ET.SubElement(root,'BODY'); desc=ET.SubElement(body,'DESC')
    ET.SubElement(ET.SubElement(desc,'STATICVARIABLES'),'SVCURRENTCOMPANY').text=settings.tally_company
    msg=ET.SubElement(ET.SubElement(body,'DATA'),'TALLYMESSAGE')
    ET.SubElement(msg,'VOUCHER',ACTION='Cancel',VCHTYPE=voucher_type(doc),TAGNAME='MASTER ID',
        TAGVALUE=str(doc.custom_tally_voucher_id),DATE=date.fromisoformat(str(doc.get('custom_tally_voucher_date') or doc.posting_date)[:10]).strftime('%d-%b-%Y'))
    return send_to_tally(ET.tostring(root,encoding='unicode'))


def run_sync(doctype, name, check_only=False):
    if doctype not in DOCTYPES:
        return
    key='tally-document:' + sha256(f'{frappe.local.site}|{doctype}|{name}'.encode()).hexdigest()
    with frappe.cache.lock(key,timeout=660,blocking_timeout=1):
        doc=frappe.get_doc(doctype,name)
        if doc.docstatus not in (1,2):
            return
        token=active_document.set(doc)
        try:
            settings=get_settings(doc)
            set_status(doc,'Syncing'); frappe.db.commit()
            found=lookup_result(doc,lookup_vouchers(settings,doc.get('custom_tally_voucher_date') or doc.posting_date))
            if found:
                frappe.db.set_value(doctype,name,{'custom_tally_voucher_id':found['id'],
                    'custom_tally_voucher_date':doc.get('custom_tally_voucher_date') or doc.posting_date,
                    'custom_tally_delivery_uncertain':0},update_modified=False)
                doc.custom_tally_voucher_id=found['id']
                if found['cancelled']:
                    set_status(doc,'Cancelled' if doc.docstatus == 2 else 'Needs Review',
                               '' if doc.docstatus == 2 else 'Tally voucher is cancelled but ERP document is submitted.')
                    return
                if doc.docstatus == 1 or check_only:
                    set_status(doc,'Synced' if doc.docstatus == 1 else 'Needs Review',
                               '' if doc.docstatus == 1 else 'ERP is cancelled; Tally voucher still needs cancellation.')
                    return
                result=cancel_voucher(doc,settings)
            else:
                if doc.get('custom_tally_voucher_id') or doc.get('custom_tally_delivery_uncertain'):
                    set_status(doc,'Needs Review','No voucher found, but an earlier delivery or Tally ID exists. Automatic resend is blocked.')
                    return
                if doc.docstatus == 2:
                    set_status(doc,'Cancelled','No Tally voucher exists for this cancelled document.')
                    return
                if check_only:
                    set_status(doc,'Pending','No matching Tally voucher found.')
                    return
                result=create_voucher(doc)
            if result.get('success'):
                set_status(doc,'Synced' if doc.docstatus == 1 else 'Cancelled')
            else:
                uncertain=frappe.db.get_value(doctype,name,'custom_tally_delivery_uncertain')
                set_status(doc,'Needs Review' if uncertain else 'Failed',result.get('response','Sync failed.'))
        except Exception as exc:
            set_status(doc,'Needs Review',str(exc))
        finally:
            active_document.reset(token)
            frappe.db.commit()
            frappe.publish_realtime('tally_sync_updated',{'doctype':doctype,'name':name},
                                    doctype=doctype,docname=name,after_commit=True)
