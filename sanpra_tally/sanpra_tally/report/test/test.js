frappe.query_reports["Sales Invoice Report"] = {
    filters: [
        {
            fieldname: "from_date",
            label: "From Date",
            fieldtype: "Date",
            default: frappe.datetime.month_start()
        },
        {
            fieldname: "to_date",
            label: "To Date",
            fieldtype: "Date",
            default: frappe.datetime.get_today()
        },
        {
            fieldname: "customer",
            label: "Customer",
            fieldtype: "Link",
            options: "Party"
        },
        {
            fieldname: "invoice_no",
            label: "Invoice No",
            fieldtype: "Link",
            options: "Sales Invoices"
        }
    ]
};