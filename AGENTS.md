# Project notes

`enex2writer` is deliberately dependency-free at runtime. The converter reads
Evernote ENEX locally, writes ordinary UTF-8 Markdown and an `assets/` folder,
and never performs network requests. The design and the safety boundaries are
documented in [`docs/design.md`](docs/design.md).

Keep migration output outside the repository. ENEX files and their extracted
attachments may contain private information; the default `.gitignore` protects
them from accidental commits.
