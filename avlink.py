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
    print(toc)


if __name__ == "__main__":
    main(sys.argv)
