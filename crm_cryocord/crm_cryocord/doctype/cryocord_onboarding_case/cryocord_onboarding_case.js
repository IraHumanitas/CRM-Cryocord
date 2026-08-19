frappe.ui.form.on("CryoCord Onboarding Case", {
    setup(frm) {
        frm.set_query("service_item", "requested_packages", () => {
            return {
                filters: {
                    item_group: frm.doc.service_category,
                    cc_is_storage_service: 1,
                    disabled: 0
                }
            };
        });
    },

    refresh(frm) {
        toggle_delivery_section(frm);
    },

    service_category(frm) {
        toggle_delivery_section(frm);
    }
});

function toggle_delivery_section(frm) {
    const banking_services = [
        "Cord Blood Banking",
        "Cord Tissue Banking",
        "Stem Cell Banking",
        "Biobanking"
    ];

    if (!banking_services.includes(frm.doc.service_category)) {
        if (frm.doc.expected_delivery_date) {
            frm.set_value("expected_delivery_date", null);
        }
        if (frm.doc.preferred_hospital) {
            frm.set_value("preferred_hospital", null);
        }
    }
}

frappe.ui.form.on("CryoCord Requested Package", {
    service_item(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (!row.service_item) return;

        frappe.db.get_value(
            "Item",
            row.service_item,
            [
                "description",
                "cc_default_billing_type",
                "cc_default_storage_years"
            ]
        ).then(r => {
            if (!r.message) return;

            frappe.model.set_value(cdt, cdn,
                "description",
                r.message.description
            );

            frappe.model.set_value(cdt, cdn,
                "billing_type",
                r.message.cc_default_billing_type
            );

            if (r.message.cc_default_billing_type === "Annual/Recurring") {
                frappe.model.set_value(
                    cdt,
                    cdn,
                    "storage_duration_years",
                    r.message.cc_default_storage_years || 1
                );
            }

        });
    },

    qty(frm, cdt, cdn) {
        calculate_row(frm, cdt, cdn);
    },

    rate(frm, cdt, cdn) {
        calculate_row(frm, cdt, cdn);
    },

    discount_percentage(frm, cdt, cdn) {
        calculate_row(frm, cdt, cdn);
    }
});

function calculate_row(frm, cdt, cdn) {
    const row = locals[cdt][cdn];

    row.amount = flt(row.qty) * flt(row.rate);

    row.discount_amount = row.amount * flt(row.discount_percentage) / 100;

    row.net_amount = row.amount - row.discount_amount;

    refresh_field("requested_packages");

    calculate_totals(frm);
}

function calculate_totals(frm) {
    let total = 0;
    let discount = 0;
    let grand = 0;

    (frm.doc.requested_packages || []).forEach(row => {
        total += flt(row.amount);
        discount += flt(row.discount_amount);
        grand += flt(row.net_amount);
    });

    frm.set_value("total_amount", total);
    frm.set_value("total_discount", discount);
    frm.set_value("grand_total_excl_tax", grand);
}