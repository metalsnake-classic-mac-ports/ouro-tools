"""Cut sprites out of a sheet as transparent PNGs at their own size: the
sheet's 1-bit mask (black = drawn) becomes the alpha. For documenting a
game (e.g. a page on The Cutting Room Floor) or checking a frame list.

Usage: python3 -I cut_sprites.py SHEET.png MASK.png OUT.png BOX [BOX ...]
  BOX   left,top,right,bottom (right and bottom exclusive)
Several boxes go into one picture side by side, bottoms aligned, 4 px
apart (e.g. a used frame next to an unused one). Needs Pillow.
"""
import sys

from PIL import Image


def cut(sheet, mask, box):
    a = sheet.crop(box)
    m = mask.crop(box)
    px, mp = a.load(), m.load()
    for y in range(a.height):
        for x in range(a.width):
            if mp[x, y] > 127:
                px[x, y] = (0, 0, 0, 0)
    return a


def row(parts, gap=4):
    w = sum(p.width for p in parts) + gap * (len(parts) - 1)
    h = max(p.height for p in parts)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    x = 0
    for p in parts:
        out.alpha_composite(p, (x, h - p.height))
        x += p.width + gap
    return out


def main():
    if len(sys.argv) < 5:
        sys.exit(__doc__)
    sheet = Image.open(sys.argv[1]).convert("RGBA")
    mask = Image.open(sys.argv[2]).convert("L")
    boxes = [tuple(int(v) for v in b.split(",")) for b in sys.argv[4:]]
    row([cut(sheet, mask, b) for b in boxes]).save(sys.argv[3])


if __name__ == "__main__":
    main()
