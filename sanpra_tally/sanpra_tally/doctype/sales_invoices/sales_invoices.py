import frappe
from frappe.model.document import Document

from sanpra_tally.sanpra_tally.tally_client import send_to_tally


class SalesInvoices(Document):

    def validate(self):
        total_qty = 0
        total_amount = 0

        for row in self.item_table:
            row.amount = (row.qty or 0) * (row.rate or 0)

            total_qty += row.qty or 0
            total_amount += row.amount or 0

        self.total_qty = total_qty
        self.total_amount = total_amount

    def on_submit(self):
        xml = self.make_tally_xml()

        result = send_to_tally(xml)

        if not result.get("success"):
            frappe.throw(
                "Tally Integration Failed: "
                + str(result.get("response"))
            )

        frappe.msgprint(
            "Sales Invoice sent to Tally successfully."
        )

    def make_tally_xml(self):

        customer = self.customer or "Customer"

        invoice_no = self.name

        posting_date = (
            self.posting_date.strftime("%Y%m%d")
            if self.posting_date
            else ""
        )

        total_amount = self.total_amount or 0

        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
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
                    VCHTYPE="Sales"
                    ACTION="Create"
                    OBJVIEW="Accounting Voucher View">

                    <DATE>{posting_date}</DATE>

                    <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>

                    <VOUCHERNUMBER>{invoice_no}</VOUCHERNUMBER>

                    <PARTYLEDGERNAME>{customer}</PARTYLEDGERNAME>

                    <PERSISTEDVIEW>
                        Accounting Voucher View
                    </PERSISTEDVIEW>

                    <ISINVOICE>Yes</ISINVOICE>

                    <LEDGERENTRIES.LIST>

                        <LEDGERNAME>{customer}</LEDGERNAME>

                        <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>

                        <AMOUNT>{total_amount}</AMOUNT>

                    </LEDGERENTRIES.LIST>

                    <LEDGERENTRIES.LIST>

                        <LEDGERNAME>Sales</LEDGERNAME>

                        <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>

                        <AMOUNT>-{total_amount}</AMOUNT>

                    </LEDGERENTRIES.LIST>

                </VOUCHER>

            </TALLYMESSAGE>

        </DATA>

    </BODY>

</ENVELOPE>"""

        return xml
