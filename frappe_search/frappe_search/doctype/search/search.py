# Copyright (c) 2024, Safwan Samsudeen and contributors
# For license information, please see license.txt

import frappe
from tantivy import Document, Index, SchemaBuilder


INDEX_PATH = "/Users/safwan/frappe-bench/apps/frappe_search/index"

@frappe.whitelist()
def create_index():
    global index
    DOCTYPES = {
        "Activity Log": {
            "title": "subject",
            "content": "ip_address",  
		},
        "User": {"title": "full_name", "content": "email"},
    }
    
    schema = get_schema()
    index = Index(schema, path=INDEX_PATH)
    writer = index.writer()
    
    docs = []
    
    for doctype, fields in DOCTYPES.items():
        for d in frappe.db.get_all(
            doctype,
            fields=list(fields.values()),
        ):
            docs.append({**{field: d[field_name] for field, field_name in fields.items()}, "doctype": doctype})
            writer.add_document(Document(
                **{field: d[field_name] for field, field_name in fields.items()}, doctype=doctype))
    writer.commit()

    return docs

@frappe.whitelist()
def tantivy_search(query_txt):
    index = Index.open(INDEX_PATH)
    searcher = index.searcher()
    schema = get_schema()
    query = index.parse_query(query_txt, ["title", "content", "doctype"])
    return [
        searcher.doc(best_doc_address).to_dict()
        for _, best_doc_address in searcher.search(query, 3).hits
    ]

def get_schema():
    schema_builder = SchemaBuilder()
    schema_builder.add_text_field("title", stored=True)
    schema_builder.add_text_field("content", stored=True)
    schema_builder.add_text_field("doctype", stored=True)
    return schema_builder.build()

