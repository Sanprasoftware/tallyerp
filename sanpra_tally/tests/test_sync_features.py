import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch, MagicMock
from xml.etree.ElementTree import fromstring

from frappe import _dict
from sanpra_tally import sync, mapping
from sanpra_tally.sanpra_tally import tally_client


def document(**values):
    doc = _dict(doctype='Payment Entry',name='PAY-1',company='ERP',posting_date='2026-09-24',
                payment_type='Pay',docstatus=1,custom_tally_delivery_uncertain=0)
    doc.update(values)
    return doc


def collection(doc, master='123', remote=None, cancelled=False):
    rid = remote if remote is not None else 'ERPNext-Payment-PAY-1'
    return '<ENVELOPE><BODY><DATA><COLLECTION><VOUCHER REMOTEID="'+rid+'">' + \
        f'<MASTERID>{master}</MASTERID><VOUCHERNUMBER>{doc.name}</VOUCHERNUMBER>' + \
        '<VOUCHERTYPENAME>Payment</VOUCHERTYPENAME><DATE>20260924</DATE>' + \
        f'<ISCANCELLED>{"Yes" if cancelled else "No"}</ISCANCELLED></VOUCHER></COLLECTION></DATA></BODY></ENVELOPE>'

EMPTY = '<ENVELOPE><BODY><DATA><COLLECTION/></DATA></BODY></ENVELOPE>'


class LookupTests(unittest.TestCase):
    def test_verified_identity_recovers_id(self):
        doc=document()
        result=sync.lookup_result(doc,{'success':True,'response':collection(doc)})
        self.assertEqual(result,{'id':'123','cancelled':False})

    def test_existing_id_accepts_legacy_voucher(self):
        doc=document(custom_tally_voucher_id='123')
        self.assertEqual(sync.lookup_result(doc,{'success':True,'response':collection(doc,remote='')})['id'],'123')

    def test_unknown_identity_is_not_adopted(self):
        doc=document()
        with self.assertRaisesRegex(ValueError,'identity'):
            sync.lookup_result(doc,{'success':True,'response':collection(doc,remote='Other')})

    def test_invalid_and_failed_responses_never_prove_absence(self):
        for xml in ('<RESPONSE/>','not xml','<ENVELOPE><STATUS>0</STATUS><COLLECTION/></ENVELOPE>'):
            with self.subTest(xml=xml), self.assertRaises(Exception):
                sync.lookup_result(document(),{'success':True,'response':xml})
        with self.assertRaises(ValueError):
            sync.lookup_result(document(),{'success':False,'response':EMPTY})

    def test_empty_collection_proves_absence(self):
        self.assertIsNone(sync.lookup_result(document(),{'success':True,'response':EMPTY}))

    def test_duplicate_matches_require_review(self):
        doc=document(); xml=collection(doc)
        voucher=xml[xml.index('<VOUCHER '):xml.index('</VOUCHER>')+10]
        xml=xml.replace('</COLLECTION>',voucher+'</COLLECTION>')
        with self.assertRaisesRegex(ValueError,'Multiple'):
            sync.lookup_result(doc,{'success':True,'response':xml})

    def test_unrelated_type_or_date_is_not_matched(self):
        doc=document()
        for xml in (collection(doc).replace('20260924','20260923'),collection(doc).replace('Payment</','Receipt</')):
            self.assertIsNone(sync.lookup_result(doc,{'success':True,'response':xml}))


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.doc=document()
        for name in ('frappe','get_settings','lookup_vouchers','create_voucher','cancel_voucher','set_status'):
            p=patch.object(sync,name); setattr(self,name,p.start());self.addCleanup(p.stop)
        self.frappe.local.site='erp.test'
        self.frappe.get_doc.return_value=self.doc
        self.frappe.db.get_value.return_value=0
        self.lookup_vouchers.return_value={'success':True,'response':EMPTY}
        self.create_voucher.return_value={'success':True}
        self.cancel_voucher.return_value={'success':True}

    def run_job(self,check_only=False):
        sync.run_sync('Payment Entry','PAY-1',check_only)

    def test_absent_voucher_is_created_once_after_lookup(self):
        self.run_job()
        self.lookup_vouchers.assert_called_once()
        self.create_voucher.assert_called_once_with(self.doc)
        self.assertEqual(self.set_status.call_args.args[1],'Synced')

    def test_found_voucher_is_reconciled_without_recreate(self):
        self.lookup_vouchers.return_value={'success':True,'response':collection(self.doc)}
        self.run_job()
        self.create_voucher.assert_not_called()
        self.assertEqual(self.set_status.call_args.args[1],'Synced')

    def test_uncertain_delivery_blocks_automatic_resend_even_if_absent(self):
        self.doc.custom_tally_delivery_uncertain=1
        self.run_job()
        self.create_voucher.assert_not_called()
        self.assertEqual(self.set_status.call_args.args[1],'Needs Review')

    def test_check_only_never_writes_to_tally(self):
        self.run_job(check_only=True)
        self.create_voucher.assert_not_called();self.cancel_voucher.assert_not_called()
        self.assertEqual(self.set_status.call_args.args[1],'Pending')

    def test_failed_lookup_blocks_creation(self):
        self.lookup_vouchers.return_value={'success':False,'response':'Offline'}
        self.run_job()
        self.create_voucher.assert_not_called()
        self.assertEqual(self.set_status.call_args.args[1],'Needs Review')

    def test_cancelled_erp_cancels_verified_active_voucher(self):
        self.doc.docstatus=2
        self.lookup_vouchers.return_value={'success':True,'response':collection(self.doc)}
        self.run_job()
        self.cancel_voucher.assert_called_once()
        self.assertEqual(self.set_status.call_args.args[1],'Cancelled')

    def test_tally_cancelled_but_erp_active_requires_review(self):
        self.lookup_vouchers.return_value={'success':True,'response':collection(self.doc,cancelled=True)}
        self.run_job()
        self.create_voucher.assert_not_called()
        self.assertEqual(self.set_status.call_args.args[1],'Needs Review')

    def test_draft_does_not_sync(self):
        self.doc.docstatus=0
        self.run_job()
        self.lookup_vouchers.assert_not_called()

    def test_write_permission_required_before_queue(self):
        self.doc.check_permission=MagicMock(side_effect=PermissionError('denied'))
        with self.assertRaises(PermissionError):
            sync.check_and_retry('Payment Entry','PAY-1')
        self.frappe.enqueue.assert_not_called()

    def test_enqueue_is_after_commit(self):
        sync.enqueue_sync(self.doc)
        self.assertTrue(self.frappe.enqueue.call_args.kwargs['enqueue_after_commit'])


