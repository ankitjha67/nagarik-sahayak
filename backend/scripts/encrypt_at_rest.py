#!/usr/bin/env python3
"""Encrypt existing profile rows at rest, or rotate the encryption key.

Run from the backend/ directory:

    python scripts/encrypt_at_rest.py --generate-key   # make a key, change nothing
    python scripts/encrypt_at_rest.py --dry-run        # report what would change
    python scripts/encrypt_at_rest.py                  # encrypt plaintext rows
    python scripts/encrypt_at_rest.py --rotate         # re-encrypt everything

Reading tolerates a mix of plaintext and ciphertext, so this can run while the
application is live: rows convert incrementally and both forms stay readable
throughout.

Key rotation: set the new key in DATA_ENCRYPTION_KEY and the previous one in
DATA_ENCRYPTION_KEY_OLD, then run with --rotate. Old rows decrypt with the
previous key and are rewritten with the new one. Remove the old key only once
this reports zero remaining.

The key is the data. If DATA_ENCRYPTION_KEY is lost there is no recovery path,
by design — a recovery path would be a second way in. Store it in a secret
manager, never in the repository.
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


async def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true",
                    help="Report what would change without writing")
    ap.add_argument("--rotate", action="store_true",
                    help="Re-encrypt every row with the current key")
    ap.add_argument("--generate-key", action="store_true",
                    help="Print a fresh key and exit")
    args = ap.parse_args()

    from dpdp import crypto

    if args.generate_key:
        print(crypto.generate_key())
        print("\nSet this as DATA_ENCRYPTION_KEY. Back it up in a secret "
              "manager — losing it means losing every stored profile.",
              file=sys.stderr)
        return 0

    if not crypto.is_enabled():
        print("DATA_ENCRYPTION_KEY is not set (or cryptography is missing).\n"
              "Generate one with --generate-key, then set it in the environment.",
              file=sys.stderr)
        return 1

    from database import prisma
    from dpdp import profile_store
    from prisma import Json

    await prisma.connect()
    try:
        users = await prisma.user.find_many()
        print(f"{len(users)} users in the database")

        converted = already = failed = 0
        for user in users:
            full_raw = getattr(user, "fullProfile", None)
            basic_raw = getattr(user, "profile", None)

            full_enc = crypto.is_encrypted(full_raw) if isinstance(full_raw, str) else False
            basic_enc = crypto.is_encrypted(basic_raw) if isinstance(basic_raw, str) else False

            if not args.rotate and full_enc and basic_enc:
                already += 1
                continue
            if not full_raw and not basic_raw:
                already += 1
                continue

            try:
                full = profile_store.load_full(user)
                basic = profile_store.load_basic(user)
            except crypto.DecryptionError as e:
                # Loud, and does not abort the run: one unreadable row should
                # not block converting the rest, but it must be visible.
                print(f"  FAILED {user.id}: {e}", file=sys.stderr)
                failed += 1
                continue

            if args.dry_run:
                state = "rotate" if (full_enc or basic_enc) else "encrypt"
                print(f"  would {state} {user.id} "
                      f"({len(full)} full, {len(basic)} basic fields)")
                converted += 1
                continue

            full_value, _ = profile_store.prepare_full_profile(full)
            basic_value, _ = profile_store.prepare_basic_profile(basic)
            await prisma.user.update(where={"id": user.id}, data={
                "fullProfile": full_value if crypto.is_enabled() else Json(full_value),
                "profile": basic_value,
            })
            converted += 1

        verb = "would convert" if args.dry_run else "converted"
        print(f"\n{verb} {converted}, already encrypted {already}, failed {failed}")
        if args.dry_run:
            print("Dry run — nothing was written.")
        if failed:
            print(f"\n{failed} row(s) could not be decrypted. Check that "
                  f"DATA_ENCRYPTION_KEY_OLD holds the key they were written "
                  f"with.", file=sys.stderr)
        return 1 if failed else 0
    finally:
        await prisma.disconnect()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
