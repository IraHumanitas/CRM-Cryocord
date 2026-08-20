import frappe

from crm_cryocord.utils.pricing import get_item_price


@frappe.whitelist()
def get_item_rate(item_code, price_list):
    return get_item_price(item_code, price_list)