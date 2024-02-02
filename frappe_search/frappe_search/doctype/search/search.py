# Copyright (c) 2024, Safwan Samsudeen and contributors
# For license information, please see license.txt
from __future__ import unicode_literals

from tantivy import Document, Index, SchemaBuilder, DocAddress
from collections import defaultdict

import frappe
import re
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

DOCTYPES = {
    "GP Discussion": ("title", ["content"]),
    "GP Page": ("title", ["content"]),
    "GP Comment": ("name", ["content"]),
}


@frappe.whitelist()
def tantivy_search(query_txt, target_number=20):
    index = Index.open(INDEX_PATH)
    searcher = index.searcher()

    tokens = query_txt.split()
    hits = []

    # Parse individual tokens, and try to see intersections
    for token in tokens:
        query = index.parse_query(
            token,
            ["title", "content", "name"],
            fuzzy_fields={"title": (True, 2, True), "content": (True, 2, True)},
        )
        hits.append(
            {
                (best_doc_address.segment_ord, best_doc_address.doc)
                for _, best_doc_address in searcher.search(query, 1000).hits
            }
        )

    # If there are no hits at all, there are no results.
    if all(not hit for hit in hits):
        return []

    results = list(set.intersection(*hits))

    # Parse entire query
    if not results:
        query = index.parse_query(
            query_txt,
            ["title", "content", "name"],
            fuzzy_fields={"title": (True, 2, True), "content": (True, 2, True)},
        )
        results.extend(
            [
                r
                for _, best_doc_address in searcher.search(
                    query, target_number // 3
                ).hits
                if not (r := (best_doc_address.segment_ord, best_doc_address.doc))
                in results
            ]
        )
    # If that too doesn't work, merge results from each individual token
    if not results:
        per_token = target_number // len(hits)
        for hit_set in hits:
            results.extend(list(hit_set)[:per_token])

    results = [
        {
            **(r := searcher.doc(DocAddress(segment_ord, doc)).to_dict()),
            "url": format_result(r),
        }
        for segment_ord, doc in results
    ]

    return groupby_and_trim_results(
        sorted(
            map(lambda r: highlight(r, tokens), results),
            key=lambda r: (r["no_title_highlights"], r["no_content_highlights"]),
            reverse=True,
        ),
        target_number,
    )


def groupby_and_trim_results(records, target_number):
    results = defaultdict(list)
    for record in records:
        results[record["doctype"][0]].append(record)
    max_group_length = target_number // len(results)

    trimmed_groups = {
        doctype: res[:max_group_length] for doctype, res in results.items()
    }
    return dict(sorted(trimmed_groups.items(), key=lambda x: len(x[1]), reverse=True))


def highlight(record, tokens):
    title = record["title"][0]
    highlighted_content = ""
    for token in tokens:
        title = re.sub(
            token,
            lambda m: f"<mark>{m.group()}</mark>",
            title,
            flags=re.M | re.I,
        )
        content_indices = [
            m.start() for m in re.finditer(token, record["content"][0], re.M | re.I)
        ]
        for idx in content_indices:
            snippet = record["content"][0][
                max(idx - 15 - len(token), 0) : min(idx + 15, len(record["content"][0]))
            ]
            highlighted_content += (
                re.sub(
                    token,
                    lambda m: f"<mark>{m.group()}</mark>",
                    snippet,
                    flags=re.M | re.I,
                )
                + "... "
            )

    highlighted_content = highlighted_content.strip("- \n.")
    return {
        **record,
        "highlighted_title": title,
        "highlighted_content": highlighted_content
        + ("..." if highlighted_content else ""),
        "no_title_highlights": title.count("<mark>"),
        "no_content_highlights": highlighted_content.count("<mark>"),
    }


def format_result(record):
    return get_absolute_url(record["doctype"][0], record["name"][0])


def get_schema():
    schema_builder = SchemaBuilder()
    schema_builder.add_text_field("title", stored=True, tokenizer_name="en_stem")
    schema_builder.add_text_field("content", stored=True, tokenizer_name="en_stem")
    schema_builder.add_text_field("doctype", stored=True)
    schema_builder.add_text_field("name", stored=True)
    # Use text field for ID as hash values will be very large
    schema_builder.add_text_field("id", stored=True)
    return schema_builder.build()


@frappe.whitelist()
def update_index(doc, _=None):
    index = Index(get_schema(), path=INDEX_PATH)
    writer = index.writer()
    if doc.doctype not in DOCTYPES:
        return False

    id = f"{doc.doctype}-{doc.name}"
    writer.delete_documents("id", id)
    writer.commit()

    title_field, content_fields = DOCTYPES[doc.doctype]
    writer.add_document(
        Document(
            id=id,
            doctype=doc.doctype,
            name=doc.name,
            title=str(getattr(doc, title_field)),
            content="|||".join(
                map(
                    lambda x: md(str(x), convert=[]),
                    (getattr(doc, field) for field in content_fields),
                )
            ),
        )
    )
    writer.commit()
    return True


@frappe.whitelist()
def build_complete_index(auto_index=False):
    doctypes = frappe.get_all(
        "DocType",
        fields=["name", "title_field"],
    )
    schema = get_schema()
    index = Index(schema, path=INDEX_PATH)
    writer = index.writer()

    # Reset index
    writer.delete_all_documents()
    writer.commit()

    records = []
    no_records = 0

    for doctype in doctypes:
        if not auto_index and doctype["name"] not in DOCTYPES:
            continue
        if auto_index and doctype["name"] in EXCLUDED_DOCTYPES:
            continue
        doctype_obj = frappe.get_doc("DocType", doctype["name"])
        doctype_record = DOCTYPES.get(doctype["name"])
        content_fields = (
            [field.fieldname for field in doctype_obj.fields if field.in_global_search]
            if auto_index
            else doctype_record[1]
        )
        if (
            not auto_index
            or doctype_obj.index_web_pages_for_search
            and not doctype_obj.issingle
        ):
            title_field = (
                doctype["title_field"] or "name" if auto_index else doctype_record[0]
            )
            db_records = frappe.get_all(
                doctype["name"], fields=[title_field, *content_fields, "name"]
            )
            if db_records:
                for record in db_records:
                    title = record.pop(title_field)
                    unique_str = f'{doctype["name"]}-{record.name}'
                    data = {
                        "title": str(title),
                        "content": "|||".join(
                            map(lambda x: md(str(x), convert=[]), record.values())
                        ),
                        "name": record.name or title,
                        "doctype": doctype["name"],
                        "id": unique_str,
                    }
                    no_records += 1
                    records.append(data)
                    writer.add_document(Document(**data))

    writer.commit()
    return records, no_records
