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

    add_links(doc, link_targets)
    doc.save(output_filename)
    doc.close()

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

    return link_targets


def add_links(doc, link_targets):
    # NOTE: For testing, just look at this one page.
    for page_idx in range(88, 89):
        page = doc[page_idx]

        text_instances = page.get_text("words")
        pp(text_instances)
        matching = (
            ti
            for ti in text_instances
            if not ti[4].endswith(":")
            and any(short_name in ti[4] for short_name in link_targets.keys())
        )
        pp(list(matching))

        # TODO: This isn't ideal because it's quite slow. Searching through the
        # text_instances manually doesn't work though because each instance can include
        # other text (like opening and closing brackets), so the rect we get doesn't
        # precisely match the text we're looking for.
        #
        # Another option could be `get_text` with appropriate delimiters.
        matches = []
        for short_name, page_no in link_targets.items():
            matches += [
                (short_name, page_no, match) for match in page.search_for(short_name)
            ]
        pp(matches)

        for short_name, page_no, match in matches:
            link = {
                "kind": fitz.LINK_GOTO,
                "from": match,  # The rectangle area to make clickable
                "page": page_no,
            }
            try:
                page.insert_link(link)
            except Exception as e:
                print(f"Error adding link for '{short_name}': {e}")
            else:
                print(f"Added link at {match} for '{short_name}'")

        return


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
