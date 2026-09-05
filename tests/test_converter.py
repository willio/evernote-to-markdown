from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from enex2writer import ConversionError, convert  # noqa: E402
from enex2writer.converter import normalize_timestamp  # noqa: E402


PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)
PNG_HASH = hashlib.sha256(PNG_BYTES).hexdigest()
PDF_BYTES = b"%PDF-1.4\nexample attachment\n"
PDF_HASH = hashlib.sha256(PDF_BYTES).hexdigest()


def make_enex() -> str:
    image_data = base64.b64encode(PNG_BYTES).decode("ascii")
    pdf_data = base64.b64encode(PDF_BYTES).decode("ascii")
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<en-export export-date="20260905T000000Z" application="test">
  <note>
    <title>First / note</title>
    <content><![CDATA[<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd">
<en-note>
  <p>Hello <strong>world</strong>.</p>
  <p>Open <a href="evernote:///view/123/1/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/">Second note</a>.</p>
  <ul><li>One</li><li><en-todo checked="true"/>Done</li></ul>
  <en-media hash="{PNG_HASH}" type="image/png" />
  <en-media hash="{PDF_HASH}" type="application/pdf" />
  <en-media hash="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb" type="image/png" />
</en-note>]]></content>
    <created>20240312T093000Z</created>
    <updated>20260701T140500Z</updated>
    <tag>work</tag>
    <tag>idea</tag>
    <note-attributes><note-guid>11111111111111111111111111111111</note-guid><author>Test Author</author></note-attributes>
    <resource>
      <data encoding="base64">{image_data}</data>
      <mime>image/png</mime>
      <hash>{PNG_HASH}</hash>
      <resource-attributes><file-name>photo.png</file-name></resource-attributes>
    </resource>
    <resource>
      <data encoding="base64">{pdf_data}</data>
      <mime>application/pdf</mime>
      <hash>{PDF_HASH}</hash>
      <resource-attributes><file-name>report.pdf</file-name></resource-attributes>
    </resource>
  </note>
  <note>
    <title>Second note</title>
    <content><![CDATA[<en-note><p>A second note.</p><p><a href="evernote:///view/123/1/cccccccccccccccccccccccccccccccc/">Missing target</a></p></en-note>]]></content>
    <created>20240313T093000Z</created>
    <updated>20240313T093000Z</updated>
    <note-attributes><note-guid>aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa</note-guid></note-attributes>
    <resource>
      <data encoding="base64">{image_data}</data>
      <mime>image/png</mime>
      <hash>{PNG_HASH}</hash>
      <resource-attributes><file-name>same-content-different-name.png</file-name></resource-attributes>
    </resource>
  </note>
</en-export>
'''


class ConverterTests(unittest.TestCase):
    def test_metadata_formatting(self) -> None:
        self.assertEqual(normalize_timestamp("20240312T093000Z"), "2024-03-12T09:30:00Z")
        self.assertEqual(normalize_timestamp("20240312T0930001234567Z"), "2024-03-12T09:30:00.123456Z")
        self.assertEqual(normalize_timestamp("already-readable"), "already-readable")

    def test_conversion_preserves_content_metadata_and_assets(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "export.enex"
            destination = root / "Notes"
            source.write_text(make_enex(), encoding="utf-8")

            result = convert(source, destination)

            self.assertEqual(result.note_count, 2)
            self.assertEqual(result.asset_count, 2)
            self.assertTrue((destination / "First - note.md").is_file())
            self.assertTrue((destination / "Second note.md").is_file())
            self.assertTrue((destination / "assets/photo.png").is_file())
            self.assertTrue((destination / "assets/report.pdf").is_file())
            self.assertEqual((destination / "assets/photo.png").read_bytes(), PNG_BYTES)
            self.assertEqual((destination / "assets/report.pdf").read_bytes(), PDF_BYTES)

            first = (destination / "First - note.md").read_text(encoding="utf-8")
            self.assertIn('title: "First / note"', first)
            self.assertIn('created: "2024-03-12T09:30:00Z"', first)
            self.assertIn('  - "work"', first)
            self.assertIn("Hello **world**.", first)
            self.assertIn("[x] Done", first)
            self.assertIn("![photo.png](assets/photo.png)", first)
            self.assertIn("[report.pdf](assets/report.pdf)", first)
            self.assertIn("[Second note](Second%20note.md)", first)
            self.assertIn("[Missing Evernote attachment: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb]", first)
            self.assertIn("\n![photo.png](assets/photo.png)", first)

            manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["format"], "enex2writer-manifest-v1")
            self.assertEqual(len(manifest["notes"]), 2)
            self.assertEqual(len(manifest["unresolved_internal_links"]), 1)
            self.assertIn("cccccccccccccccccccccccccccccccc", manifest["unresolved_internal_links"][0]["href"])

    def test_dry_run_does_not_write_and_existing_notes_are_protected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "export.enex"
            destination = root / "Notes"
            source.write_text(make_enex(), encoding="utf-8")

            preview = convert(source, destination, dry_run=True)
            self.assertTrue(preview.dry_run)
            self.assertEqual(preview.note_count, 2)
            self.assertFalse(destination.exists())

            convert(source, destination)
            with self.assertRaises(ConversionError):
                convert(source, destination)
            self.assertIn("# First / note", (destination / "First - note.md").read_text(encoding="utf-8"))

    def test_no_frontmatter_and_no_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "export.enex"
            destination = root / "Notes"
            source.write_text(make_enex(), encoding="utf-8")

            result = convert(source, destination, include_frontmatter=False, write_manifest=False)

            self.assertFalse(result.manifest_written)
            self.assertFalse((destination / "manifest.json").exists())
            self.assertTrue((destination / "First - note.md").read_text(encoding="utf-8").startswith("# First / note\n"))


if __name__ == "__main__":
    unittest.main()
