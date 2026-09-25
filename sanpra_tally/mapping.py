"""Resolve company-specific ERP-to-Tally names without changing ERP masters."""
import frappe
from sanpra_tally.subscription_client import get_settings


def ledger_name(reference_type, reference_name, default, company=None):
    company = company or get_settings().gateway_company
    if reference_type == 'Account':
        owner = frappe.db.get_value('Account', reference_name, 'company')
        if owner != company:
            frappe.throw('The account does not belong to the registered ERP company.')
    mapped = frappe.db.get_value('Tally Ledger Mapping', {
        'company': company, 'reference_type': reference_type,
        'reference_name': reference_name, 'enabled': 1}, 'tally_ledger')
    return mapped or default
