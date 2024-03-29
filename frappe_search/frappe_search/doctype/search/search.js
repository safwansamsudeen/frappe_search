// Copyright (c) 2024, Frappe Technologies Pvt Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on("Search", {
  refresh(frm) {
    frm.add_custom_button("Index", () => {
      frappe.confirm(
        "Are you sure you want to index or reindex the entire DB?",
        () => {
          frappe.call({
            method: "frappe_search.api.build_index",
            callback: (e) =>
              frappe.msgprint(`Completed indexing: added ${e.message} items.`),
          });
        }
      );
    });

    frm.add_custom_button("Search", () => {
      frappe.prompt(
        [{ fieldname: "query", fieldtype: "Data", label: "Query", reqd: 1 }],
        function ({ query }) {
          frappe.call({
            method: "frappe_search.api.search",
            args: { query, groupby: true },
            callback: ({ message: { results, duration, total } }) => {
              let html = `<p>You obtained ${total} results in about ${duration} milliseconds.</p>`;
              for (let [groupName, groupResults] of Object.entries(results)) {
                html += `<div class="py-3"><h3>${groupName}</h3>`;
                html += `${groupResults.map(showResult).join("<hr />")}</div>`;
              }
              frappe.msgprint(html, "Search Results");
            },
          });
        }
      );
    });
  },
});

function getIndicesOf(searchStr, str, caseSensitive) {
  var searchStrLen = searchStr.length;
  if (searchStrLen == 0) {
    return [];
  }
  var startIndex = 0,
    index,
    indices = [];
  if (!caseSensitive) {
    str = str.toLowerCase();
    searchStr = searchStr.toLowerCase();
  }
  while ((index = str.indexOf(searchStr, startIndex)) > -1) {
    indices.push(index);
    startIndex = index + searchStrLen;
  }
  return indices;
}

function showResult(record) {
  return `<div><a href="${record.url}">${
    record.highlighted_title || record.title
  }</a><br><p>${record.highlighted_content.replaceAll("|||", " · ")}</p></div>`;
}
