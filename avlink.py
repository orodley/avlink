#!/usr/bin/env python3

import argparse
import pprint
import re
import sys
import traceback
from collections import defaultdict
from pathlib import Path
from pprint import pprint as pp

import fitz


def main(argv):
    parser = argparse.ArgumentParser(
        description="Add links to a PDF of 'Halls of Arden Vul'"
    )
    parser.add_argument("input_filename", help="The input PDF filename. Required.")
    parser.add_argument(
        "--maps_filename",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "-v", "--verbose", help="Print detailed information", action="store_true"
    )
    parser.add_argument(
        "--print-link-targets",
        help=argparse.SUPPRESS,
        action="store_true",
    )
    parser.add_argument(
        "-p",
        "--page",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--overwrite",
        help="If true, the output file will be overwritten if it exists.",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "--no-entities",
        help="By default, links are generated for areas and also for various"
        + "entities such as monsters, items, etc. If this flag is passed, "
        + "links are only added for areas.",
        dest="link_entities",
        action="store_false",
    )
    parser.add_argument(
        "--maps-only",
        help=argparse.SUPPRESS,
        action="store_true",
        default=False,
    )

    args = parser.parse_args(argv[1:])
    output_filename = args.input_filename.replace(".pdf", "_linked.pdf")
    global VERBOSE
    VERBOSE = args.verbose

    doc = fitz.open(args.input_filename)

    link_targets = get_link_targets(doc, args.link_entities)
    if not link_targets:
        exit(f"No table of contents found in {args.input_filename}")

    vprint(f"{len(link_targets)} link targets found")

    if args.print_link_targets:
        print(link_targets)
        return

    links_added = 0
    if not args.maps_only:
        if args.page:
            page = int(args.page) - 1
            pages = doc.pages(page, page + 1)
        else:
            pages = doc.pages()
        for page in pages:
            if not args.verbose:
                print(f"\rAdding links to page {page.number + 1}", end="")
            for word, rect, target_page in find_references(
                page, link_targets, args.link_entities
            ):
                add_link(page, word, rect, target_page)
                links_added += 1
        if not args.verbose:
            print("")
        print(f"Added {links_added} links")
        vprint(f"Excluded {DIE_RANGES_EXCLUDED} die ranges")

    if args.maps_filename:
        vprint(f"Loading maps from {args.maps_filename}")
        maps_doc = fitz.open(args.maps_filename)
        add_maps_links(doc, maps_doc, link_targets)

    print(f"Saving to '{output_filename}'. This may take a few minutes.")
    if not args.overwrite and Path(output_filename).exists():
        exit(
            f"Output file {output_filename} already exists. Use --overwrite to replace it."
        )
    doc.save(output_filename, deflate=True, garbage=2, use_objstms=True)
    doc.close()


