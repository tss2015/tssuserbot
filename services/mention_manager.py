import html


def mention(user) -> str:
    name = user.first_name or user.username or "user"
    name = html.escape(str(name), quote=False)
    return f'<a href="tg://user?id={user.id}">{name}</a>'


def batches(items, size=5):
    size = max(1, int(size))
    for i in range(0, len(items), size):
        yield items[i:i + size]
