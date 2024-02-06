from frappe_search.frappe_search.doctype.search.search import (
    build_complete_index,
    tantivy_search,
)
import frappe


@frappe.whitelist()
def search(query, target_number=25, groupby=True):
    if groupby == "true":
        groupby = True
    elif isinstance(groupby, str):
        groupby = False
    return tantivy_search(query, target_number, groupby)


@frappe.whitelist()
def build_index(auto_index=False):
    return build_complete_index(auto_index)
