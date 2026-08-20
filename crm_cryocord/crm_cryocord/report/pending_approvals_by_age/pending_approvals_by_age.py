import frappe
from frappe import _
from frappe.utils import getdate, nowdate


def execute(filters=None):
    filters = filters or {}

    columns = get_columns()
    data = get_data(filters)

    chart = get_chart(data)
    report_summary = get_report_summary(data)

    return (
        columns,
        data,
        None,
        chart,
        report_summary,
        False,
    )


def get_columns():
    return [
        {
            "label": _("Case ID"),
            "fieldname": "name",
            "fieldtype": "Link",
            "options": "CryoCord Onboarding Case",
            "width": 180,
        },
        {
            "label": _("Customer"),
            "fieldname": "customer",
            "fieldtype": "Link",
            "options": "Customer",
            "width": 180,
        },
        {
            "label": _("Workflow State"),
            "fieldname": "workflow_state",
            "fieldtype": "Data",
            "width": 180,
        },
        {
            "label": _("Sales Officer"),
            "fieldname": "sales_officer",
            "fieldtype": "Link",
            "options": "User",
            "width": 170,
        },

        {
            "label": _("Submitted On"),
            "fieldname": "submitted_on",
            "fieldtype": "Datetime",
            "width": 165,
        },
        {
            "label": _("Waiting Days"),
            "fieldname": "waiting_days",
            "fieldtype": "Int",
            "width": 100,
        },
        {
            "label": _("Aging"),
            "fieldname": "aging",
            "fieldtype": "Data",
            "width": 120,
        },
        {
            "label": _("Queue Status"),
            "fieldname": "queue_status",
            "fieldtype": "Data",
            "width": 120,
        },

        {
            "label": _("Expected Delivery Date"),
            "fieldname": "expected_delivery_date",
            "fieldtype": "Date",
            "width": 130,
        },
        {
            "label": _("Days to EDD"),
            "fieldname": "days_to_edd",
            "fieldtype": "Int",
            "width": 110,
        },
        {
            "label": _("EDD Status"),
            "fieldname": "edd_status",
            "fieldtype": "Data",
            "width": 120,
        },

        {
            "label": _("Priority Score"),
            "fieldname": "priority_score",
            "fieldtype": "Int",
            "width": 120,
        },
        {
            "label": _("Priority"),
            "fieldname": "priority",
            "fieldtype": "Data",
            "width": 110,
        },

        {
            "label": _("Service Category"),
            "fieldname": "service_category",
            "fieldtype": "Data",
            "width": 160,
        },
        {
            "label": _("Grand Total"),
            "fieldname": "grand_total_excl_tax",
            "fieldtype": "Currency",
            "width": 140,
        },
    ]


def get_data(filters):
    conditions = []
    values = {}

    if filters.get("workflow_state"):
        conditions.append("workflow_state = %(workflow_state)s")
        values["workflow_state"] = filters["workflow_state"]

    if filters.get("sales_officer"):
        conditions.append("sales_officer = %(sales_officer)s")
        values["sales_officer"] = filters["sales_officer"]

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    rows = frappe.db.sql(
        f"""
        SELECT
            name,
            customer,
            service_category,
            sales_officer,
            expected_delivery_date,
            grand_total_excl_tax,
            submitted_on,
            workflow_state
        FROM `tabCryoCord Onboarding Case`
        {where_clause}
        ORDER BY submitted_on ASC
        """,
        values,
        as_dict=True,
    )

    today = getdate(nowdate())

    result = []

    for row in rows:
        waiting_days = 0

        if row.submitted_on:
            waiting_days = (today - getdate(row.submitted_on)).days

        if waiting_days <= 2:
            queue_status = "Normal"
        elif waiting_days <= 7:
            queue_status = "Warning"
        else:
            queue_status = "Critical"

        if waiting_days <= 2:
            aging = "0-2 Days"
        elif waiting_days <= 7:
            aging = "3-7 Days"
        else:
            aging = ">7 Days"

        score = 0
        if waiting_days > 7:
            score += 30
        elif waiting_days >= 3:
            score += 15

        days_to_edd = None
        edd_status = "-"

        if row.expected_delivery_date:
            days_to_edd = (
                getdate(row.expected_delivery_date) - today
            ).days

            if days_to_edd < 0:
                edd_status = "Overdue"
                score += 40
            elif days_to_edd <= 3:
                edd_status = "Due Soon"
                score += 20
            else:
                edd_status = "On Track"

        if (row.grand_total_excl_tax or 0) >= 10000:
            score += 10

        if score >= 60:
            priority = "🔴 High"
        elif score >= 30:
            priority = "🟡 Medium"
        else:
            priority = "🟢 Low"

        row.priority = priority
        row.days_to_edd = days_to_edd
        row.waiting_days = waiting_days
        row.queue_status = queue_status
        row.edd_status = edd_status
        row.priority_score = score
        row.aging = aging

        if filters.get("queue_status") and queue_status != filters.get("queue_status"):
            continue

        if filters.get("edd_status") and edd_status != filters.get("edd_status"):
            continue

        result.append(row)

    result.sort(
        key=lambda r: (
            -r.priority_score,
            -r.waiting_days,
            r.submitted_on or nowdate(),
        )
    )

    return result


def get_report_summary(data):
    total = len(data)

    normal = sum(1 for d in data if d.queue_status == "Normal")
    warning = sum(1 for d in data if d.queue_status == "Warning")
    critical = sum(1 for d in data if d.queue_status == "Critical")

    overdue = sum(1 for d in data if d.edd_status == "Overdue")

    avg_waiting = (
        round(sum(d.waiting_days for d in data) / total, 1)
        if total else 0
    )

    due_soon = sum(
        1 for d in data
        if d.edd_status == "Due Soon"
    )

    return [
        {
            "label": _("Total Cases"),
            "value": total,
            "datatype": "Int",
            "indicator": "Blue",
        },
        {
            "label": _("Critical Queue"),
            "value": critical,
            "datatype": "Int",
            "indicator": "Red",
        },
        {
            "label": _("Warning Queue"),
            "value": warning,
            "datatype": "Int",
            "indicator": "Orange",
        },
        {
            "label": _("Overdue EDD"),
            "value": overdue,
            "datatype": "Int",
            "indicator": "Red",
        },
        {
            "label": _("Due Soon"),
            "value": due_soon,
            "datatype": "Int",
            "indicator": "Orange",
        },
        {
            "label": _("Average Waiting Days"),
            "value": avg_waiting,
            "datatype": "Float",
            "indicator": "Green",
        }
    ]



def get_chart(data):
    aging_distribution = {
        "0-2 Days": 0,
        "3-7 Days": 0,
        ">7 Days": 0,
    }

    for row in data:
        aging_distribution[row.aging] += 1

    return {
        "data": {
            "labels": [
                _("0-2 Days"),
                _("3-7 Days"),
                _(">7 Days"),
            ],
            "datasets": [
                {
                    "name": _("Cases"),
                    "values": [
                        aging_distribution["0-2 Days"],
                        aging_distribution["3-7 Days"],
                        aging_distribution[">7 Days"],
                    ],
                }
            ],
        },
        "type": "donut",
        "colors": [
            "#4CAF50",
            "#FFC107",
            "#F44336",
        ],
        "height": 280,
    }