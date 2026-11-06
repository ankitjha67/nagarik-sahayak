#!/usr/bin/env python3
"""Populate identity fingerprints for users who predate the index.

Run from the backend/ directory:

    python scripts/backfill_identity_index.py --dry-run   # report, change nothing
    python scripts/backfill_identity_index.py             # only missing users
    python scripts/backfill_identity_index.py --all       # recompute everything

When to run this:

* Once after deploying the fingerprint index, so users who registered earlier
  are covered. Until then, cross-applicant fraud checks simply return no match
  for them — a silent loss of signal, not an error, which is exactly the kind of
  gap worth closing deliberately.
* After rotating IDENTITY_HASH_SALT, with --all. Every stored digest is derived
  from that key, so rotating it invalidates all of them at once and shared-
  identifier detection stops matching until they are recomputed.
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _profile_of(user) -> dict:
    """Merge a user's extended and basic profiles, preferring the extended one.

    Routed through profile_store so this reads encrypted rows too — otherwise
    the backfill would silently compute fingerprints from ciphertext.
    """
    from dpdp import profile_store
    return profile_store.load(user)


async def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true",
                    help="Report what would change without writing")
    ap.add_argument("--all", action="store_true",
                    help="Recompute every user, not only those missing digests "
                         "(required after a salt rotation)")
    args = ap.parse_args()

    import identity_index
    from database import prisma

    await prisma.connect()
    try:
        users = await prisma.user.find_many()
        print(f"{len(users)} users in the database")

        updated = skipped = cleared = 0
        for user in users:
            profile = _profile_of(user)
            desired = identity_index.fingerprints_for(profile)

            current = {c: getattr(user, c, None) or "" for c in desired}
            if not args.all and current == desired:
                skipped += 1
                continue
            # With --all we rewrite regardless; without it we only touch users
            # whose stored digests disagree with a fresh computation.
            if current == desired:
                skipped += 1
                continue

            has_any = any(desired.values())
            if not has_any and not any(current.values()):
                skipped += 1
                continue

            if args.dry_run:
                changed = [c for c in desired if current[c] != desired[c]]
                print(f"  would update {user.id}: {', '.join(changed)}")
            else:
                await prisma.user.update(where={"id": user.id}, data=desired)
            updated += 1
            if not has_any:
                cleared += 1

        verb = "would update" if args.dry_run else "updated"
        print(f"\n{verb} {updated}, unchanged {skipped}"
              + (f", of which {cleared} had no identifiers to index" if cleared else ""))
        if args.dry_run:
            print("Dry run — nothing was written.")
        return 0
    finally:
        await prisma.disconnect()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
