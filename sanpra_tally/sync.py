"""Queued voucher sync with per-document locking and conservative reconciliation."""
from contextvars import ContextVar
from hashlib import sha256
from datetime import date

import frappe
from frappe.utils import now_datetime
from sanpra_tally.subscription_client import get_settings, lookup_vouchers, run_conversion_job
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


def voucher_date(doc):
    return date.fromisoformat(str(doc.get('custom_tally_voucher_date') or doc.posting_date)[:10])


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
    expected_date = voucher_date(doc).strftime('%Y%m%d')
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


def serialise_doc(doc):
    data = doc.as_dict() if hasattr(doc, 'as_dict') else dict(doc)
    data.pop('_user_tags', None); data.pop('_comments', None); data.pop('_assign', None); data.pop('_liked_by', None)
    return frappe.parse_json(frappe.as_json(data))


def add_related(seen, rows, doctype, name):
    if not name or (doctype, name) in seen or not frappe.db.exists(doctype, name):
        return
    related = frappe.get_doc(doctype, name)
    seen.add((doctype, name))
    rows.append(serialise_doc(related))
    if doctype == 'Item':
        add_related(seen, rows, 'Item Group', related.get('item_group'))
        add_related(seen, rows, 'UOM', related.get('stock_uom'))


def collect_related(doc):
    seen, rows = set(), []
    if doc.get('customer'):
        add_related(seen, rows, 'Customer', doc.customer)
    if doc.get('supplier'):
        add_related(seen, rows, 'Supplier', doc.supplier)
    for item in doc.get('items') or []:
        add_related(seen, rows, 'Item', item.get('item_code'))
        for account in (item.get('income_account'), item.get('expense_account')):
            add_related(seen, rows, 'Account', account)
    for tax in doc.get('taxes') or []:
        add_related(seen, rows, 'Account', tax.get('account_head'))
    for row in doc.get('accounts') or []:
        add_related(seen, rows, 'Account', row.get('account'))
        if row.get('party_type') in ('Customer', 'Supplier'):
            add_related(seen, rows, row.get('party_type'), row.get('party'))
    for account in (doc.get('paid_from'), doc.get('paid_to')):
        add_related(seen, rows, 'Account', account)
    if doc.get('party_type') in ('Customer', 'Supplier'):
        add_related(seen, rows, doc.party_type, doc.get('party'))
    return rows


def snapshot_for(doc):
    return {'document': serialise_doc(doc), 'related': collect_related(doc)}


def request_id_for(doc, action, snapshot):
    import json
    payload = json.dumps([frappe.local.site, action, snapshot], sort_keys=True, default=str, separators=(',', ':'))
    return sha256(payload.encode()).hexdigest()


def apply_updates(doc, updates):
    allowed = {'custom_tally_voucher_id', 'custom_tally_voucher_date', 'custom_tally_cancel_voucher_id'}
    clean = {key: value for key, value in (updates or {}).items() if key in allowed}
    if clean:
        clean['custom_tally_delivery_uncertain'] = 0
        frappe.db.set_value(doc.doctype, doc.name, clean, update_modified=False)
        doc.update(clean)


def server_voucher_action(doc, action, settings):
    snapshot = snapshot_for(doc)
    result = run_conversion_job(settings, action, snapshot, request_id_for(doc, action, snapshot))
    if result.get('state') == 'complete':
        apply_updates(doc, result.get('updates'))
        return result.get('result') or {'success': False, 'response': 'Private conversion returned no result.'}
    return result


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


def create_voucher(doc, settings=None):
    return server_voucher_action(doc, 'create', settings or get_settings(doc))


def cancel_voucher(doc, settings):
    return server_voucher_action(doc, 'cancel', settings)


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
                doc.custom_tally_delivery_uncertain=0
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
                result=create_voucher(doc,settings)
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
