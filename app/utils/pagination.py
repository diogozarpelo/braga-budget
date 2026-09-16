from flask import request


def get_pagination(total_count, per_page):
    page = request.args.get("page", default=1, type=int) or 1
    page = max(page, 1)
    total_pages = max(
        1,
        (total_count + per_page - 1) // per_page,
    )
    page = min(page, total_pages)
    offset = (page - 1) * per_page

    return page, total_pages, offset