class MappingTests(unittest.TestCase):
    @patch.object(mapping,'frappe')
    def test_mapping_scoped_to_company_and_record(self,f):
        f.db.get_value.side_effect=['ERP','Mapped Bank']
        self.assertEqual(mapping.ledger_name('Account','Bank','Bank','ERP'),'Mapped Bank')
        filters=f.db.get_value.call_args.args[1]
        self.assertEqual(filters,{'company':'ERP','reference_type':'Account','reference_name':'Bank','enabled':1})

    @patch.object(mapping,'frappe')
    def test_missing_mapping_preserves_default(self,f):
        f.db.get_value.return_value=None
        self.assertEqual(mapping.ledger_name('Customer','CUS','Customer Name','ERP'),'Customer Name')

    @patch.object(mapping,'frappe')
    def test_cross_company_account_rejected(self,f):
        f.db.get_value.return_value='Other'
        f.throw.side_effect=ValueError('wrong company')
        with self.assertRaises(ValueError):mapping.ledger_name('Account','Bank','Bank','ERP')


class TransportTests(unittest.TestCase):
    def setUp(self):
        p=patch.object(tally_client,'get_tally_settings',return_value=_dict(tally_company='Demo'))
        p.start();self.addCleanup(p.stop)
        p=patch.object(tally_client,'send_via_gateway')
        self.gateway=p.start();self.addCleanup(p.stop)
        self.gateway.return_value={'success':True,'response':'<RESPONSE><CREATED>1</CREATED><LASTVCHID>123</LASTVCHID></RESPONSE>'}
        self.xml='<ENVELOPE><BODY><DESC/><DATA><TALLYMESSAGE><VOUCHER ACTION="Create"><ALLLEDGERENTRIES.LIST><AMOUNT>-10</AMOUNT></ALLLEDGERENTRIES.LIST><ALLLEDGERENTRIES.LIST><AMOUNT>10</AMOUNT></ALLLEDGERENTRIES.LIST></VOUCHER></TALLYMESSAGE></DATA></BODY></ENVELOPE>'

    def test_missing_company_is_injected(self):
        self.assertTrue(tally_client.send_to_tally(self.xml)['success'])
        self.assertEqual(fromstring(self.gateway.call_args.args[1]).findtext('.//SVCURRENTCOMPANY'),'Demo')

    def test_unbalanced_voucher_never_reaches_gateway(self):
        self.assertFalse(tally_client.send_to_tally(self.xml.replace('>10<','>9<'))['success'])
        self.gateway.assert_not_called()

    def test_tally_error_never_reports_success(self):
        self.gateway.return_value={'success':True,'response':'<RESPONSE><CREATED>0</CREATED><ERRORS>2</ERRORS><LASTVCHID>999</LASTVCHID></RESPONSE>'}
        self.assertFalse(tally_client.send_to_tally(self.xml)['success'])

    def test_missing_id_requires_review(self):
        self.gateway.return_value={'success':True,'response':'<RESPONSE><CREATED>1</CREATED></RESPONSE>'}
        result=tally_client.send_to_tally(self.xml)
        self.assertFalse(result['success']);self.assertTrue(result['uncertain'])


