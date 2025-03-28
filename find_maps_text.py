#!/usr/bin/env python3

import sys

import easyocr
import fitz


def main(argv):
    maps_filename = argv[1]
    ocr = easyocr.Reader(["en"])

    doc = fitz.open(maps_filename)
    for page in doc.pages(7, doc.page_count):
        (xref, *_) = page.get_images()[0]
        image_info = doc.extract_image(xref)
        image_bytes = image_info["image"]
        extension = image_info["ext"]

        with open(f"{page.number}.{extension}", "wb") as f:
            f.write(image_bytes)

        result = ocr.readtext(image_bytes)

        for [[x0, y0], _, [x1, y1], _], word, _ in result:
            print(f"{page.number},{word.replace(',', '_')},{x0},{y0},{x1},{y1}")


if __name__ == "__main__":
    main(sys.argv)
