#!/usr/bin/env python3

import sys

import fitz


def main(args):
    if len(args) != 2:
        print("Usage: avlink.py <input_filename>")
        sys.exit(1)
    input_filename = args[1]

    doc = fitz.open(input_filename)
    toc = doc.get_toc()
    if not toc:
        exit(f"No table of contents found in {input_filename}")

    for (level, title, page_num, *_) in toc:
        title = title.strip()
        print(f"{(level - 1) * ' '}'{title}' {page_num}")


def exit(message):
    print(message, file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main(sys.argv)
