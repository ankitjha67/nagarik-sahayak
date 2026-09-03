import { useCallback, useEffect, useState } from "react";
import { AppHeader } from "../components/AppHeader";
import { BottomNav } from "../components/BottomNav";
import { useLanguage } from "../lib/i18n";
import { loadKycOutcomes, saveKycOutcome } from "../lib/kycStore";
import {
  getKycMethods,
  getKycStatus,
  getProfile,
  recordSelfDeclaration,
  verifyAadhaarOfflineXml,
  verifyAadhaarSecureQr,
} from "../lib/api";
import { toast } from "sonner";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  FileArchive,
  Info,
  Loader2,
  Lock,
  QrCode,
  ShieldCheck,
  UserCheck,
} from "lucide-react";

// Identity verification, presented as what it is: optional, useful, and never a
// gate. Two things this screen must never do —
//
//   * imply that an unverified applicant cannot apply. Under the Aadhaar Act
//     s7 proviso a benefit cannot be refused for want of authentication, and a
//     screen that reads like a checkpoint will turn people away before any rule
//     is ever evaluated;
//   * present an unavailable method as though it worked. Methods needing a
//     UIDAI licence are shown greyed with the reason, because a citizen told by
//     a leaflet to "verify with DigiLocker" deserves to know it is switched off
//     rather than to hunt for a button that does not exist.

const ASSURANCE_STYLE = {
  0: "bg-gray-100 text-gray-700",
  1: "bg-gray-100 text-gray-700",
  2: "bg-blue-100 text-blue-800",
  3: "bg-green-100 text-green-800",
  4: "bg-green-100 text-green-800",
  5: "bg-green-100 text-green-800",
};

const CHANNEL_LABEL = {
  self_offline: "Works without an internet connection",
  self_online: "Needs a phone or computer online",
  assisted: "Done for you at a service centre",
  in_person: "Done in front of an official",
};

function AvailabilityNote({ method }) {
  if (method.usable) return null;
  if (method.availability === "needs_licence") {
    return (
      <p className="text-xs text-gray-600 mt-2">
        Not available here. This needs a UIDAI appointment that this service does
        not hold — it cannot be switched on with a setting.
      </p>
    );
  }
  return (
    <p className="text-xs text-gray-600 mt-2">
      Not switched on here yet
      {method.missingConfig?.length ? ` (missing: ${method.missingConfig.join(", ")})` : ""}.
    </p>
  );
}

