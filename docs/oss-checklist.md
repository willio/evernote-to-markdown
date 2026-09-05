# OSS release checklist

This checklist records the repository contents verified for the initial public
push. It is a source-repository checklist, not a substitute for reviewing the
contents of a real export before conversion.

## Project and licensing

- [x] Clear project name: `enex2writer`.
- [x] MIT `LICENSE` included.
- [x] `pyproject.toml` declares package metadata, Python support, and the CLI entry point.
- [x] No runtime dependencies are declared.
- [x] `.gitignore` excludes private ENEX exports and generated migration output.

## User documentation

- [x] README explains the Evernote Desktop export prerequisite.
- [x] README includes installation, CLI/module usage, dry-run, and overwrite behavior.
- [x] README documents output layout, metadata, links, attachments, limitations, and tests.
- [x] Design notes capture non-obvious conversion and safety decisions.
- [x] Contribution and security guidance are included.

## Engineering and community health

- [x] Standard-library tests cover content, metadata, assets, links, dry-run, and overwrite protection.
- [x] GitHub Actions CI runs tests and builds a wheel on supported Python versions.
- [x] Bug and feature issue templates are included.
- [x] Pull-request checklist is included.
- [x] Maintainer command/architecture notes are included in `CLAUDE.md`.

## Sanitization gate

- [x] No `.env`, private key, credential file, or certificate file is present.
- [x] No personal absolute filesystem path is present.
- [x] No private project-internal reference is present.
- [x] The sample ENEX contains synthetic content only.
- [x] ZIP contents were inspected and contain source files only.

## Post-push GitHub settings

After the first push, the repository owner should confirm the GitHub-level
description, topics, default branch, vulnerability-reporting setting, and
branch protection policy. Those settings are outside the Git object itself.
