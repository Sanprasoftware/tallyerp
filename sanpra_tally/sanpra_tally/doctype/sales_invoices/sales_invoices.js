frappe.ui.form.on("Sales Invoices", {
    refresh: function(frm) {
        calculate_totals(frm);
    }
});

frappe.ui.form.on("Sales Invoice Items", {
    qty: function(frm, cdt, cdn) {
        calculate_row_amount(frm, cdt, cdn);
    },

    rate: function(frm, cdt, cdn) {
        calculate_row_amount(frm, cdt, cdn);
    },

    item: function(frm, cdt, cdn) {
        calculate_row_amount(frm, cdt, cdn);
    }
});

function calculate_row_amount(frm, cdt, cdn) {
    let row = frappe.get_doc(cdt, cdn);

    row.amount = (row.qty || 0) * (row.rate || 0);

    frm.refresh_field("item_table");

    calculate_totals(frm);
}

function calculate_totals(frm) {
    let total_qty = 0;
    let total_amount = 0;

    (frm.doc.item_table || []).forEach(function(row) {
        total_qty += row.qty || 0;
        total_amount += row.amount || 0;
    });

    frm.set_value("total_qty", total_qty);
    frm.set_value("total_amount", total_amount);
}