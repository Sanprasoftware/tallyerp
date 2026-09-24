frappe.ui.form.on("Payment Entry", {

    setup(frm) {

        frm.set_query("party", function() {

            return {
                filters: {
                    party_type: frm.doc.party_type
                }
            };

        });

    },

    payment_type(frm) {

        if (frm.doc.payment_type === "Receive") {
            frappe.msgprint("Receiving payment from customer");
        }

        if (frm.doc.payment_type === "Pay") {
            frappe.msgprint("Paying supplier");
        }

    }

});