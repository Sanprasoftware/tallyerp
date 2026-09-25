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
        "on_submit": "sanpra_tally.sync.on_submit",
        "on_cancel": "sanpra_tally.sync.on_cancel",
        "on_trash": "sanpra_tally.sync.on_trash",
    },
 
    "Sales Invoice": {
        "on_submit": "sanpra_tally.sync.on_submit",
        "on_cancel": "sanpra_tally.sync.on_cancel",
        "on_trash": "sanpra_tally.sync.on_trash",
    },
    
    "Purchase Invoice": {
    "on_submit": "sanpra_tally.sync.on_submit",
    "on_cancel": "sanpra_tally.sync.on_cancel",
    "on_trash": "sanpra_tally.sync.on_trash",
},
    
   "Payment Entry": {
        "on_submit": "sanpra_tally.sync.on_submit",
        "on_cancel": "sanpra_tally.sync.on_cancel",
        "on_trash": "sanpra_tally.sync.on_trash",
    },
}
after_install = "sanpra_tally.install.ensure_fields"
after_migrate = "sanpra_tally.install.ensure_fields"

# Export only the Custom Fields owned by the Tally integration.
fixtures = [
    {
        "dt": "Custom Field",
        "filters": [
            ["fieldname", "in", [
                "custom_tally_voucher_id",
                "custom_tally_voucher_date",
                "custom_tally_sync_status",
                "custom_tally_sync_error",
                "custom_tally_last_sync_attempt",
                "custom_tally_delivery_uncertain",
                "custom_tally_cancel_voucher_id",
            ]],
            ["dt", "in", ["Purchase Invoice", "Sales Invoice", "Journal Entry", "Payment Entry"]],
        ],
    },
]

doctype_js = {doctype: "public/js/tally_sync.js" for doctype in
    ("Sales Invoice", "Purchase Invoice", "Journal Entry", "Payment Entry")}
