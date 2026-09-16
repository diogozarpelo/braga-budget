def escape_like(value):
    return (
        value.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )


def normalize_comparison_text(value):
    return " ".join((value or "").split()).casefold()


def phone_digits(value):
    return "".join(
        character
        for character in (value or "")
        if character.isdigit()
    )
