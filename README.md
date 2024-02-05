## Frappe Search
#### How To Use
To your app's `hooks.py`, add the following variable. It should be a dictionary of dictionaries with the key being the DocType name, and the dictionary containing the content fields("mandatory"), the "title" field (optional, defaults to `name`), and the "extras" fields (optional, defaults to `[]`).
```py
frappe_search_doctypes = {
    "GP Discussion": {
        "content": ["content"],
        "extras": ["team", "project"],
        "title": "title",
    }
}
```

*What is the difference between content and extras*? Content and title fields will be used when searching. Extras are fields which will be returned to you as part of the search result, but will not be used in the searching.

**To build the index:** go over to the Search page and click on "Index". Alternatively, run the following command:
```
bench --site gameplan.test execute frappe_search.core.build_index
```

**To search:** by default, the app provides a search interface to test at the Search page. You can call `frappe_search.core.search` passing in `query` to get search results, though.
```js
frappe.call({
    method: 'frappe_search.core.search', 
    args: {query: 'toykraft'}, 
    callback: (e) => {
        console.log(e.message)
    }
})
// Output
{
    "results": [
        ...
    ],
    "duration": 16.167,
    "total": 3
}
```

Each record will be have the following keys:
- `title`: original title of the record
- `content`: original content of the record
- `highlighted_title`: highlighted content of the record
- `highlighted_content`: highlighted content of the record
- `doctype`: the DocType of the record
- `name`: the Frappe `name` value of the record
- `id`: unique identifier of index, a string of the format `{doctype}-{name}`.
- `addr`: the address in the Tantivy index
- `extras`: an object containing key value pairs of all the extra fields and values.
- `url`: the URL to the object in Frappe Desk.

#### Configuration
`search` accepts the following two optional arguments:
- `target_number`: the number of results to return, defaults to 25.
- `groupby`, defaults to false. If `true` (in JavaScript, `True` in Python), `results` will be an object, with the results grouped by doctype. The advantage with using our groupby is that each group will definitely be represented within the `target_number`, while if you got back `target_number` results, it might be the case that every doctype is not represented.

`build_index` can have take in the following optional argument:
- `auto_index`: whether to automatically decide which doctypes and fields to index. By default, `auto_index` is True if `frappe_search_doctypes` is not set, and `False` if it is. If a doctype has the property `index_web_pages_for_search`, it will be indexed with the title field `doctype_obj.title_field` if set, or `name`; and content fields being all the doctype fields that have `in_global_search` checked.

#### License

mit