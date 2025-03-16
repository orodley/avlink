#!/usr/bin/env python3

import re
import sys
from pprint import pprint as pp

import fitz


def main(args):
    if len(args) != 2:
        print("Usage: avlink.py <input_filename>")
        sys.exit(1)
    input_filename = args[1]
    output_filename = input_filename.replace(".pdf", "_linked.pdf")

    doc = fitz.open(input_filename)

    link_targets = get_link_targets(doc)
    if not link_targets:
        exit(f"No table of contents found in {input_filename}")
    pp(link_targets)
    print(f"{len(link_targets)} targets found")

    links_added = 0

    # NOTE: For testing, just look at this one page.
    for page_idx in range(88, 89):
        page = doc[page_idx]

        for (x0, y0, x1, y1, word, *_) in page.get_text("words", delimiters="(),"):
            if target_page := link_targets.get(word):
                add_link(page, word, fitz.Rect(x0, y0, x1, y1), target_page)
                links_added += 1

    doc.ez_save(args.output_filename)
    doc.close()

    print(f"Added {links_added} links")
    print(f"Saved to {output_filename}")


def get_link_targets(doc):
    toc = doc.get_toc()
    if not toc:
        return None

    link_targets = {}
    for (_, title, page_num, *_) in toc:
        title = title.strip()
        short_name = extract_short_name(title)
        if short_name:
            link_targets[short_name] = page_num

    # This one is missing from the table of contents.
    # TODO: We could find missing ones automatically -- we have TS-5 and TS-7.
    link_targets["TS-6"] = 113

    return link_targets


def add_link(page, short_name, rect, target_page):
    link = {
        "kind": fitz.LINK_GOTO,
        "from": rect,
        "page": target_page,
    }
    page.insert_link(link)

    # Add an underline to indicate the presence of the link.

    # Unlike the PDF coordinate system, MuPDF has y=0 at the top of the page,
    # increasing towards the bottom.
    underline_rect = fitz.Rect(rect.x0, rect.y1 - 2.5, rect.x1, rect.y1 - 2.0)
    page.draw_rect(underline_rect, color=(0, 0, 0.8), width=0.5, fill=(0, 0, 0.8, 1.0))

    print(f"Added link at {rect} for '{short_name}'")


def extract_short_name(title):
    # For now this is just area keys.
    #
    # Area keys all have the format: "X-n: Name", where X is the short name for
    # the level and n is the room/area number.
    #
    # Level names are usually just a number, or "SLn" for sublevels, and a few
    # other special cases like "AV" for the ruined city.
    #
    # Room/area numbers are just numbers, up to three digits.
    #
    # Both level names and room/area numbers sometimes have a capital letter
    # suffix, like "SL10A" or "187B".
    match = re.match(
        r"""(?x)
        ^(
           (
             \d{1,2}         |
             SL\d{1,2}[A-Z]? |
             AV|EX|UP|TS
           )-(\d{1,3})[A-Z]?
        ):.*$""",
        title,
    )

    # TODO:  Extract other stuff:
    #   * Monsters
    #   * Items
    #   * Flora
    #   * Spells
    #   * Books
    #   * NPCs

    if match:
        return match.group(1)


def exit(message):
    print(message, file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main(sys.argv)
