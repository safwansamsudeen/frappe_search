// Copyright (c) 2024, Safwan Samsudeen and contributors
// For license information, please see license.txt

frappe.ui.form.on("Search", {
  after_save(frm) {
    frappe.call({
      method:
        "frappe_search.frappe_search.doctype.search.search.tantivy_search",
      args: { query_txt: frm.doc.query },
      callback: (e) => {
        let groups = Object.groupBy(e.message, (r) => r.doctype);
        let sortedGroups = Object.entries(groups).sort(
          (l, l2) => l2[1].length - l[1].length
        );
        let html = "";
        for (let [groupName, results] of sortedGroups) {
          html += `<div class="py-3"> <h3>${groupName}</h3>`;
          html += `${results.map((l) => l.url).join("<br />")}</div>`;
        }
        frappe.msgprint(html || "No Results", "Search Results");
      },
    });
  },
});
