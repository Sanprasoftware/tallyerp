frappe.ui.form.on("Tally Ledger Mapping", {
    setup(frm) {
        frm.set_query("reference_name", () => ({filters: frm.doc.reference_type === "Account"
            ? {company: frm.doc.company, is_group: 0, disabled: 0} : {}}));
    },
    reference_type(frm) { frm.set_value("reference_name", ""); },
    company(frm) { frm.set_value("reference_name", ""); }
});
