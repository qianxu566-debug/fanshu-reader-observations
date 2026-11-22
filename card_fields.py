import json


def book_tags(book):
    categories = book.get("categoryV2")
    if isinstance(categories, str):
        try:
            categories = json.loads(categories)
        except ValueError:
            return None
    if not isinstance(categories, list):
        return None
    return list(dict.fromkeys(
        c["Name"] for c in categories
        if isinstance(c, dict) and c.get("MainCategory") is False
        and isinstance(c.get("Name"), str) and c["Name"]
    ))
