frappe.ui.form.on("Purchase Invoices", {
    refresh(frm) {
        calculate_totals(frm);
    }
});


frappe.ui.form.on("Purchase Invoices Item", {

    qty(frm, cdt, cdn) {
        calculate_amount(frm, cdt, cdn);
    },

    rate(frm, cdt, cdn) {
        calculate_amount(frm, cdt, cdn);
    },

    item(frm, cdt, cdn) {
        calculate_amount(frm, cdt, cdn);
    }

});


function calculate_amount(frm, cdt, cdn) {

    let row = locals[cdt][cdn];

    let qty = flt(row.qty);
    let rate = flt(row.rate);

    let amount = qty * rate;

    frappe.model.set_value(cdt, cdn, "amount", amount);

    calculate_totals(frm);
}


function calculate_totals(frm) {

    let total_qty = 0;
    let total_amount = 0;

    (frm.doc.items || []).forEach(function(row) {

        total_qty += flt(row.qty);
        total_amount += flt(row.amount);

    });

    frm.set_value("total_qty", total_qty);
    frm.set_value("total_amount", total_amount);
}