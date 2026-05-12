"""Minimal Chinese bitmap font rendering for Camera Test.

Format:
- Chinese glyph: 16x16, 1bpp, 32 bytes per glyph, row-major.
- Bit value 1 = draw pixel, 0 = transparent.
- In each byte, bit7 is left-most pixel, bit0 is right-most pixel.
"""

ZH16_W = 16
ZH16_H = 16
ZH16_BYTES = 32


def _rows16_to_bytes(rows):
    out = bytearray()
    i = 0
    while i < len(rows):
        v = int(rows[i]) & 0xFFFF
        out.append((v >> 8) & 0xFF)
        out.append(v & 0xFF)
        i += 1
    return bytes(out)


# 16x16 glyphs (minimal readable forms for Camera Test).
_GLYPH_ZH = {
    "幀": _rows16_to_bytes(
        (
            0b0001000010000000,
            0b1111111111111100,
            0b0010000010000100,
            0b1111111111111100,
            0b0010001010000000,
            0b0011111111111000,
            0b0010001010001000,
            0b0011111111111000,
            0b0010001010001000,
            0b0011111111111000,
            0b0010001010001000,
            0b0011111111111000,
            0b0010000010001000,
            0b0010000010001000,
            0b1111111111111110,
            0b0000000000000000,
        )
    ),
    "數": _rows16_to_bytes(
        (
            0b0010001000100000,
            0b1111111111111000,
            0b0010001000100000,
            0b0011111111100000,
            0b0000100010000000,
            0b1111111111111000,
            0b0000100010000000,
            0b0111111111110000,
            0b0100100100100000,
            0b0111111111110000,
            0b0100100100100000,
            0b0111111111110000,
            0b0100100100100000,
            0b0100000000100000,
            0b1111111111111100,
            0b0000000000000000,
        )
    ),
}


# 5x7 digits, each row uses low 5 bits.
_DIGIT_5X7 = {
    "0": (0x0E, 0x11, 0x13, 0x15, 0x19, 0x11, 0x0E),
    "1": (0x04, 0x0C, 0x04, 0x04, 0x04, 0x04, 0x0E),
    "2": (0x0E, 0x11, 0x01, 0x02, 0x04, 0x08, 0x1F),
    "3": (0x1E, 0x01, 0x01, 0x0E, 0x01, 0x01, 0x1E),
    "4": (0x02, 0x06, 0x0A, 0x12, 0x1F, 0x02, 0x02),
    "5": (0x1F, 0x10, 0x1E, 0x01, 0x01, 0x11, 0x0E),
    "6": (0x06, 0x08, 0x10, 0x1E, 0x11, 0x11, 0x0E),
    "7": (0x1F, 0x01, 0x02, 0x04, 0x08, 0x08, 0x08),
    "8": (0x0E, 0x11, 0x11, 0x0E, 0x11, 0x11, 0x0E),
    "9": (0x0E, 0x11, 0x11, 0x0F, 0x01, 0x02, 0x0C),
    ",": (0x00, 0x00, 0x00, 0x00, 0x00, 0x04, 0x08),
    "-": (0x00, 0x00, 0x00, 0x1F, 0x00, 0x00, 0x00),
}


def _set_px565(buf, buf_w, buf_h, x, y, color565):
    if x < 0 or y < 0 or x >= buf_w or y >= buf_h:
        return
    off = ((y * buf_w) + x) * 2
    buf[off] = color565 & 0xFF
    buf[off + 1] = (color565 >> 8) & 0xFF


def _draw_zh16(buf, buf_w, buf_h, x, y, glyph, color565):
    gy = 0
    while gy < ZH16_H:
        row_hi = glyph[gy * 2]
        row_lo = glyph[gy * 2 + 1]
        row_bits = ((row_hi << 8) | row_lo) & 0xFFFF
        gx = 0
        while gx < ZH16_W:
            if (row_bits >> (15 - gx)) & 0x01:
                _set_px565(buf, buf_w, buf_h, x + gx, y + gy, color565)
            gx += 1
        gy += 1


def _draw_digit_5x7(buf, buf_w, buf_h, x, y, digit, color565):
    rows = _DIGIT_5X7.get(digit)
    if rows is None:
        return
    ry = 0
    while ry < 7:
        bits = rows[ry] & 0x1F
        rx = 0
        while rx < 5:
            if (bits >> (4 - rx)) & 0x01:
                _set_px565(buf, buf_w, buf_h, x + rx, y + ry, color565)
            rx += 1
        ry += 1


def draw_text_to_buf(buf, buf_w, buf_h, x, y, text, color565):
    cx = int(x)
    cy = int(y)
    s = str(text)
    i = 0
    while i < len(s):
        ch = s[i]
        glyph = _GLYPH_ZH.get(ch)
        if glyph is not None:
            _draw_zh16(buf, buf_w, buf_h, cx, cy, glyph, color565)
            cx += 17
        elif ch in _DIGIT_5X7:
            _draw_digit_5x7(buf, buf_w, buf_h, cx, cy + 5, ch, color565)
            cx += 6
        else:
            cx += 6
        i += 1


def get_digits_text_width(text):
    s = str(text)
    w = 0
    i = 0
    while i < len(s):
        ch = s[i]
        if ch in _DIGIT_5X7:
            w += 6
        else:
            w += 6
        i += 1
    return w


def draw_digits_to_buf(buf, buf_w, buf_h, x, y, text, color565):
    cx = int(x)
    cy = int(y)
    s = str(text)
    i = 0
    while i < len(s):
        ch = s[i]
        if ch in _DIGIT_5X7:
            _draw_digit_5x7(buf, buf_w, buf_h, cx, cy, ch, color565)
        cx += 6
        i += 1
