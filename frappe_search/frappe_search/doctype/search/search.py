# Copyright (c) 2024, Safwan Samsudeen and contributors
# For license information, please see license.txt
from __future__ import unicode_literals

from tantivy import Document, Index, SchemaBuilder, DocAddress, SnippetGenerator
from collections import defaultdict
from datetime import datetime

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

DOCTYPES = {
    "GP Discussion": ("title", ["content"], ["team", "project"]),
    "GP Page": ("title", ["content"], ["team", "project"]),
    "GP Comment": ("name", ["content"], []),
}


@frappe.whitelist()
def tantivy_search(query, target_number=20, groupby=True):
    # Gimick to ensure users can name the argument as `query`
    query_txt = query

    a = datetime.now()
    schema = get_schema()
    index = Index.open(INDEX_PATH)
    searcher = index.searcher()

    tokens = query_txt.split()
    hits = []
    non_fuzzy_query = index.parse_query(query_txt, ["title", "content", "name"])
    highlights = []

    # Parse individual tokens, and try to see intersections
    for token in tokens:
        query = index.parse_query(
            token,
            ["title", "content", "name"],
            fuzzy_fields={"title": (True, 2, True), "content": (True, 2, True)},
        )
        token_hit = {
            (best_doc_address.segment_ord, best_doc_address.doc)
            for _, best_doc_address in searcher.search(query, 1000).hits
        }
        hits.append(token_hit)
        highlights.extend(highlight(token_hit, searcher, non_fuzzy_query, schema))

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
        highlights.extend(highlight(results, searcher, non_fuzzy_query, schema))

    # If that too doesn't work, merge results from each individual token
    if not results:
        per_token = target_number // len(hits)
        for hit_set in hits:
            results.extend(list(hit_set)[:per_token])

    result_docs = sorted(
        (r for r in highlights if r["addr"] in results),
        key=lambda r: (r["no_of_title_highlights"], r["no_of_content_highlights"]),
        reverse=True,
    )

    b = datetime.now()
    n, final_results = (
        groupby_and_trim_results(result_docs, target_number)
        if groupby
        else (target_number, result_docs[:target_number])
    )
    diff = b - a
    return {
        "results": final_results,
        "duration": diff.seconds * 100 + (diff.microseconds / 1000),
        "total": n,
    }


def groupby_and_trim_results(records, target_number):
    results = defaultdict(list)
    for record in records:
        results[record["doctype"]].append(record)

    max_group_length = target_number // len(results)
    trimmed_groups = {}
    n = 0

    for doctype, res in results.items():
        trimmed_groups[doctype] = res[:max_group_length]
        n += len(res[:max_group_length])

    return n, dict(
        sorted(trimmed_groups.items(), key=lambda x: len(x[1]), reverse=True)
    )


def highlight(results, searcher, query, schema):
    title_snippet_generator = SnippetGenerator.create(searcher, query, schema, "title")
    content_snippet_generator = SnippetGenerator.create(
        searcher, query, schema, "content"
    )

    cleaned_results = []
    for segment_ord, _doc in results:
        doc = searcher.doc(DocAddress(segment_ord, _doc))
        title_snippet = title_snippet_generator.snippet_from_doc(doc)
        content_snippet = content_snippet_generator.snippet_from_doc(doc)
        # if title_snippet.highlighted() or content_snippet.highlighted():
        cleaned_results.append(
            {
                "name": doc["name"][0],
                "title": doc["title"][0],
                "content": doc["content"][0],
                "doctype": doc["doctype"][0],
                "highlighted_title": title_snippet.to_html()
                .replace("<b>", "<mark>")
                .replace("</b>", "</mark>"),
                "highlighted_content": content_snippet.to_html()
                .replace("<b>", "<mark>")
                .replace("</b>", "</mark>"),
                "no_of_title_highlights": len(title_snippet.highlighted()),
                "no_of_content_highlights": len(content_snippet.highlighted()),
                "url": get_url(doc),
                "extras": doc["extras"][0],
                "id": doc["id"][0],
                "addr": (segment_ord, _doc),
            }
        )
    return cleaned_results


def get_url(record):
    return get_absolute_url(record["doctype"][0], record["name"][0])


def get_schema():
    schema_builder = SchemaBuilder()
    schema_builder.add_text_field("id", stored=True)
    schema_builder.add_text_field("name", stored=True)
    schema_builder.add_text_field("title", stored=True, tokenizer_name="en_stem")
    schema_builder.add_text_field("content", stored=True, tokenizer_name="en_stem")
    schema_builder.add_json_field("extras", stored=True)
    schema_builder.add_text_field("doctype", stored=True)
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
        extra_fields = [] if auto_index else doctype_record[2]

        if (
            not auto_index
            or doctype_obj.index_web_pages_for_search
            and not doctype_obj.issingle
        ):
            title_field = (
                doctype["title_field"] or "name" if auto_index else doctype_record[0]
            )
            db_records = frappe.get_all(
                doctype["name"],
                fields=[title_field, *content_fields, *extra_fields, "name"],
            )
            if db_records:
                for record in db_records:
                    title = record.pop(title_field)
                    extras = {}
                    for extra_field in extra_fields:
                        extras[extra_field] = record.pop(extra_field)

                    unique_str = f'{doctype["name"]}-{record.name}'
                    data = {
                        "title": str(title),
                        "content": "|||".join(
                            map(lambda x: md(str(x), convert=[]), record.values())
                        ),
                        "name": record.name or title,
                        "doctype": doctype["name"],
                        "extras": extras,
                        "id": unique_str,
                    }
                    no_records += 1
                    records.append(data)
                    writer.add_document(Document(**data))

    writer.commit()
    return records, no_records