def get_link_targets(doc, link_entities):
    toc = doc.get_toc()
    if not toc:
        return None

    curr_section = None
    link_targets = {}
    for (level, title, page_num, *_) in toc:
        # The table of contents has a 1-based page number, but we want 0-based.
        page_num -= 1
        title = title.strip().replace("\r", "")

        if level == 1:
            curr_section = title

        if (
            link_entities
            and level == 2
            and curr_section
            in {
                "New Monsters",
                "New Magic Items",
                "New Technological Items",
                "Arden Vul Items",
                "New Flora",
                "New Spells",
                "Arden Vul Books",
            }
        ):
            # The ToC entries sometimes have the ':' still on the end.
            title.removesuffix(":")
            title = title.lower()

            forms = [title]
            if title.endswith(", The"):
                forms.append(f"The {title[:-5]}")
            s = title.split(" ")
            # Transform "skeleton, black" into "black skeleton"
            if len(s) >= 2 and s[-2].endswith(","):
                forms.append(" ".join([s[-1]] + s[:-2] + [s[-2][:-1]]))

            # This is just a rough approximation. Doing this in full generality
            # is very tricky. There are lots of cases we don't handle, like
            # irregular plural forms other than "y"->"ies", or cases where the
            # plural doesn't apply on the end ("X of Y" -> "Xs of Y").
            plural_and_singles = []
            for form in forms:
                plural_and_singles.append(form + "s")
                if form.endswith("y"):
                    plural_and_singles.append(form[:-1] + "ies")
                if form.endswith("s"):
                    plural_and_singles.append(form[:-1])
            forms.extend(plural_and_singles)

            for form in forms:
                link_targets[form] = page_num
        elif short_name := extract_short_name(title):
            link_targets[short_name] = page_num

    # Add areas that are missing from the table of contents.
    # Some areas with letters on the end don't contain an entry for the area
    # as a whole, but do contain references to the area. We point these at
    # the first of the sub-areas.
    # Note that these are 0-based page numbers, so won't line up with what you
    # see when you open the PDF in a viewer.
    # TODO: Maybe we could add them to the table of contents also?
    link_targets |= {
        # "AV-3 & AV-4", we only match to "AV-3".
        "AV-4": link_targets["AV-3"],
        "2-13": 126,
        "2-36A": link_targets["2-36"],
        "2-36B": link_targets["2-36"],
        "2-36C": link_targets["2-36"],
        "2-36D": link_targets["2-36"],
        "2-36E": link_targets["2-36"],
        "3-36": link_targets["3-36A"],
        "3-52A": link_targets["3-53"],
        # "3-101 through 3-103", we only match to "3-101".
        "3-102": link_targets["3-101"],
        "3-103": link_targets["3-101"],
        "3-146": 210,
        "3-147": 210,
        "3-172": 220,
        "4-8": link_targets["4-8A"],
        "4-99": 285,
        "4-112": link_targets["4-112A"],
        "4-120": 290,
        "4-138": link_targets["4-138A"],
        "4-139": link_targets["4-139A"],
        "5-75": 348,
        "6-6": link_targets["6-6A"],
        "6-20": 393,
        "6-68": 415,
        "6-99": 425,
        "7-40": 468,
        "7-76": link_targets["7-76A"],
        "8-69": 539,
        "9-10": 584,
        "9-33": 591,
        "SL1-6": 658,
        "SL6-46": 745,
        "SL7-22": 771,
        "SL8-14": 781,
        "SL9-28": 792,
        "SL9-76": 804,
    }

    # Scan through the link targets to find missing areas. We infer that if
    # there is an area X-n, there should also be an area X-(n-1) as long as
    # n>1, and an area X-(n+1) as long as we have X-(n+2).
    missing = set()
    for short_name in sorted(link_targets.keys()):
        pat = r"(^[A-Z]*\d*[A-Z]*-)(\d+)(.*$)"
        match = re.match(pat, short_name)
        if not match:
            continue
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


DIE_RANGES_EXCLUDED = 0


def find_references(page, link_targets, link_entities):
    # Delimiters are carefully chosen to only capture cases where we want to
    # add links.
    # * We omit ":", because the section headers have colons after the name
    #   and we don't want to link a section header to itself.
    # * We omit "/" because monster damage is formatted like "1-4/1-4",
    #   which looks like a link to area 1-4 if we split on "/". There are
    #   some instances where we have legimate links separated by "/"s.
    #   Perhaps we should handle this through context instead...
    words = []
    for (x0, y0, x1, y1, word, *_) in page.get_text("words", delimiters="()[],.;"):
        if (
            words
            and any(y0 > last_word_y0 for (_, last_word_y0, _, _) in words[-1][1])
            and words[-1][0].endswith("-")
        ):
            # If the last word ended with a hyphen and is further up the page,
            # it's likely that the two are actually one word, split over the
            # line break. We merge them, but keep the hyphen. References all
            # contain hyphens and are most likely split at that point, so we
            # want to keep it. If it's not a reference then maybe the original
            # word didn't contain a hyphen, but we don't really care because
            # it's not a reference.
            words[-1] = (words[-1][0] + word, words[-1][1] + [(x0, y0, x1, y1)])
        else:
            words.append((word, [(x0, y0, x1, y1)]))

    die_ranges = []
    links = []
    for i in range(len(words)):
        word, rects = words[i]

        if len(rects) == 1 and (r := die_range(word)):
            die_ranges.append((*r, centre(*rects[0])))

        if target_page := link_targets.get(word):
            before, after = (
                words[i - 1][0] if i > 0 else None,
                words[i + 1][0] if i < len(words) - 1 else None,
            )
            if non_ref_pattern(before, after):
                continue
            for rect in rects:
                links.append((word, fitz.Rect(*rect), target_page))

    if link_entities:
        longest = max(len(name.split()) for name in link_targets.keys())
        for i in range(len(words)):
            for j in range(min(len(words), i + longest + 1), i + 1, -1):
                phrase = " ".join(text for (text, _) in words[i:j]).lower()
                if target_page := link_targets.get(phrase):
                    all_rects = []
                    for _, rects in words[i:j]:
                        all_rects.extend(fitz.Rect(*r) for r in rects)
                    for rect in join_rects(all_rects):
                        links.append((phrase, rect, target_page))
                    # We started from the longest possible match, so as soon as we
                    # get one we stop so that we don't have overlapping links.
                    break

    if not links:
        return []

    excluded_points = find_table_entries(die_ranges)

    output = []
    for word, rect, target_page in links:
        if any(rect.contains(excluded_point) for excluded_point in excluded_points):
            global DIE_RANGES_EXCLUDED
            DIE_RANGES_EXCLUDED += 1
        else:
            output.append((word, rect, target_page))
    return output


