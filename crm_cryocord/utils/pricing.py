import frappe
from frappe.utils import flt

def get_item_price(item_code: str, price_list: str) -> float:
    """
    Return selling rate from Item Price.
    """

    rate = frappe.db.get_value(
        "Item Price",
        {
            "item_code": item_code,
            "price_list": price_list,
        },
        "price_list_rate",
    )

    return flt(rate or 0)