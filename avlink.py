#!/usr/bin/env python3

import argparse
import re
import sys
from pprint import pprint as pp

import fitz


def main(argv):
    parser = argparse.ArgumentParser(
        description="Add links to a PDF of 'Halls of Arden Vul'"
    )
    parser.add_argument("input_filename", help="The input PDF filename. Required.")
    parser.add_argument(
        "output_filename",
        help="The output PDF filename. If not provided, defaults to <input_filename>_linked.pdf",
        nargs="?",
    )
    parser.add_argument(
        "-v", "--verbose", help="Print detailed information", action="store_true"
    )
    parser.add_argument(
        "-u",
        "--uncompressed",
        help="Save the output PDF uncompressed",
        dest="compressed",
        action="store_false",
    )

    args = parser.parse_args(argv[1:])
    if not args.output_filename:
        args.output_filename = args.input_filename.replace(".pdf", "_linked.pdf")
    global VERBOSE
    VERBOSE = args.verbose

    doc = fitz.open(args.input_filename)

    link_targets = get_link_targets(doc)
    if not link_targets:
        exit(f"No table of contents found in {args.input_filename}")

    vprint(f"{len(link_targets)} link targets found")

    links_added = 0

    for page in doc.pages():
        # Delimiters are carefully chosen to only capture cases where we want to
        # add links.
        # * We omit ":", because the section headers have colons after the name
        #   and we don't want to link a section header to itself.
        # * We omit "/" because monster damage is formatted like "1-4/1-4",
        #   which looks like a link to area 1-4 if we split on "/".
        for (x0, y0, x1, y1, word, *_) in page.get_text("words", delimiters="()[],.;"):
            # TODO: It may be necessary to also include context around the word.
            # There are cases like "Levels 5-8", "Dmg 2-8", "1-4 HP", "4-5 turns",
            # and "1-3 hours" which we erroneously link to an area.
            if target_page := link_targets.get(word):
                add_link(page, word, fitz.Rect(x0, y0, x1, y1), target_page)
                links_added += 1
    vprint(f"Added {links_added} links")

    vprint(f"Saving to {args.output_filename}")
    if args.compressed:
        doc.ez_save(args.output_filename)
    else:
        doc.save(args.output_filename)
    doc.close()


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

    vprint(f"Added link at {rect} for '{short_name}'")


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
        )
        (: | ) # Most area names have a colon after the key, but not all.
        .*$""",
        title,
    )

    # TODO:  Extract other stuff:
    #   * Monsters
    #   * Items
    #   * Flora
    #   * Spells
    #   * Books
    #   * NPCs
    #   * Tables (these are local to the section and not in the ToC)
    #   * Chapters (e.g. link "UP" to the top-level "Pyramid of Thoth" section,
    #     or "Level 1" to the top-level "The Basement" section)

    if match:
        return match.group(1)


VERBOSE = None


def vprint(*args, **kwargs):
    if VERBOSE:
        print(*args, **kwargs)


def exit(message):
    print(message, file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main(sys.argv)
