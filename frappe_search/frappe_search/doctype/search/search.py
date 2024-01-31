# Copyright (c) 2024, Safwan Samsudeen and contributors
# For license information, please see license.txt

from tantivy import Document, Index, SchemaBuilder

import frappe
from frappe.core.utils import html2text
from frappe.utils.data import get_absolute_url


INDEX_PATH = "/Users/safwan/frappe-bench/apps/frappe_search/index"
EXCLUDED_DOCTYPES = [
    "DocField",
    "Workspace Shortcut",
    "Activity Log",
    "Notification Settings",
]


@frappe.whitelist()
def tantivy_search(query_txt):
    index = Index.open(INDEX_PATH)
    searcher = index.searcher()
    query = index.parse_query(query_txt, ["title", "content", "name"])
    return [
        {**(r := searcher.doc(best_doc_address).to_dict()), "url": format_result(r)}
        for _, best_doc_address in searcher.search(query, 30).hits
    ]


def format_result(record):
    return f'<a href="{get_absolute_url(record["doctype"][0], record["name"][0])}">{record["title"][0]}</a>'


def get_schema():
    schema_builder = SchemaBuilder()
    schema_builder.add_text_field("title", stored=True)
    schema_builder.add_text_field("content", stored=True)
    schema_builder.add_text_field("doctype", stored=True)
    schema_builder.add_text_field("name", stored=True)
    return schema_builder.build()


@frappe.whitelist()
def complete_index():
    doctypes = frappe.get_all(
        "DocType",
        fields=["name", "title_field"],
    )
    schema = get_schema()
    index = Index(schema, path=INDEX_PATH)
    writer = index.writer()

    records = []
    no_records = 0

    for doctype in doctypes:
        if doctype["name"] in EXCLUDED_DOCTYPES:
            continue
        doctype_obj = frappe.get_doc("DocType", doctype["name"])
        content_fields = [
            field.fieldname for field in doctype_obj.fields if field.in_global_search
        ]
        if doctype_obj.index_web_pages_for_search and not doctype_obj.issingle:
            title_field = doctype["title_field"] or "name"
            db_records = frappe.get_all(
                doctype["name"], fields=[title_field, *content_fields, "name"]
            )
            if db_records:
                for record in db_records:
                    title = record.pop(title_field)
                    data = {
                        "title": title,
                        "content": "\n".join(
                            map(lambda x: html2text(str(x)), record.values())
                        ),
                        "name": record.name or title,
                        "doctype": doctype["name"],
                    }
                    no_records += 1
                    records.append(data)
                    writer.add_document(Document(**data))

    writer.commit()
    return records, no_records
