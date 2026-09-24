app_name = "parshwa"
app_title = "Parshwa"
app_publisher = "Parshwa"
app_description = "Parshwa Custom Application"
app_email = "admin@example.com"
app_license = "mit"

doc_events = {
    
    "Item": {
        "after_insert": "parshwa.parshwa.tally.item.on_item_after_insert"
    },

    "Item Group": {
        "after_insert": "parshwa.parshwa.tally.item_group.on_item_group_after_insert"
    },

    "Customer": {
        "after_insert": "parshwa.parshwa.tally.customer.on_customer_after_insert"
    },

    "UOM": {
        "after_insert": "parshwa.parshwa.tally.uom.on_uom_after_insert"
    },

    "Supplier": {
        "after_insert": "parshwa.parshwa.tally.supplier.on_supplier_after_insert"
    },

    "Journal Entry": {
        "on_submit": "parshwa.parshwa.tally.hooks.on_journal_entry_submit",
        "on_cancel": "parshwa.parshwa.tally.hooks.on_journal_entry_cancel",
        "on_trash": "parshwa.parshwa.tally.hooks.on_journal_entry_trash",
    },
 
    "Sales Invoice": {
        "on_submit": "parshwa.parshwa.tally.hooks.on_sales_invoice_submit",
        "on_cancel": "parshwa.parshwa.tally.hooks.on_sales_invoice_cancel",
        "on_trash": "parshwa.parshwa.tally.hooks.on_sales_invoice_trash",
    },
    
    "Purchase Invoice": {
    "on_submit": "parshwa.parshwa.tally.hooks.on_purchase_invoice_submit",
    "on_cancel": "parshwa.parshwa.tally.hooks.on_purchase_invoice_cancel",
    "on_trash": "parshwa.parshwa.tally.hooks.on_purchase_invoice_trash",
},
    
   "Payment Entry": {
        "on_submit": "parshwa.parshwa.tally.hooks.on_payment_entry_submit",
        "on_cancel": "parshwa.parshwa.tally.hooks.on_payment_entry_cancel",
        "on_trash": "parshwa.parshwa.tally.hooks.on_payment_entry_delete",
    },
}