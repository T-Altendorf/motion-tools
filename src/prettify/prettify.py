from sty import bg, fg, rs


def colorize(text, colorHex):
    """Colorize text with given colorHex"""
    # convert hex to rgb
    r = int(colorHex[1:3], 16)
    g = int(colorHex[3:5], 16)
    b = int(colorHex[5:7], 16)
    return fg(r, g, b) + text + rs.all