TABLE_HEADING_PATTERN = re.compile(r"^[dD]\d{1,3}$")


def die_range(word):
    # Special case to handle table headings. This allows this method to work
    # in cases we we only have the header and the next row before reaching
    # the end of the page.
    if re.match(TABLE_HEADING_PATTERN, word):
        # This will match before the start of any real roll table entry
        return (0, 0)

    if all(c.isdigit() for c in word):
        if 1 <= (x := int(word)) <= 100:
            return (x, x)
        return None

    if (
        len((s := word.split("-"))) == 2
        and all(len(x) > 0 for x in s)
        and all(c.isdigit() for x in s for c in x)
    ):
        x, y = map(int, s)
        if 1 <= x < y <= 100:
            return (x, y)
    return None


# This fails in some cases like on p405 where we just so happen to have
# "AC 5" from a previous paragraph directly above a "6-47".
#
# There are also a few known cases where this fails but a table approach
# works. This is because sometimes the entries are left-aligned rather
# than centre-aligned, so we don't detect them as being in a chain.
# These are on pages 124, 293, and 854. Since there's only three, whatever.
def find_table_entries(die_ranges):
    die_ranges.sort(key=lambda x: (x[0], x[1], x[2].y, x[2].x))
    starting_points = {}
    prev = None
    for i, (start, _, _) in enumerate(die_ranges):
        if prev != start:
            starting_points[start] = i
        prev = start

    excluded_points = []
    used = set()
    for i in range(len(die_ranges)):
        if i in used:
            continue

        chain = [i]
        while True:
            _, end, point1 = die_ranges[chain[-1]]
            j = starting_points.get(end + 1)
            if j is None:
                break
            while j < len(die_ranges) and die_ranges[j][0] == end + 1:
                _, _, point2 = die_ranges[j]
                if abs(point2.x - point1.x) < 0.05 and point2.y > point1.y:
                    chain.append(j)
                    break
                j += 1
            else:
                break

        if len(chain) > 1:
            excluded_points.extend(
                die_ranges[j][2] for j in chain if die_ranges[j][0] != die_ranges[j][1]
            )
            for j in chain:
                used.add(j)
    return excluded_points


def non_ref_pattern(before, after):
    prefixes = {"on", "level", "levels", "dmg", "damage"}
    suffixes = {
        "levels",
        "dmg",
        "damage",
        "dagger",
        "flail",
        "mace",
        "crossbow",
        "club",
        "hammer",
        "war",
        "hp",
        "health",
        "cp",
        "sp",
        "gp",
        "pp",
        "silver",
        "gold",
        "platinum",
        "gems",
        "scrolls",
        "keys",
        "magic",
        "curios",
        "specimens",
        "spells",
        "objects",
        "rounds",
        "turns",
        "hours",
        "days",
        "weeks",
        "months",
        "years",
        "light",
        "large",
        "short",
        "long",
        "normal",
        "lesser",
        "male",
        "female",
        "skilled",
        "unskilled",
        "classed",
        "nonclassed",
        "guildsmen",
        "poor",
        "groups",
    }
    if before and canon(before) in prefixes:
        return True
    if after and canon(after) in suffixes:
        return True
    return False