class InvoiceMappingTests(unittest.TestCase):
    def test_invoice_accounts_are_mapped_and_xml_escaped(self):
        from contextlib import ExitStack, redirect_stdout
        import io
        from sanpra_tally.sanpra_tally.tally import sales_invoice, purchase_invoice
        for module,method,doctype in [(sales_invoice,'send_sales_invoice_to_tally','Sales Invoice'),
                                      (purchase_invoice,'create_tally_purchase_invoice','Purchase Invoice')]:
            item=_dict(item_code='ITEM',qty=1,rate=100,amount=100,uom='Nos',stock_uom='Nos',income_account='Sales ERP',expense_account='Purchase ERP')
            doc=SimpleNamespace(name='INV-1',doctype=doctype,company='ERP',customer='CUS',supplier='SUP',
                custom_tally_voucher_id=None,posting_date=date(2026,9,24),grand_total=118,items=[item],
                taxes=[_dict(account_head='GST ERP',tax_amount=18,add_deduct_tax='Add')],get=lambda key:None)
            with self.subTest(doctype=doctype), ExitStack() as stack:
                f=stack.enter_context(patch.object(module,'frappe'))
                f.get_doc.side_effect=lambda dt,name: doc if dt==doctype else SimpleNamespace(item_name='Item & Special',stock_uom='Nos')
                stack.enter_context(patch.object(module,'get_settings'))
                stack.enter_context(patch.object(module,'get_tally_settings',return_value=_dict(tally_company='Company & Co')))
                stack.enter_context(patch.object(module,'create_tally_stock_item',return_value={'success':True}))
                stack.enter_context(patch.object(module,'create_tally_account_ledger',side_effect=lambda account: {'success':True,'ledger_name':'Mapped & '+account}))
                party_helper='create_tally_customer_ledger' if doctype=='Sales Invoice' else 'create_tally_supplier_ledger'
                stack.enter_context(patch.object(module,party_helper,return_value={'success':True,'ledger_name':'Party & Co'}))
                if doctype=='Purchase Invoice':
                    stack.enter_context(patch.object(module,'create_tally_tax_ledger',return_value={'success':True,'ledger_name':'Mapped & GST ERP'}))
                send=stack.enter_context(patch.object(module,'send_to_tally',return_value={'success':True,'response':'<RESPONSE><CREATED>1</CREATED><ERRORS>0</ERRORS><LASTVCHID>123</LASTVCHID></RESPONSE>'}))
                with redirect_stdout(io.StringIO()): getattr(module,method)(doc.name)
                root=fromstring(send.call_args.args[0])
                self.assertEqual(root.findtext('.//SVCURRENTCOMPANY'),'Company & Co')
                names=[node.text for node in root.iter('LEDGERNAME')]
                self.assertIn('Party & Co',names)
                self.assertIn('Mapped & GST ERP',names)
                self.assertIn('Mapped & '+('Sales ERP' if doctype=='Sales Invoice' else 'Purchase ERP'),names)
                from decimal import Decimal
                voucher=root.find('.//VOUCHER')
                total=sum(Decimal(n.findtext('AMOUNT','0')) for n in voucher if n.tag in ('LEDGERENTRIES.LIST','ALLINVENTORYENTRIES.LIST'))
                self.assertEqual(total,0)
