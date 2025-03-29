# avlink

`avlink` is a Python script which adds hyperlinks to a _Halls of Arden Vul_ PDF.
It scans the document for references to areas, entities, and other elements, and
creates clickable links to their respective locations within the PDF.

It doesn't work perfectly -- text like "1-4" is ambiguous as it could be a
reference to area 1-4, or it could be a range of numbers used for some other
purpose. The script does its best to figure this out from context, but it
doesn't always get it right.

It contains no material from _Halls of Arden Vul_ beyond a few words and short
phrases used to locate entries and disambiguate references. You must already
own the PDF for this script to do anything. You can purchase a copy from
[DriveThruRPG](https://www.drivethrurpg.com/en/product/307320/the-halls-of-arden-vul-complete).

Note that this script was designed to work on the complete document which
compiles all volumes. I do not have the individual volumes so cannot test
whether it works on them. At any rate, the combined document would work much
better as there are numerous links between volumes.

## How to use

If you're comfortable with the command line and using Python:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
./avlink.py --help
```

If you're not, and you're running Windows, you can download an executable from
the Releases section of this repository. Once obtained you can drag your PDF
onto the `avlink.exe` executable, and it will create the linked PDF for you.
