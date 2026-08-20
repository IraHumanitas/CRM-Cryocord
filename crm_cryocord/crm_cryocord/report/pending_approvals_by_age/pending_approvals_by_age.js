frappe.query_reports["Pending Approvals by Age"] = {
    filters: [
        {
            fieldname: "sales_officer",
            label: __("Sales Officer"),
            fieldtype: "Link",
            options: "User"
        }
    ]
};