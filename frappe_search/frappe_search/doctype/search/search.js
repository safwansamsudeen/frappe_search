// Copyright (c) 2024, Safwan Samsudeen and contributors
// For license information, please see license.txt

frappe.ui.form.on("Search", {
  refresh(frm) {
    frm.add_custom_button("Index", () => {
      frappe.confirm(
        "Are you sure you want to index or reindex the entire DB?",
        () => {
          frappe.call({
            method:
              "frappe_search.frappe_search.doctype.search.search.complete_index",
            callback: (e) =>
              frappe.msgprint(
                `Completed indexing: added ${e.message[1]} items.`
              ),
          });
        }
      );
    });
    frm.add_custom_button("Search", () => {
      frappe.prompt(
        [{ fieldname: "query", fieldtype: "Data", label: "Query", reqd: 1 }],
        function ({ query }) {
          const min = (x, y) => (x > y ? y : x);
          const max = (x, y) => (x > y ? x : y);

          function highlight(record) {
            tokens = query.split(" ");
            let new_content = "";
            let new_title = record.title[0];
            for (let token of tokens) {
              content_indices = getIndicesOf(token, record.content[0], false);
              for (idx of content_indices)
                new_content +=
                  record.content[0]
                    .slice(
                      max(idx - 15 - token.length, 0),
                      min(idx + 15 + token.length, record.content[0].length)
                    )
                    .replaceAll(
                      new RegExp(token, "ig"),
                      (token) => `<mark>${token}</mark>`
                    )
                    .trim() + "... ";
              new_title = new_title.replaceAll(
                new RegExp(token, "ig"),
                (token) => `<mark>${token}</mark>`
              );
            }

            return { ...record, content: new_content, title: new_title };
          }

          function sortRecords(prev, curr) {
            return (
              (curr.content.match(/<mark>/g)?.length || 0) -
              (prev.content.match(/<mark>/g)?.length || 0)
            );
          }

          function prioritizeTitle(prev, curr) {
            return (
              (curr.title.match(/<mark>/g)?.length || 0) -
              (prev.title.match(/<mark>/g)?.length || 0)
            );
          }

          function showResult(record) {
            return `<div><a href="${record.url}">${
              record.title
            }</a><br><p>${record.content.replaceAll("\n", " · ")}</p></div>`;
          }

          frappe.call({
            method:
              "frappe_search.frappe_search.doctype.search.search.tantivy_search",
            args: { query_txt: query },
            callback: (e) => {
              let html = "";
              for (let [groupName, results] of Object.entries(e.message)) {
                html += `<div class="py-3"> <h3>${groupName}</h3>`;
                html += `${results
                  .map(highlight)
                  .sort(sortRecords)
                  .sort(prioritizeTitle)
                  .map(showResult)
                  .join("<hr />")}</div>`;
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
