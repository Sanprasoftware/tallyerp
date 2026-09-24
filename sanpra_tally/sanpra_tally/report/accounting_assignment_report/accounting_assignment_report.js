frappe.query_reports["Accounting Assignment Report"] = {
    filters: [
        {
            fieldname: "company",
            label: "Company",
            fieldtype: "Link",
            options: "Company"
        },
        {
            fieldname: "from_date",
            label: "From Date",
            fieldtype: "Date",
            default: frappe.datetime.add_months(frappe.datetime.get_today(), -1)
        },
        {
            fieldname: "to_date",
            label: "To Date",
            fieldtype: "Date",
            default: frappe.datetime.get_today()
        },
        {
            fieldname: "transaction_type",
            label: "Transaction Type",
            fieldtype: "Select",
            options: "\nSales Invoice\nPayment Entry\nJournal Entry"
        },
        {
            fieldname: "party",
            label: "Party",
            fieldtype: "Data"
        },
        {
            fieldname: "currency",
            label: "Currency",
            fieldtype: "Link",
            options: "Currency"
        }
    ]
};