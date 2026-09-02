"""Know Your Customer / identity verification.

Layout:
    methods.py          — what methods exist, what each proves, and whether this
                          deployment can actually run it
    matching.py         — comparing a claimed identity against a verified one,
                          tolerantly and in one direction only
    aadhaar_offline.py  — UIDAI offline e-KYC XML and Secure QR, the only
                          high-assurance route available without a licence
    service.py          — orchestration; produces evidence, never a decision

The design constraint the whole package answers: identity verification in a
welfare context must be able to *admit* automatically and must never *refuse*
automatically, because every automated check here fails hardest on the people
the schemes exist for.
"""
from kyc.methods import (  # noqa: F401
    Assurance, Availability, Channel, KycMethod, available_methods, options,
)