def canon(word):
    return "".join(c for c in word.lower() if c.isalpha())


def join_rects(rects):
    output = [rects[0]]
    for rect in rects[1:]:
        if rect.y1 == output[-1].y1:
            output[-1].x1 = rect.x1
        else:
            output.append(rect)
    return output


def add_maps_links(doc, maps_doc, link_targets):
    toc = maps_doc.get_toc()
    if not toc:
        return

    ocr_data = defaultdict(list)
    for line in open("ocr.csv", "r").readlines():
        s = line.strip().split(",")
        page_no, text, x0, y0, x1, y1 = s
        ocr_data[int(page_no)].append((text, fitz.Rect(x0, y0, x1, y1)))

    to_link = {}
    for (_, title, page_num, *_) in toc:
        title = title.strip().replace("\r", "")
        if m := re.match(r"Level (\d+)", title):
            area_prefix = m.group(1)
        elif m := re.match(r"Sub-Level (\d+[A-Z]?)", title):
            area_prefix = f"SL{m.group(1)}"
        elif ap := {
            "The Cliff Face": "EX",
            "AV - City Ruins": "AV",
            "Under the pyramid of Thoth": "UP",
            "The Tower of Scrutiny": "TS",
        }.get(title):
            area_prefix = ap
        else:
            continue

        # ToC uses a 1-based index, we want 0-based.
        to_link[page_num - 1] = area_prefix

    src_page_nos = []
    for page in maps_doc.pages():
        area_prefix = to_link.get(page.number)
        if not area_prefix:
            continue

        # TODO: Should add to the ToC as well.
        doc.insert_pdf(maps_doc, from_page=page.number, to_page=page.number)
        src_page_nos.append(page.number)

    for i, page in enumerate(doc.pages(-len(src_page_nos))):
        src_page_no = src_page_nos[i]
        area_prefix = to_link.get(src_page_no)

        info = page.get_image_info()[0]
        pp((info["width"], info["height"]))
        pp(page.rect)
        scale_x = page.rect.width / info["width"]
        scale_y = page.rect.height / info["height"]
        pp((scale_x, scale_y))
        for word, rect in ocr_data[src_page_no]:
            if "-" in word:
                full_name = word
            else:
                full_name = f"{area_prefix}-{word}"

            rect.x0 *= scale_x
            rect.x1 *= scale_x
            rect.y0 *= scale_y
            rect.y1 *= scale_y
            if target := link_targets.get(full_name):
                add_link(page, full_name, rect, target)


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

    vprint(
        f"Added link at page {page.number + 1} {rect} -> {target_page + 1} for '{short_name}'"
    )


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
             AK|AV|EX|UP|TS
           )-(\d{1,3})[A-Z]?
        )
        (: | ) # Most area names have a colon after the key, but not all.
        .*$""",
        title,
    )

    if match:
        return match.group(1)

    # TODO:  Extract other stuff:
    #   * NPCs
    #   * Tables (these are local to the section and not in the ToC)
    #   * Chapters (e.g. link "UP" to the top-level "Pyramid of Thoth" section,
    #     or "Level 1" to the top-level "The Basement" section)
    #   * Having numbers on the maps link up would be nice, but this is
    #     challenging because a) the maps are in a separate PDF, and b) the
    #     maps are all images, so we can't extract text from them. We'd have to
    #     merge the maps PDF into this one, and either OCR the maps or manually
    #     add the locations of all the numbers (which sounds like hell so I'm
    #     ruling that one out).


def centre(x0, y0, x1, y1):
    return fitz.Point((x0 + x1) / 2, (y0 + y1) / 2)


VERBOSE = None


def vprint(*args, **kwargs):
    if VERBOSE:
        print(*args, **kwargs)


def exit(message):
    print(message, file=sys.stderr)
    print("Press enter to exit")
    input()
    sys.exit(1)


if __name__ == "__main__":
    try:
        main(sys.argv)
    except Exception as e:
        exit("".join(traceback.format_exception(e)))
