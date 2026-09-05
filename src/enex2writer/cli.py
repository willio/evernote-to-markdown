"""Command-line interface for enex2writer."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .converter import ConversionError, convert
from .version import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="enex2writer",
        description="Convert an Evernote ENEX export into iA Writer-friendly Markdown.",
    )
    parser.add_argument("input", type=Path, metavar="INPUT.enex", help="local Evernote ENEX export")
    parser.add_argument("output", type=Path, metavar="OUTPUT_DIR", help="directory for Markdown and assets")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="replace existing generated note, asset, or manifest files",
    )
    parser.add_argument("--no-manifest", action="store_true", help="do not write manifest.json")
    parser.add_argument("--no-frontmatter", action="store_true", help="omit YAML frontmatter")
    parser.add_argument("--dry-run", action="store_true", help="parse and plan without writing files")
    parser.add_argument("-q", "--quiet", action="store_true", help="print only errors")
    parser.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = convert(
            args.input,
            args.output,
            overwrite=args.overwrite,
            write_manifest=not args.no_manifest,
            include_frontmatter=not args.no_frontmatter,
            dry_run=args.dry_run,
        )
    except ConversionError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if not args.quiet:
        action = "would convert" if result.dry_run else "converted"
        manifest = "; manifest.json written" if result.manifest_written else ""
        print(f"{action} {result.note_count} note(s) and {result.asset_count} asset(s) to {result.output_dir}{manifest}")
        for warning in result.warnings:
            print(f"warning: {warning}", file=sys.stderr)
        if result.unresolved_internal_links:
            count = len(result.unresolved_internal_links)
            print(f"warning: {count} unresolved internal Evernote link(s) preserved in the Markdown", file=sys.stderr)
    return 0


__all__ = ["build_parser", "main"]
