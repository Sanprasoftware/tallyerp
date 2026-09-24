// Copyright (c) 2026, Parshwa and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Journal Entrys", {
// 	refresh(frm) {

// 	},
// });
frappe.ui.form.on("Journal Entry", {

    refresh(frm) {
        calculate_journal_totals(frm);
    }

});

frappe.ui.form.on("Journal Entry Account", {

    debit(frm) {
        calculate_journal_totals(frm);
    },

    credit(frm) {
        calculate_journal_totals(frm);
    },

    accounting_entries_remove(frm) {
        calculate_journal_totals(frm);
    }

});

function calculate_journal_totals(frm) {

    let total_debit = 0;
    let total_credit = 0;

    (frm.doc.accounting_entries || []).forEach(row => {

        total_debit += row.debit || 0;
        total_credit += row.credit || 0;

    });

    frm.set_value("total_debit", total_debit);
    frm.set_value("total_credit", total_credit);

    frm.set_value(
        "difference",
        total_debit - total_credit
    );
}