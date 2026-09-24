frappe.query_reports["Payment Entry Report"] = {

    filters: [
        {
            fieldname: "name",
            label: "Payment Entry",
            fieldtype: "Link",
            options: "Payment Entrys"
        },

        {
            fieldname: "posting_date",
            label: "Posting Date",
            fieldtype: "Date"
        },

        {
            fieldname: "payment_type",
            label: "Payment Type",
            fieldtype: "Select",
            options: "\nReceive\nPay"
        },

        {
            fieldname: "party_type",
            label: "Party Type",
            fieldtype: "Select",
            options: "\nCustomer\nSupplier"
        },

        {
            fieldname: "party",
            label: "Party",
            fieldtype: "Link",
            options: "Party"
        }
    ]
};