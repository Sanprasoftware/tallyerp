import unittest
from unittest.mock import MagicMock, patch
from xml.etree.ElementTree import fromstring

from frappe import _dict
from sanpra_tally.sanpra_tally.tally import payment_entry as pe


def response(counter='CREATED', **extra):
    return dict(success=True, response=f'<RESPONSE><{counter}>1</{counter}><ERRORS>0</ERRORS>'
                '<EXCEPTIONS>0</EXCEPTIONS><LASTVCHID>123</LASTVCHID></RESPONSE>', **extra)


class PaymentTests(unittest.TestCase):
    def setUp(self):
        self.doc = _dict(name='PAY-001', doctype='Payment Entry', docstatus=1,
                         company='ERP Co', payment_type='Pay', posting_date='2026-09-24',
                         remarks='A & B <payment>')
        self.rows = [_dict(account='Creditors', party_type='Supplier', party='SUP-1', debit=100, credit=0),
                     _dict(account='Bank', debit=0, credit=100)]
        for name in ('frappe', 'get_settings', 'send_to_tally', 'create_tally_account_ledger',
                     'create_tally_supplier_ledger', 'create_tally_customer_ledger'):
            patcher = patch.object(pe, name)
            setattr(self, name, patcher.start())
            self.addCleanup(patcher.stop)
        self.frappe.get_doc.return_value = self.doc
        self.frappe.get_all.side_effect = lambda *a, **kw: self.rows
        self.get_settings.return_value = _dict(tally_company='Configured & Co')
        self.send_to_tally.return_value = response()
        self.create_tally_account_ledger.side_effect = lambda name: response(ledger_name=name)
        self.create_tally_supplier_ledger.return_value = response(ledger_name='Supplier & Co')
        self.create_tally_customer_ledger.return_value = response(ledger_name='Customer & Co')

    def create(self):
        return pe.create_tally_payment_entry(self.doc.name)

    def test_payment_uses_posted_amounts_party_and_configured_company(self):
        self.rows[0].debit = 95
        self.rows.append(_dict(account='Charges', debit=5, credit=0))
        result = self.create()
        self.assertTrue(result['success'])
        root = fromstring(result['xml'])
        self.assertEqual(root.findtext('.//SVCURRENTCOMPANY'), 'Configured & Co')
        self.assertEqual(root.findtext('.//VOUCHERTYPENAME'), 'Payment')
        self.assertEqual(root.findtext('.//PARTYLEDGERNAME'), 'Supplier & Co')
        amounts = {n.findtext('LEDGERNAME'): n.findtext('AMOUNT') for n in root.iter('ALLLEDGERENTRIES.LIST')}
        self.assertEqual(amounts, {'Supplier & Co': '-95.00', 'Bank': '100.00', 'Charges': '-5.00'})
        self.frappe.db.set_value.assert_called_once_with('Payment Entry', 'PAY-001',
            {'custom_tally_voucher_id': '123', 'custom_tally_voucher_date': '2026-09-24'})
        self.frappe.db.commit.assert_not_called()
        self.get_settings.assert_called_once_with(self.doc)

    def test_receipt_credits_customer(self):
        self.doc.payment_type = 'Receive'
        self.rows = [_dict(account='Debtors', party_type='Customer', party='CUS-1', credit=100),
                     _dict(account='Bank', debit=100)]
        root = fromstring(self.create()['xml'])
        self.assertEqual(root.findtext('.//VOUCHERTYPENAME'), 'Receipt')
        party = next(n for n in root.iter('ALLLEDGERENTRIES.LIST') if n.findtext('ISPARTYLEDGER') == 'Yes')
        self.assertEqual(party.findtext('AMOUNT'), '100.00')
        self.assertEqual(party.findtext('LEDGERNAME'), 'Customer & Co')

    def test_internal_transfer_is_contra(self):
        self.doc.payment_type = 'Internal Transfer'
        self.rows = [_dict(account='Cash', credit=100), _dict(account='Bank', debit=100)]
        root = fromstring(self.create()['xml'])
        self.assertEqual(root.findtext('.//VOUCHERTYPENAME'), 'Contra')
        self.create_tally_supplier_ledger.assert_not_called()
        self.create_tally_customer_ledger.assert_not_called()

    def test_duplicate_and_draft_do_not_send(self):
        self.doc.custom_tally_voucher_id = '123'
        self.assertFalse(self.create()['success'])
        self.doc.custom_tally_voucher_id = None
        self.doc.docstatus = 0
        self.assertFalse(self.create()['success'])
        self.send_to_tally.assert_not_called()
        self.frappe.get_all.assert_not_called()

    def test_unbalanced_or_missing_gl_never_creates_masters(self):
        self.rows[0].debit = 90
        self.assertFalse(self.create()['success'])
        self.rows = []
        self.assertFalse(self.create()['success'])
        self.create_tally_supplier_ledger.assert_not_called()
        self.send_to_tally.assert_not_called()

    def test_failed_master_stops_voucher(self):
        self.create_tally_supplier_ledger.return_value = dict(success=True,
            response='<RESPONSE><LINEERROR>Missing ledger</LINEERROR></RESPONSE>')
        self.assertFalse(self.create()['success'])
        self.send_to_tally.assert_not_called()

    def test_invalid_results_never_save_id(self):
        for result in [dict(success=False, response=response()['response']),
                       dict(success=True, response='<RESPONSE><CREATED>1</CREATED><ERRORS>1</ERRORS></RESPONSE>'),
                       dict(success=True, response='<RESPONSE><CREATED>1</CREATED></RESPONSE>'),
                       dict(success=True, response='not XML')]:
            with self.subTest(result=result):
                self.send_to_tally.return_value = result
                self.assertFalse(self.create()['success'])
        self.frappe.db.set_value.assert_not_called()

    def test_cancel_and_delete_target_saved_id_date_and_company(self):
        self.doc.custom_tally_voucher_id = '123'
        self.doc.custom_tally_voucher_date = '2026-08-01'
        for action, fn, counter in [('Cancel', lambda: pe.cancel_tally_payment_entry(self.doc.name), 'CANCELLED'),
                                    ('Delete', lambda: pe.delete_tally_payment_entry(self.doc), 'DELETED')]:
            self.send_to_tally.return_value = response(counter)
            result = fn()
            self.assertTrue(result['success'])
            root = fromstring(result['xml'])
            voucher = root.find('.//VOUCHER')
            self.assertEqual(voucher.attrib['ACTION'], action)
            self.assertEqual(voucher.attrib['TAGVALUE'], '123')
            self.assertEqual(voucher.attrib['DATE'], '01-Aug-2026')
            self.assertEqual(root.findtext('.//SVCURRENTCOMPANY'), 'Configured & Co')

    def test_unsynced_delete_skips_tally(self):
        self.assertTrue(pe.delete_tally_payment_entry(self.doc)['skipped'])
        self.send_to_tally.assert_not_called()

    def test_missing_saved_date_blocks_mutation(self):
        self.doc.custom_tally_voucher_id = '123'
        self.assertFalse(pe.cancel_tally_payment_entry(self.doc.name)['success'])
        self.send_to_tally.assert_not_called()


if __name__ == '__main__':
    unittest.main()
