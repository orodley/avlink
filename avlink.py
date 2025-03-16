#!/usr/bin/env python3

import argparse
import pprint
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
    parser.add_argument(
        "--print-link-targets",
        help="Print the link targets and exit. For debugging.",
        action="store_true",
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

    if args.print_link_targets:
        print(link_targets)
        sys.exit(0)

    links_added = 0
    for page in doc.pages():
        # Delimiters are carefully chosen to only capture cases where we want to
        # add links.
        # * We omit ":", because the section headers have colons after the name
        #   and we don't want to link a section header to itself.
        # * We omit "/" because monster damage is formatted like "1-4/1-4",
        #   which looks like a link to area 1-4 if we split on "/". There are
        #   some instances where we have legimate links separated by "/"s.
        #   Perhaps we should handle this through context instead...
        for (x0, y0, x1, y1, word, *_) in page.get_text("words", delimiters="()[],.;"):
            # TODO: It may be necessary to also include context around the word.
            #   There are cases like "Levels 5-8", "Dmg 2-8", "Damage: 1-6",
            #   "1-4 HP", "4-5 turns", and "1-3 hours" which we erroneously link
            #   to an area.
            # TODO: More difficult to deal with are item quantities (e.g.
            #   "1-3 glass beads") and roll tables with die roll ranges in one
            #   column.
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

    # Add areas that are missing from the table of contents.
    # Some areas with letters on the end don't contain an entry for the area
    # as a whole, but do contain references to the area. We point these at
    # the first of the sub-areas.
    # TODO: Maybe we could add them to the table of contents also?
    link_targets |= {
        # "AV-3 & AV-4", we only match to "AV-3".
        "AV-4": link_targets["AV-3"],
        "2-13": 127,
        "3-36": link_targets["3-36A"],
        # "3-101 through 3-103", we only match to "3-101".
        "3-102": link_targets["3-101"],
        "3-103": link_targets["3-101"],
        "3-146": 211,
        "3-147": 211,
        "3-172": 221,
        "4-8": link_targets["4-8A"],
        "4-99": 286,
        "4-112": link_targets["4-112A"],
        "4-120": 291,
        "4-138": link_targets["4-138A"],
        "4-139": link_targets["4-139A"],
        "5-75": 349,
        "6-6": link_targets["6-6A"],
        "6-20": 394,
        "6-68": 416,
        "6-99": 426,
        "7-40": 469,
        "7-76": link_targets["7-76A"],
        "8-69": 540,
        "9-10": 585,
        "9-33": 592,
        "SL1-6": 659,
        "SL6-46": 746,
        "SL7-22": 772,
        "SL8-14": 782,
        "SL9-28": 793,
        "SL9-76": 805,
    }

    # Scan through the link targets to find missing areas. We infer that if
    # there is an area X-n, there should also be an area X-(n-1) as long as
    # n>1, and an area X-(n+1) as long as we have X-(n+2).
    missing = set()
    for short_name in sorted(link_targets.keys()):
        pat = r"(^[A-Z]*\d*[A-Z]*-)(\d+)(.*$)"
        match = re.match(pat, short_name)
        area_num = int(match.group(2))

        prev = re.sub(pat, rf"\g<1>{area_num - 1}\g<3>", short_name)
        next = re.sub(pat, rf"\g<1>{area_num + 1}\g<3>", short_name)
        next_next = re.sub(pat, rf"\g<1>{area_num + 2}\g<3>", short_name)

        # The existence of X-2A implies the existence of X-1, not X-1A.
        if prev[-1].isalpha():
            prev = prev[:-1]
        if next[-1].isalpha():
            next = next[:-1]
        if next_next[-1].isalpha():
            next_next = next_next[:-1]

        if area_num > 1 and prev not in link_targets:
            missing |= {prev}
        if next_next in link_targets and next not in link_targets:
            if link_targets[short_name] == link_targets[next_next]:
                # If n and n+2 are on the same page, n+1 must be on the same
                # page also.
                link_targets[next] = link_targets[next_next]
                vprint(f"Inferred page number of {next} from surrounding areas")
            else:
                missing |= {next}

    if missing:
        vprint("Missing areas:")
        vprint(pprint.pformat(sorted(missing)))

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

    vprint(f"Added link at page {page.number} {rect} for '{short_name}'")


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
