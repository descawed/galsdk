def validate_int(value: str, base: int = 10) -> bool:
    if value == '':
        return True

    try:
        int(value, base)
        return True
    except ValueError:
        return False


def validate_float(value: str) -> bool:
    if value == '':
        return True

    try:
        float(value)
        return True
    except ValueError:
        return False

