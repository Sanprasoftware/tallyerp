"""Private gateway transport with strict import confirmation and sync tracking."""
import xml.etree.ElementTree as ET
from decimal import Decimal
from defusedxml.ElementTree import fromstring
from sanpra_tally.subscription_client import get_settings, send_via_gateway
from sanpra_tally.xml_utils import checked_result


def get_tally_settings():
    return get_settings()


def send_to_tally(xml_data):
    import frappe
    from sanpra_tally.sync import active_document, remote_id
    doc = active_document.get()
    settings = get_settings(doc) if doc else get_tally_settings()
    try:
        root = fromstring(xml_data,forbid_dtd=True)
        body = root.find('BODY')
        if body is None:
            raise ValueError('Missing Tally BODY.')
        companies = root.findall('.//SVCURRENTCOMPANY')
        if not companies:
            desc = body.find('DESC')
            if desc is None:
                desc = ET.SubElement(body,'DESC')
            static = desc.find('STATICVARIABLES')
            if static is None:
                static = ET.SubElement(desc,'STATICVARIABLES')
            ET.SubElement(static,'SVCURRENTCOMPANY').text = settings.tally_company
        elif any((n.text or '') != settings.tally_company for n in companies):
            raise ValueError('Voucher company does not match the registered company.')
        vouchers=root.findall('.//VOUCHER')
        counter=None
        if vouchers:
            if len(vouchers) != 1:
                raise ValueError('Only one voucher per sync request is supported.')
            voucher=vouchers[0]
            action=voucher.get('ACTION','Create')
            counter={'Create':'CREATED','Cancel':'CANCELLED','Delete':'DELETED','Alter':'ALTERED'}[action]
            if action == 'Create':
                entries=[n for n in voucher if n.tag in ('ALLLEDGERENTRIES.LIST','LEDGERENTRIES.LIST','ALLINVENTORYENTRIES.LIST')]
                amounts=[Decimal(n.findtext('AMOUNT','0')) for n in entries]
                if not amounts or abs(sum(amounts)) > Decimal('0.005'):
                    raise ValueError('Tally voucher is not balanced. Check taxes, discounts and ledger mapping.')
                if doc:
                    voucher.set('REMOTEID',remote_id(doc))
        xml_data=ET.tostring(root,encoding='unicode')
    except Exception as exc:
        return {'success':False,'response':str(exc)}
    if vouchers and doc:
        # Persist before the external write. A worker crash leaves a review marker.
        frappe.db.set_value(doc.doctype,doc.name,'custom_tally_delivery_uncertain',1,update_modified=False)
        frappe.db.commit()
    result=checked_result(send_via_gateway(settings,xml_data),counter)
    if result.get('success') and counter == 'CREATED':
        identity=fromstring(result['response'],forbid_dtd=True).findtext('.//LASTVCHID','')
        if not identity.strip().isdigit() or int(identity) <= 0:
            result={'success':False,'uncertain':True,'response':'Tally created the voucher without a valid ID. Use Check Tally to reconcile.'}
    if vouchers and doc and result.get('success'):
        updates={'custom_tally_delivery_uncertain':0}
        if counter == 'CREATED':
            updates.update(custom_tally_voucher_id=identity.strip(),custom_tally_voucher_date=doc.posting_date)
        frappe.db.set_value(doc.doctype,doc.name,updates,update_modified=False)
    return result
