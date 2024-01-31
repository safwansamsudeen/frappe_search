// Copyright (c) 2024, Safwan Samsudeen and contributors
// For license information, please see license.txt

frappe.ui.form.on("Search", {
  refresh(frm) {
    frm.add_custom_button("Search", () => {
      frappe.prompt(
        [{ fieldname: "query", fieldtype: "Data", label: "Query", reqd: 1 }],
        function ({ query }) {
          const min = (x, y) => (x > y ? y : x);
          const max = (x, y) => (x > y ? x : y);

          function showRecord(record) {
            tokens = query.split(" ");
            let content_new = "";
            let title_new = "";
            for (let token of tokens) {
              content_idx = record.content[0].search(new RegExp(token, "ig"));
              content_new +=
                record.content[0]
                  .slice(
                    max(content_idx - 15, 0),
                    min(content_idx + 15, record.content[0].length)
                  )
                  .replaceAll(
                    new RegExp(token, "ig"),
                    (token) => `<mark>${token}</mark>`
                  )
                  .trim() + "... ";

              title_new = record.title[0].replaceAll(
                new RegExp(token, "ig"),
                (token) => `<mark>${token}</mark>`
              );
            }

            return `<div><a href="${record.url}}">${title_new}</a><br><p>${content_new}</p></div>`;
          }

          frappe.call({
            method:
              "frappe_search.frappe_search.doctype.search.search.tantivy_search",
            args: { query_txt: query },
            callback: (e) => {
              let groups = Object.groupBy(e.message, (r) => r.doctype);
              let sortedGroups = Object.entries(groups).sort(
                (l, l2) => l2[1].length - l[1].length
              );
              console.log(e.message);
              let html = "";
              for (let [groupName, results] of sortedGroups) {
                html += `<div class="py-3"> <h3>${groupName}</h3>`;
                html += `${results.map(showRecord).join("<hr />")}</div>`;
              }
              frappe.msgprint(html, "Search Results");
            },
          });
        }
      );
    });
  },
});
