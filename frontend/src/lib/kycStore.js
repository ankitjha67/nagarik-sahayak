// Where a citizen's identity-check results live between screens.
//
// The backend is deliberately stateless about these: persisting a verification
// history server-side would create a second store of identity evidence to
// protect, on top of the profile. So the caller holds them, and "the caller"
// is this browser.
//
// **Only the verdict is stored, never the evidence.** A VerificationOutcome
// comes back carrying `established` (the name, date of birth and address read
// out of the document) and `matches` (a field-by-field comparison). None of
// that is needed to make a decision — the gate reads the assurance level and
// the fraud signal — so none of it is written to disk. Putting a citizen's
// demographics into localStorage would spread personal data onto a device the
// application does not control, for no gain.

const KEY = "ns_kyc_outcomes";

// Exactly the fields the gate reads. Anything else is dropped on the way in,
// so a future change to the outcome shape cannot silently start persisting
// personal data.
const PERSISTED_FIELDS = [
  "method",
  "succeeded",
  "assurance",
  "assuranceLabel",
  "contradicted",
  "needsReview",
  "fraudSignal",
  "verifiedAt",
];

function strip(outcome) {
  const out = {};
  for (const field of PERSISTED_FIELDS) {
    if (outcome[field] !== undefined) out[field] = outcome[field];
  }
  return out;
}

export function loadKycOutcomes() {
  try {
    const raw = localStorage.getItem(KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    // Private windows, cleared site data, or a browser set to block storage.
    // An empty list is the correct answer in every one of those cases: it
    // means "no checks recorded", which is a normal, lawful state.
    return [];
  }
}

export function saveKycOutcome(outcome) {
  if (!outcome || !outcome.succeeded) return loadKycOutcomes();
  try {
    const next = [...loadKycOutcomes(), strip(outcome)];
    localStorage.setItem(KEY, JSON.stringify(next));
    return next;
  } catch {
    return loadKycOutcomes();
  }
}

export function clearKycOutcomes() {
  try {
    localStorage.removeItem(KEY);
  } catch {
    /* nothing to do; the caller cannot act on this either */
  }
}
