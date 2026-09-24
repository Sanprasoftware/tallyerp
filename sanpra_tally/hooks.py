app_name = "sanpra_tally"
app_title = "Sanpra Tally"
app_publisher = "Parshwa"
app_description = "Sanpra Tally Custom Application"
app_email = "admin@example.com"
app_license = "mit"

doc_events = {
    
    "Item": {
        "after_insert": "sanpra_tally.sanpra_tally.tally.item.on_item_after_insert"
    },

    "Item Group": {
        "after_insert": "sanpra_tally.sanpra_tally.tally.item_group.on_item_group_after_insert"
    },

    "Customer": {
        "after_insert": "sanpra_tally.sanpra_tally.tally.customer.on_customer_after_insert"
    },

    "UOM": {
        "after_insert": "sanpra_tally.sanpra_tally.tally.uom.on_uom_after_insert"
    },

    "Supplier": {
        "after_insert": "sanpra_tally.sanpra_tally.tally.supplier.on_supplier_after_insert"
    },

    "Journal Entry": {
        "on_submit": "sanpra_tally.sanpra_tally.tally.hooks.on_journal_entry_submit",
        "on_cancel": "sanpra_tally.sanpra_tally.tally.hooks.on_journal_entry_cancel",
        "on_trash": "sanpra_tally.sanpra_tally.tally.hooks.on_journal_entry_trash",
    },
 
    "Sales Invoice": {
        "on_submit": "sanpra_tally.sanpra_tally.tally.hooks.on_sales_invoice_submit",
        "on_cancel": "sanpra_tally.sanpra_tally.tally.hooks.on_sales_invoice_cancel",
        "on_trash": "sanpra_tally.sanpra_tally.tally.hooks.on_sales_invoice_trash",
    },
    
    "Purchase Invoice": {
    "on_submit": "sanpra_tally.sanpra_tally.tally.hooks.on_purchase_invoice_submit",
    "on_cancel": "sanpra_tally.sanpra_tally.tally.hooks.on_purchase_invoice_cancel",
    "on_trash": "sanpra_tally.sanpra_tally.tally.hooks.on_purchase_invoice_trash",
},
    
   "Payment Entry": {
        "on_submit": "sanpra_tally.sanpra_tally.tally.hooks.on_payment_entry_submit",
        "on_cancel": "sanpra_tally.sanpra_tally.tally.hooks.on_payment_entry_cancel",
        "on_trash": "sanpra_tally.sanpra_tally.tally.hooks.on_payment_entry_delete",
    },
}