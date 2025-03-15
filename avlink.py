#!/usr/bin/env python3

import sys

from pypdf import PdfReader


def main(args):
    print(args)
    input_filename = args[1]

    reader = PdfReader(input_filename)

    print(f"Number of pages: {len(reader.pages)}")

    page = reader.pages[0]
    text = page.extract_text()
    print(f"First page text: {text}")


if __name__ == "__main__":
    main(sys.argv)
