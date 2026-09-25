frappe.provide("sanpra_tally");
sanpra_tally.registered = sanpra_tally.registered || new Set();
for (const doctype of ["Sales Invoice", "Purchase Invoice", "Journal Entry", "Payment Entry"]) {
    if (sanpra_tally.registered.has(doctype)) continue;
    sanpra_tally.registered.add(doctype);
    frappe.ui.form.on(doctype, {
        refresh(frm) {
            if (frm.doc.docstatus === 0) return;
            const status = frm.doc.custom_tally_sync_status || "Pending";
            const colors = {Synced: "green", Failed: "red", "Needs Review": "orange", Cancelled: "gray"};
            frm.dashboard.set_headline_alert(__("Tally: {0}", [__(status)]), colors[status] || "blue");
            if (!frappe.user_roles.some(role => ["System Manager", "Accounts Manager", "Accounts User"].includes(role))) return;
            const queue = async (check_only) => {
                await frappe.call({method: "sanpra_tally.sync.check_and_retry",
                    args: {doctype: frm.doctype, name: frm.doc.name, check_only}, freeze: true,
                    freeze_message: __("Queueing Tally check...")});
                frappe.show_alert({message: __("Tally check queued. Refresh to see the result."), indicator: "blue"});
                await frm.reload_doc();
            };
            frm.add_custom_button(__("Check Tally"), () => queue(1), __("Tally"));
            frm.add_custom_button(__("Check & Retry"), () => queue(0), __("Tally"));
            if (frappe.user_roles.some(role => ["System Manager", "Accounts Manager"].includes(role))) {
                frm.add_custom_button(__("Ledger Mapping"), () => frappe.set_route("List", "Tally Ledger Mapping", {company: frm.doc.company}), __("Tally"));
            }
        }
    });
}

if (!sanpra_tally.listening) {
    sanpra_tally.listening = true;
    frappe.realtime.on("tally_sync_updated", (data) => {
        if (window.cur_frm && cur_frm.doctype === data.doctype && cur_frm.doc.name === data.name && !cur_frm.is_dirty()) {
            cur_frm.reload_doc();
        }
    });
}
