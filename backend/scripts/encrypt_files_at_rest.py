#!/usr/bin/env python3
"""Encrypt generated documents already on disk.

Run from the backend/ directory:

    python scripts/encrypt_files_at_rest.py --dry-run   # report only
    python scripts/encrypt_files_at_rest.py             # convert plaintext files
    python scripts/encrypt_files_at_rest.py --status    # how much is encrypted

Documents created before encryption was enabled sit in the clear beside the
encrypted database. A filled application form carries the same name, bank
account and income as the row it came from, so leaving them unconverted defeats
the point of encrypting the database at all.

Safe to run on a live system: reads tolerate both forms, so a document is
servable whether or not it has been converted yet. Each file is written to a
temporary path and renamed, so an interrupted run cannot leave a half-written
document.

Uses the same DATA_ENCRYPTION_KEY as the database. After rotating that key, run
scripts/encrypt_at_rest.py --rotate for the database and this script for the
documents; both read old keys from DATA_ENCRYPTION_KEY_OLD during the changeover.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true",
                    help="Report what would change without writing")
    ap.add_argument("--status", action="store_true",
                    help="Report how much of the document store is encrypted")
    args = ap.parse_args()

    from config import AUDIO_DIR, PDF_DIR, UPLOADS_DIR
    from dpdp import crypto, file_vault

    directories = [d for d in (PDF_DIR, AUDIO_DIR, UPLOADS_DIR) if d]

    if args.status:
        st = file_vault.status(directories)
        print(f"encryption enabled : {st['enabled']}")
        print(f"encrypted          : {st['files_encrypted']}")
        print(f"plaintext          : {st['files_plaintext']}")
        print(f"fully encrypted    : {st['fully_encrypted']}")
        if st["warning"]:
            print(f"\n{st['warning']}")
        return 0

    if not crypto.is_enabled():
        print("DATA_ENCRYPTION_KEY is not set (or cryptography is missing).\n"
              "Generate one with:  python scripts/encrypt_at_rest.py --generate-key",
              file=sys.stderr)
        return 1

    converted = already = failed = 0
    for directory in directories:
        path = Path(directory)
        if not path.exists():
            continue
        for entry in sorted(path.iterdir()):
            if not entry.is_file() or entry.name.endswith(".enc-tmp"):
                continue
            if file_vault.is_encrypted(entry):
                already += 1
                continue
            if args.dry_run:
                print(f"  would encrypt {entry.name} ({entry.stat().st_size:,} bytes)")
                converted += 1
                continue
            if file_vault.encrypt_in_place(entry):
                converted += 1
            else:
                # encrypt_in_place logs the cause; one bad file must not stop
                # the rest from being protected.
                print(f"  FAILED {entry.name}", file=sys.stderr)
                failed += 1

    verb = "would encrypt" if args.dry_run else "encrypted"
    print(f"\n{verb} {converted}, already encrypted {already}, failed {failed}")
    if args.dry_run:
        print("Dry run — nothing was written.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
