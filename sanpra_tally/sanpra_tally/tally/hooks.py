import frappe

from sanpra_tally.sanpra_tally.tally.journal_entry import (
    create_tally_journal_entry,
    cancel_tally_journal_entry,
    delete_tally_journal_entry,
)

from sanpra_tally.sanpra_tally.tally.sales_invoice import (
    send_sales_invoice_to_tally,
    cancel_tally_sales_invoice,
    delete_tally_sales_invoice,
)


# ============================================================
# JOURNAL ENTRY
# ============================================================

def on_journal_entry_submit(doc, method=None):

    try:

        result = create_tally_journal_entry(
            doc.name
        )

        response = result.get(
            "response",
            ""
        )

        if "<CREATED>1</CREATED>" not in response:

            frappe.log_error(
                title=f"Tally Journal Entry Failed: {doc.name}",
                message=response
            )

    except Exception:

        frappe.log_error(
            title=f"Tally Journal Entry Exception: {doc.name}",
            message=frappe.get_traceback()
        )


def on_journal_entry_cancel(doc, method=None):

    try:

        result = cancel_tally_journal_entry(
            doc.name
        )

        response = result.get(
            "response",
            ""
        )

        if "<CANCELLED>1</CANCELLED>" not in response:

            frappe.log_error(
                title=f"Tally Journal Cancel Failed: {doc.name}",
                message=response
            )

    except Exception:

        frappe.log_error(
            title=f"Tally Journal Cancel Exception: {doc.name}",
            message=frappe.get_traceback()
        )


def on_journal_entry_trash(doc, method=None):

    try:

        result = delete_tally_journal_entry(
            doc
        )

        if not result.get("success"):

            frappe.throw(
                f"Unable to delete Journal Entry "
                f"{doc.name} from Tally."
            )

    except Exception:

        frappe.log_error(
            title=f"Tally Journal Delete Exception: {doc.name}",
            message=frappe.get_traceback()
        )

        raise


# ============================================================
# SALES INVOICE
# ============================================================

def on_sales_invoice_submit(doc, method=None):

    try:

        result = send_sales_invoice_to_tally(
            doc.name
        )

        response = result.get(
            "response",
            ""
        )

        if "<CREATED>1</CREATED>" not in response:

            frappe.log_error(
                title=f"Tally Sales Invoice Failed: {doc.name}",
                message=response
            )

    except Exception:

        frappe.log_error(
            title=f"Tally Sales Invoice Exception: {doc.name}",
            message=frappe.get_traceback()
        )


def on_sales_invoice_cancel(doc, method=None):

    try:

        result = cancel_tally_sales_invoice(
            doc.name
        )

        response = result.get(
            "response",
            ""
        )

        if "<CANCELLED>1</CANCELLED>" not in response:

            frappe.log_error(
                title=f"Tally Sales Invoice Cancel Failed: {doc.name}",
                message=response
            )

    except Exception:

        frappe.log_error(
            title=f"Tally Sales Invoice Cancel Exception: {doc.name}",
            message=frappe.get_traceback()
        )
        
        
        
def on_sales_invoice_trash(doc, method=None):

    try:

        result = delete_tally_sales_invoice(
            doc
        )

        if not result.get("success"):

            frappe.throw(
                f"Unable to delete Sales Invoice "
                f"{doc.name} from Tally."
            )

    except Exception:

        frappe.log_error(
            title=f"Tally Sales Invoice Delete Exception: {doc.name}",
            message=frappe.get_traceback()
        )

        raise


# ============================================================
# PURCHASE INVOICE
# ============================================================

def on_purchase_invoice_submit(doc, method=None):

    from sanpra_tally.sanpra_tally.tally.purchase_invoice import (
        create_tally_purchase_invoice
    )

    try:

        result = create_tally_purchase_invoice(
            doc.name
        )

        if not result.get("success"):

            frappe.log_error(
                title="Tally Purchase Invoice Error",
                message=str(result)
            )

    except Exception:

        frappe.log_error(
            title="Tally Purchase Invoice Submit Error",
            message=frappe.get_traceback()
        )


def on_purchase_invoice_cancel(doc, method=None):

    from sanpra_tally.sanpra_tally.tally.purchase_invoice import (
        cancel_tally_purchase_invoice
    )

    try:

        result = cancel_tally_purchase_invoice(
            doc.name
        )

        if not result.get("success"):

            frappe.log_error(
                title="Tally Purchase Invoice Cancel Error",
                message=str(result)
            )

    except Exception:

        frappe.log_error(
            title="Tally Purchase Invoice Cancel Exception",
            message=frappe.get_traceback()
        )
        
        
def on_purchase_invoice_trash(doc, method=None):

    from sanpra_tally.sanpra_tally.tally.purchase_invoice import (
            delete_tally_purchase_invoice
    )

    try:

        result = delete_tally_purchase_invoice(
            doc
        )

        if not result.get("success"):

            frappe.throw(
                f"Unable to delete Purchase Invoice "
                f"{doc.name} from Tally."
            )

    except Exception:

        frappe.log_error(
            title=f"Tally Purchase Invoice Delete Exception: {doc.name}",
            message=frappe.get_traceback()
        )

        raise
    


from sanpra_tally.sanpra_tally.tally.payment_entry import (
    create_tally_payment_entry,
    cancel_tally_payment_entry,
    delete_tally_payment_entry,
)


# ============================================================
# PAYMENT ENTRY - SUBMIT
# ============================================================

def on_payment_entry_submit(doc, method=None):

    try:

        result = create_tally_payment_entry(doc.name)

        if not result.get("success"):

            frappe.log_error(
                title="Tally Payment Entry Create Failed",
                message=(
                    f"Payment Entry: {doc.name}\n\n"
                    f"Response:\n{result.get('response', '')}\n\n"
                    f"XML:\n{result.get('xml', '')}"
                ),
            )

    except Exception:

        frappe.log_error(
            title="Tally Payment Entry Submit Error",
            message=frappe.get_traceback(),
        )


# ============================================================
# PAYMENT ENTRY - CANCEL
# ============================================================

def on_payment_entry_cancel(doc, method=None):

    try:

        result = cancel_tally_payment_entry(doc.name)

        if not result.get("success"):

            frappe.log_error(
                title="Tally Payment Entry Cancellation Failed",
                message=(
                    f"Payment Entry: {doc.name}\n\n"
                    f"Response:\n{result.get('response', '')}\n\n"
                    f"XML:\n{result.get('xml', '')}"
                ),
            )

    except Exception:

        frappe.log_error(
            title="Tally Payment Entry Cancel Error",
            message=frappe.get_traceback(),
        )


# ============================================================
# PAYMENT ENTRY DELETE
# ============================================================

def on_payment_entry_delete(doc, method=None):

    result = delete_tally_payment_entry(doc)

    if not result.get("success"):

        frappe.throw(
            "Payment Entry was NOT deleted because the Tally voucher "
            "could not be deleted.<br><br>"
            f"Tally Response: {result.get('response', '')}"
        )