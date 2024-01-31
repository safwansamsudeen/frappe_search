# Copyright (c) 2024, Safwan Samsudeen and contributors
# For license information, please see license.txt
from __future__ import unicode_literals

from tantivy import Document, Index, SchemaBuilder, DocAddress

import frappe
from markdownify import markdownify as md
from frappe.utils.data import get_absolute_url

import frappe
from frappe.model.document import Document as FrappeDocument


class Search(FrappeDocument):
    pass


INDEX_PATH = "/Users/safwan/frappe-bench/apps/frappe_search/index"
EXCLUDED_DOCTYPES = [
    "DocField",
    "Workspace Shortcut",
    "Activity Log",
    "Notification Settings",
]


@frappe.whitelist()
def tantivy_search(query_txt, number_of_results=15):
    index = Index.open(INDEX_PATH)
    searcher = index.searcher()

    tokens = query_txt.split()
    hits = []

    for token in tokens:
        query = index.parse_query(token, ["title", "content", "name"])
        hits.append(
            {
                (best_doc_address.segment_ord, best_doc_address.doc)
                for _, best_doc_address in searcher.search(query, 1000).hits
            }
        )

    results = list(set.intersection(*hits))

    if not results:
        query = index.parse_query(query_txt, ["title", "content", "name"])
        results.extend(
            [
                r
                for _, best_doc_address in searcher.search(
                    query, number_of_results
                ).hits
                if not (r := (best_doc_address.segment_ord, best_doc_address.doc))
                in results
            ]
        )

    if not results:
        per_token = number_of_results // len(hits)
        for hit_set in hits:
            results.extend(list(hit_set)[:per_token])

    return [
        {
            **(r := searcher.doc(DocAddress(segment_ord, doc)).to_dict()),
            "url": format_result(r),
        }
        for segment_ord, doc in results
    ]


def format_result(record):
    return get_absolute_url(record["doctype"][0], record["name"][0])


def get_schema():
    schema_builder = SchemaBuilder()
    schema_builder.add_text_field("title", stored=True)
    schema_builder.add_text_field("content", stored=True, tokenizer_name="en_stem")
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
                            map(lambda x: md(str(x), convert=[]), record.values())
                        ),
                        "name": record.name or title,
                        "doctype": doctype["name"],
                    }
                    no_records += 1
                    records.append(data)
                    writer.add_document(Document(**data))

    writer.commit()
    return records, no_records