function MethodCard({ method, onChoose }) {
  const [open, setOpen] = useState(false);
  return (
    <div
      className={`rounded-xl border p-4 ${
        method.usable ? "border-gray-200 bg-white" : "border-gray-200 bg-gray-50"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="font-semibold text-[15px] leading-snug">{method.name}</h3>
          <p className="text-sm text-gray-600 mt-0.5">{method.nameHindi}</p>
        </div>
        <span
          className={`shrink-0 text-[11px] px-2 py-1 rounded ${
            ASSURANCE_STYLE[method.assurance] || ASSURANCE_STYLE[0]
          }`}
        >
          {method.assuranceLabel}
        </span>
      </div>

      <p className="text-sm text-gray-700 mt-2 leading-relaxed">{method.whatItProves}</p>
      <p className="text-xs text-gray-500 mt-1">{CHANNEL_LABEL[method.channel]}</p>
      <AvailabilityNote method={method} />

      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex items-center gap-1 text-xs text-gray-600 mt-3 hover:text-gray-900"
      >
        <ChevronDown
          className={`w-3.5 h-3.5 transition-transform ${open ? "rotate-180" : ""}`}
          aria-hidden="true"
        />
        What you need, and who this does not work for
      </button>
      {open && (
        <div className="mt-2 space-y-2 text-xs text-gray-600 border-l-2 border-gray-200 pl-3">
          <p>
            <span className="font-semibold text-gray-700">You will need: </span>
            {method.requirements}
          </p>
          {/* Shown to everyone, not buried in a help page. The people a method
              fails are the ones most likely to be reading this screen. */}
          <p>
            <span className="font-semibold text-gray-700">Does not work for: </span>
            {method.excludes}
          </p>
          <p className="text-gray-500">{method.legalBasis}</p>
        </div>
      )}

      {method.usable && onChoose && (
        <button
          type="button"
          onClick={() => onChoose(method)}
          className="mt-3 w-full py-2 rounded-lg bg-[#FF9933] text-white text-sm font-semibold hover:brightness-95"
        >
          Use this
        </button>
      )}
    </div>
  );
}

function MatchRow({ match }) {
  const tone = match.match
    ? "text-green-700"
    : match.decisive
    ? "text-red-700"
    : "text-amber-700";
  return (
    <li className="text-sm">
      <span className={`font-medium ${tone}`}>{match.field.replace(/_/g, " ")}</span>
      <span className="text-gray-600"> — {match.reason}</span>
    </li>
  );
}

function OutcomePanel({ outcome }) {
  if (!outcome) return null;
  const bad = outcome.contradicted;
  return (
    <div
      role="status"
      className={`rounded-xl border p-4 ${
        bad
          ? "border-amber-300 bg-amber-50"
          : outcome.needsReview
          ? "border-blue-200 bg-blue-50"
          : "border-green-200 bg-green-50"
      }`}
    >
      <div className="flex items-start gap-2">
        {bad ? (
          <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" aria-hidden="true" />
        ) : (
          <CheckCircle2 className="w-5 h-5 text-green-600 shrink-0 mt-0.5" aria-hidden="true" />
        )}
        <div className="min-w-0">
          <p className="text-sm font-medium text-gray-900">{outcome.message}</p>
          <p className="text-sm text-gray-700 mt-1">{outcome.messageHindi}</p>
        </div>
      </div>

      {outcome.matches?.length > 0 && (
        <ul className="mt-3 space-y-1.5 pl-7">
          {outcome.matches.map((m) => (
            <MatchRow key={m.field} match={m} />
          ))}
        </ul>
      )}

      {Object.keys(outcome.established || {}).length > 0 && (
        <div className="mt-3 pl-7">
          <p className="text-xs font-semibold text-gray-600 uppercase tracking-wide">
            Read from your document
          </p>
          <dl className="mt-1 grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1">
            {Object.entries(outcome.established).map(([k, v]) => (
              <div key={k} className="text-sm">
                <dt className="inline text-gray-500">{k.replace(/_/g, " ")}: </dt>
                <dd className="inline text-gray-900">{String(v)}</dd>
              </div>
            ))}
          </dl>
        </div>
      )}

      {outcome.warnings?.length > 0 && (
        <ul className="mt-3 pl-7 space-y-1">
          {outcome.warnings.map((w, i) => (
            <li key={i} className="text-xs text-gray-600">
              {w}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function IdentityPage({ userId }) {
  const { t } = useLanguage();
  const [methods, setMethods] = useState([]);
  const [profile, setProfile] = useState({});
  // Seeded from what this browser already recorded, so a citizen who verified
  // last week is not asked to do it again.
  const [outcomes, setOutcomes] = useState(() => loadKycOutcomes());
  const [status, setStatus] = useState(null);
  const [active, setActive] = useState(null);
  const [busy, setBusy] = useState(false);
  const [shareCode, setShareCode] = useState("");
  const [file, setFile] = useState(null);
  const [qr, setQr] = useState("");

  useEffect(() => {
    getKycMethods()
      .then((res) => setMethods(res.data.methods || []))
      .catch(() => toast.error(t("msg.error_generic")));
    if (userId) {
      getProfile(userId)
        .then((res) => setProfile(res.data?.profile || res.data || {}))
        .catch(() => setProfile({}));
    }
  }, [userId, t]);

  const refreshStatus = useCallback((next) => {
    getKycStatus(next)
      .then((res) => setStatus(res.data))
      .catch(() => setStatus(null));
  }, []);

  // Show what this browser already holds on arrival, so the page opens on the
  // citizen's actual state rather than a blank one.
  useEffect(() => {
    if (outcomes.length) refreshStatus(outcomes);
    // Deliberately runs once: later changes go through record().
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const record = useCallback(
    (outcome) => {
      // saveKycOutcome persists the verdict only — the demographics read out
      // of the document are deliberately not written to this device.
      const next = saveKycOutcome(outcome);
      setOutcomes(next.length ? next : [...outcomes, outcome]);
      refreshStatus(next);
    },
    [outcomes, refreshStatus]
  );

  const showError = (err) => {
    const detail = err?.response?.data?.detail;
    // The backend returns a bilingual, actionable object for anything the
    // citizen can fix themselves — a mistyped share code, the wrong file.
    if (detail && typeof detail === "object" && detail.error) {
      toast.error(detail.error, { description: detail.errorHindi });
    } else {
      toast.error(typeof detail === "string" ? detail : t("msg.error_generic"));
    }
  };

  const submitXml = async (e) => {
    e.preventDefault();
    if (!file) return;
    setBusy(true);
    try {
      const base64 = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result).split(",")[1] || "");
        reader.onerror = () => reject(reader.error);
        reader.readAsDataURL(file);
      });
      const res = await verifyAadhaarOfflineXml(profile, base64, shareCode);
      record(res.data);
      setShareCode("");
      setFile(null);
    } catch (err) {
      showError(err);
    } finally {
      setBusy(false);
    }
  };

  const submitQr = async (e) => {
    e.preventDefault();
    if (!qr.trim()) return;
    setBusy(true);
    try {
      const res = await verifyAadhaarSecureQr(profile, qr.trim());
      record(res.data);
      setQr("");
    } catch (err) {
      showError(err);
    } finally {
      setBusy(false);
    }
  };

  const submitSelfDeclaration = async () => {
    setBusy(true);
    try {
      const res = await recordSelfDeclaration(profile);
      record(res.data);
    } catch (err) {
      showError(err);
    } finally {
      setBusy(false);
    }
  };

  const latest = outcomes[outcomes.length - 1];

  return (
    <div className="min-h-screen bg-gray-50 pb-24">
      <AppHeader title="पहचान सत्यापन / Identity" />

      <div className="px-4 py-4 space-y-4 max-w-2xl mx-auto">
        {/* Stated first and without hedging. Everything below is optional, and a
            citizen who reads only the first paragraph must still learn that. */}
        <div className="rounded-xl border border-blue-200 bg-blue-50 p-4">
          <div className="flex items-start gap-2">
            <Info className="w-5 h-5 text-blue-600 shrink-0 mt-0.5" aria-hidden="true" />
            <div>
              <p className="text-sm font-semibold text-blue-900">
                None of this is compulsory.
              </p>
              <p className="text-sm text-blue-900 mt-1 leading-relaxed">
                You can apply for every scheme without verifying anything here.
                Verifying just means an officer has less to check, so your claim
                moves faster. {t("msg.aadhaar_optional")}
              </p>
              <p className="text-sm text-blue-900 mt-1">{t("msg.no_fee")}</p>
            </div>
          </div>
        </div>

        {status && (
          <div className="rounded-xl border border-gray-200 bg-white p-4">
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-5 h-5 text-gray-500" aria-hidden="true" />
              <span className="font-semibold text-sm">
                {status.label}
                <span className="text-gray-500 font-normal"> · {status.labelHindi}</span>
              </span>
            </div>
            <p className="text-sm text-gray-700 mt-2">{status.nextStep}</p>
            <p className="text-sm text-gray-600 mt-1">{status.nextStepHindi}</p>
          </div>
        )}

        <OutcomePanel outcome={latest} />

        {/* Aadhaar offline e-KYC — the strongest route that needs no licence. */}
        <form onSubmit={submitXml} className="rounded-xl border border-gray-200 bg-white p-4">
          <div className="flex items-center gap-2">
            <FileArchive className="w-5 h-5 text-[#FF9933]" aria-hidden="true" />
            <h2 className="font-semibold">Aadhaar offline e-KYC file</h2>
          </div>
          <p className="text-sm text-gray-600 mt-1.5 leading-relaxed">
            Download the ZIP from myaadhaar.uidai.gov.in and upload it here with
            the four-character share code you chose. The file is read and
            discarded — your full Aadhaar number is not in it and is never stored.
          </p>
          <label className="block mt-3 text-sm font-medium" htmlFor="ekyc-file">
            e-KYC ZIP file
          </label>
          <input
            id="ekyc-file"
            type="file"
            accept=".zip,application/zip"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
            className="mt-1 block w-full text-sm"
          />
          <label className="block mt-3 text-sm font-medium" htmlFor="share-code">
            Share code
          </label>
          <input
            id="share-code"
            type="text"
            value={shareCode}
            onChange={(e) => setShareCode(e.target.value)}
            maxLength={16}
            autoComplete="off"
            placeholder="The 4-character code you set"
            className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
          />
          <button
            type="submit"
            disabled={busy || !file}
            className="mt-3 w-full py-2.5 rounded-lg bg-[#FF9933] text-white font-semibold disabled:opacity-50"
          >
            {busy ? (
              <Loader2 className="w-4 h-4 animate-spin mx-auto" aria-hidden="true" />
            ) : (
              t("action.verify_identity")
            )}
          </button>
        </form>

        {/* Secure QR — for someone holding a printed card and no download. */}
        <form onSubmit={submitQr} className="rounded-xl border border-gray-200 bg-white p-4">
          <div className="flex items-center gap-2">
            <QrCode className="w-5 h-5 text-[#FF9933]" aria-hidden="true" />
            <h2 className="font-semibold">Aadhaar QR code</h2>
          </div>
          <p className="text-sm text-gray-600 mt-1.5 leading-relaxed">
            Scan the QR on your e-Aadhaar letter or PVC card and paste the value
            here. Older letters carry an unsigned QR that cannot be checked — if
            that happens you will be told, and another route offered.
          </p>
          <label className="block mt-3 text-sm font-medium" htmlFor="qr-value">
            Scanned QR value
          </label>
          <textarea
            id="qr-value"
            value={qr}
            onChange={(e) => setQr(e.target.value)}
            rows={3}
            className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm font-mono"
          />
          <button
            type="submit"
            disabled={busy || !qr.trim()}
            className="mt-3 w-full py-2.5 rounded-lg border border-[#FF9933] text-[#FF9933] font-semibold disabled:opacity-50"
          >
            Check QR code
          </button>
        </form>

        <div className="rounded-xl border border-gray-200 bg-white p-4">
          <div className="flex items-center gap-2">
            <UserCheck className="w-5 h-5 text-gray-500" aria-hidden="true" />
            <h2 className="font-semibold">Carry on without verifying</h2>
          </div>
          <p className="text-sm text-gray-600 mt-1.5 leading-relaxed">
            Record your details as self-declared. Nothing is checked against any
            record, and that is fine — you can still apply for everything.
          </p>
          <button
            type="button"
            onClick={submitSelfDeclaration}
            disabled={busy}
            className="mt-3 w-full py-2.5 rounded-lg border border-gray-300 font-semibold disabled:opacity-50"
          >
            {t("action.skip")}
          </button>
        </div>

        <section aria-labelledby="all-methods">
          <h2 id="all-methods" className="text-sm font-semibold text-gray-700 px-1 mb-2">
            Every way to prove who you are
          </h2>
          <div className="space-y-3">
            {methods.map((m) => (
              <MethodCard key={m.key} method={m} onChoose={setActive} />
            ))}
          </div>
        </section>

        <p className="text-xs text-gray-500 flex items-start gap-1.5 px-1">
          <Lock className="w-3.5 h-3.5 mt-0.5 shrink-0" aria-hidden="true" />
          {t("msg.not_government")}
        </p>
      </div>

      {active && (
        <div className="sr-only" role="status">
          Selected method: {active.name}
        </div>
      )}
      <BottomNav />
    </div>
  );
}
