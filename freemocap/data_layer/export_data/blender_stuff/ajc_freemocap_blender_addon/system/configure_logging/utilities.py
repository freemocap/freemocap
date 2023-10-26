def ensure_min_brightness(value, threshold=50):
    """Ensure the RGB value is above a certain threshold."""
    return max(value, threshold)


def ensure_not_grey(r, g, b, threshold_diff=100):
    """Ensure that the color isn't desaturated grey by making one color component dominant."""
    max_val = max(r, g, b)
    if (
            abs(r - g) < threshold_diff
            and abs(r - b) < threshold_diff
            and abs(g - b) < threshold_diff
    ):
        if max_val == r:
            r = 255
        elif max_val == g:
            g = 255
        else:
            b = 255
    return r, g, b


def get_hashed_color(value):
    """Generate a consistent random color for the given value."""
    # Use modulo to ensure it's within the range of normal terminal colors.
    hashed = hash(value) % 0xFFFFFF  # Keep within RGB 24-bit color
    red = ensure_min_brightness(hashed >> 16 & 255)
    green = ensure_min_brightness(hashed >> 8 & 255)
    blue = ensure_min_brightness(hashed & 255)

    red, green, blue = ensure_not_grey(red, green, blue)

    return "\033[38;2;{};{};{}m".format(red, green, blue)
