app_name = "frappe_search"
app_title = "Frappe Search"
app_publisher = "Frappe Technologies Pvt Ltd"
app_description = "Full text search for Frappe apps"
app_email = "safwan@frappe.com"
app_license = "mit"

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
    "*": {
        "on_update": "frappe_search.frappe_search.doctype.search.search.update_index",
    }
}
