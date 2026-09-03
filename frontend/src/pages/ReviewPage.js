import { useState, useEffect, useCallback, useRef } from "react";
import { AppHeader } from "../components/AppHeader";
import {
  getReviewQueue, getReviewCase, decideReviewCase, reopenReviewCase,
} from "../lib/api";
import { toast } from "sonner";
import {
  AlertTriangle, ArrowLeft, BadgeCheck, CheckCircle2, ChevronRight, Clock,
  Eye, EyeOff, FileWarning, Inbox, Loader2, LogOut, RefreshCw, RotateCcw,
  Search, ShieldAlert, ShieldCheck, User, XCircle,
} from "lucide-react";

// Reviewer credentials live in sessionStorage, not localStorage: they should
// not outlive the browser session or leak into an ordinary citizen's device
// state. They are never attached to the shared axios instance.
const CRED_KEY = "ns_reviewer_creds";

const loadCreds = () => {
  try {
    const raw = sessionStorage.getItem(CRED_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
};

const STATUS_TABS = [
  { key: "pending", label: "Pending", labelHi: "लंबित", icon: Inbox },
  { key: "approved", label: "Approved", labelHi: "स्वीकृत", icon: CheckCircle2 },
  { key: "rejected", label: "Rejected", labelHi: "अस्वीकृत", icon: XCircle },
];

const STATUS_STYLE = {
  pending: "bg-amber-50 text-amber-700 border-amber-200",
  approved: "bg-green-50 text-green-700 border-green-200",
  rejected: "bg-red-50 text-red-700 border-red-200",
};

// Mirrors the backend's REVIEW_THRESHOLD (25) and ESCALATE_THRESHOLD (60).
function riskBand(score) {
  if (score >= 60) return { label: "High", cls: "bg-red-100 text-red-800", ring: "ring-red-300" };
  if (score >= 25) return { label: "Medium", cls: "bg-amber-100 text-amber-800", ring: "ring-amber-300" };
  return { label: "Low", cls: "bg-gray-100 text-gray-700", ring: "ring-gray-200" };
}

function timeAgo(iso) {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const mins = Math.floor((Date.now() - then) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

function apiError(err, fallback) {
  return err?.response?.data?.detail || err?.message || fallback;
}

/* ─────────────── Sign-in ─────────────── */

function ReviewerSignIn({ onSignIn }) {
  const [reviewerId, setReviewerId] = useState("");
  const [adminSecret, setAdminSecret] = useState("");
  const [showSecret, setShowSecret] = useState(false);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e) => {
    e?.preventDefault();
    if (!reviewerId.trim() || !adminSecret.trim()) return;
    setChecking(true);
    setError("");
    const creds = { reviewerId: reviewerId.trim(), adminSecret: adminSecret.trim() };
    try {
      // Verify by actually hitting the queue — no point admitting someone to a
      // console whose every request will then fail.
      await getReviewQueue(creds, { limit: 1 });
      sessionStorage.setItem(CRED_KEY, JSON.stringify(creds));
      onSignIn(creds);
    } catch (err) {
      setError(
        err?.response?.status === 403
          ? "Those credentials were not accepted."
          : apiError(err, "Could not reach the review service.")
      );
    } finally {
      setChecking(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
      <form
        onSubmit={submit}
        data-testid="reviewer-signin"
        className="w-full max-w-sm bg-white rounded-2xl border border-gray-100 shadow-sm p-6"
      >
        <div className="text-center mb-5">
          <div className="w-12 h-12 mx-auto rounded-xl bg-[#E8EAF6] flex items-center justify-center mb-3">
            <ShieldCheck size={24} className="text-[#000080]" />
          </div>
          <h1 className="text-base font-bold text-[#000080] font-['Mukta']">
            समीक्षक लॉगिन / Reviewer Sign-in
          </h1>
          <p className="text-xs text-gray-500 font-['Nunito'] mt-1">
            Flagged benefit applications
          </p>
        </div>

        <label className="text-xs font-semibold text-gray-700 font-['Mukta'] block mb-1">
          Reviewer ID
        </label>
        <input
          type="text"
          value={reviewerId}
          onChange={(e) => setReviewerId(e.target.value)}
          placeholder="e.g. officer.sharma"
          data-testid="reviewer-id-input"
          autoComplete="username"
          className="w-full px-3 py-2.5 mb-1 rounded-xl border border-gray-200 text-sm font-['Nunito'] focus:border-[#000080] focus:ring-1 focus:ring-[#000080] outline-none"
        />
        <p className="text-[10px] text-gray-400 font-['Nunito'] mb-3">
          Recorded against every decision you make.
        </p>

        <label className="text-xs font-semibold text-gray-700 font-['Mukta'] block mb-1">
          Access Key
        </label>
        <div className="relative mb-4">
          <input
            type={showSecret ? "text" : "password"}
            value={adminSecret}
            onChange={(e) => setAdminSecret(e.target.value)}
            data-testid="reviewer-secret-input"
            autoComplete="current-password"
            className="w-full px-3 py-2.5 pr-10 rounded-xl border border-gray-200 text-sm font-['Nunito'] focus:border-[#000080] focus:ring-1 focus:ring-[#000080] outline-none"
          />
          <button
            type="button"
            onClick={() => setShowSecret((v) => !v)}
            aria-label={showSecret ? "Hide access key" : "Show access key"}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
          >
            {showSecret ? <EyeOff size={15} /> : <Eye size={15} />}
          </button>
        </div>

        {error && (
          <p
            data-testid="signin-error"
            className="text-xs text-red-600 font-['Nunito'] mb-3 flex items-center gap-1"
          >
            <XCircle size={12} className="flex-shrink-0" />
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={checking || !reviewerId.trim() || !adminSecret.trim()}
          data-testid="reviewer-signin-btn"
          className="w-full py-2.5 rounded-xl bg-[#000080] text-white text-sm font-semibold hover:bg-[#000060] transition-colors disabled:opacity-40 flex items-center justify-center gap-2"
        >
          {checking ? <Loader2 size={15} className="animate-spin" /> : <ShieldCheck size={15} />}
          {checking ? "Verifying…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}

/* ─────────────── Queue summary ─────────────── */

function QueueSummary({ summary }) {
  if (!summary) return null;
  const cards = [
    { label: "Pending", value: summary.pending, cls: "text-amber-600 bg-amber-50" },
    { label: "High risk", value: summary.high_risk_pending, cls: "text-red-600 bg-red-50" },
    { label: "Approved", value: summary.approved, cls: "text-green-600 bg-green-50" },
    { label: "Rejected", value: summary.rejected, cls: "text-gray-600 bg-gray-50" },
  ];
  const topSignals = Object.entries(summary.top_signals || {});

  return (
    <div className="mb-4">
      <div className="grid grid-cols-4 gap-2">
        {cards.map((c) => (
          <div key={c.label} className={`rounded-xl p-2.5 text-center ${c.cls}`}>
            <p className="text-lg font-bold leading-none">{c.value ?? 0}</p>
            <p className="text-[9px] mt-1 opacity-80 font-['Nunito']">{c.label}</p>
          </div>
        ))}
      </div>
      {topSignals.length > 0 && (
        <div className="mt-2 bg-white rounded-xl border border-gray-100 p-2.5">
          <p className="text-[10px] font-semibold text-gray-500 font-['Nunito'] mb-1.5">
            Most common reasons in the pending queue
          </p>
          <div className="flex flex-wrap gap-1">
            {topSignals.map(([code, n]) => (
              <span
                key={code}
                className="text-[9px] px-2 py-0.5 rounded-full bg-gray-100 text-gray-700 font-['Nunito']"
              >
                {code.replace(/_/g, " ")} · {n}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ─────────────── Case detail ─────────────── */

function SignalCard({ signal }) {
  const [open, setOpen] = useState(false);
  const band = riskBand(signal.weight >= 40 ? 60 : signal.weight >= 20 ? 25 : 0);
  return (
    <div className="rounded-xl border border-gray-100 bg-white overflow-hidden">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full p-3 text-left flex items-start gap-2"
      >
        <ShieldAlert size={14} className="text-amber-500 mt-0.5 flex-shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="text-[11px] font-bold text-gray-800 font-['Mukta']">
              {(signal.code || "").replace(/_/g, " ")}
            </span>
            <span className={`text-[9px] px-1.5 py-0.5 rounded-full ${band.cls}`}>
              +{signal.weight}
            </span>
            {signal.threat && (
              <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-gray-100 text-gray-600">
                {signal.threat}
              </span>
            )}
          </div>
          <p className="text-[11px] text-gray-600 font-['Nunito'] mt-1 leading-snug">
            {signal.detail_en}
          </p>
        </div>
        <ChevronRight
          size={14}
          className={`text-gray-400 flex-shrink-0 transition-transform ${open ? "rotate-90" : ""}`}
        />
      </button>

      {open && (
        <div className="px-3 pb-3 pt-0 space-y-2 border-t border-gray-50">
          {signal.what_it_means && (
            <div className="mt-2">
              <p className="text-[9px] font-bold text-gray-500 uppercase tracking-wide">
                What it means
              </p>
              <p className="text-[11px] text-gray-700 font-['Nunito'] leading-snug">
                {signal.what_it_means}
              </p>
            </div>
          )}
          {/* Shown with equal prominence to the accusation: clearing an innocent
              applicant must be as easy as confirming a fraudulent one. */}
          {signal.innocent_explanation && (
            <div className="rounded-lg bg-green-50 border border-green-100 p-2">
              <p className="text-[9px] font-bold text-green-700 uppercase tracking-wide">
                Innocent explanation to rule out
              </p>
              <p className="text-[11px] text-green-800 font-['Nunito'] leading-snug">
                {signal.innocent_explanation}
              </p>
            </div>
          )}
          {signal.suggested_check && (
            <div className="rounded-lg bg-blue-50 border border-blue-100 p-2">
              <p className="text-[9px] font-bold text-blue-700 uppercase tracking-wide">
                Suggested check
              </p>
              <p className="text-[11px] text-blue-800 font-['Nunito'] leading-snug">
                {signal.suggested_check}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// What identity evidence stands behind this application. A reviewer needs to
// tell apart an applicant who produced a UIDAI-signed document from one who
// typed a number into a form — those deserve different amounts of scrutiny,
// and without this panel they look identical on screen.
//
// "Self-declared" is rendered as a neutral state, not a warning. It is the
// normal, lawful condition of an applicant under the Aadhaar Act s7 proviso,
// and colouring it red would train reviewers to treat the unverified poor as
// suspects.
const ASSURANCE_TONE = {
  0: "bg-gray-50 border-gray-200 text-gray-700",
  1: "bg-gray-50 border-gray-200 text-gray-700",
  2: "bg-blue-50 border-blue-200 text-blue-900",
  3: "bg-green-50 border-green-200 text-green-900",
  4: "bg-green-50 border-green-200 text-green-900",
  5: "bg-green-50 border-green-200 text-green-900",
};

function IdentityPanel({ identity }) {
  if (!identity) return null;
  const tone = ASSURANCE_TONE[identity.assurance] || ASSURANCE_TONE[0];

  return (
    <div className={`rounded-xl border p-3 ${tone}`}>
      <div className="flex items-center gap-2">
        <BadgeCheck size={14} className="shrink-0" aria-hidden="true" />
        <span className="text-[12px] font-bold font-['Mukta']">
          {identity.label}
        </span>
        {identity.contradiction && (
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-100 text-amber-900 font-semibold">
            Document disagrees
          </span>
        )}
      </div>

      <p className="text-[11px] mt-1.5 leading-relaxed font-['Nunito']">
        {identity.reviewer_note}
      </p>

      {identity.methodsUsed?.length > 0 && (
        <p className="text-[11px] mt-1.5 opacity-80 font-['Nunito']">
          Checks completed: {identity.methodsUsed.join(", ").replace(/_/g, " ")}
        </p>
      )}

      {identity.comparisons?.length > 0 && (
        <div className="mt-2 pt-2 border-t border-black/10">
          <p className="text-[10px] font-bold uppercase tracking-wide opacity-70">
            Field comparison
          </p>
          <ul className="mt-1 space-y-1">
            {identity.comparisons.map((c, i) => (
              <li key={i} className="text-[11px] font-['Nunito']">
                <span className="font-semibold">
                  {String(c.field).replace(/_/g, " ")}
                </span>
                {c.decisive ? " — cannot be a transcription difference: " : " — "}
                {c.reason}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Shown so the reviewer knows exactly what the applicant has been told,
          and does not contradict it on a phone call. */}
      {identity.citizen_is_told?.en && (
        <p className="text-[10px] mt-2 pt-2 border-t border-black/10 opacity-70 font-['Nunito']">
          The applicant is being shown: “{identity.citizen_is_told.en}”
        </p>
      )}
    </div>
  );
}

function ApplicantPanel({ applicant, error }) {
  if (error || !applicant) {
    return (
      <div className="rounded-xl border border-gray-200 bg-gray-50 p-3 flex items-center gap-2">
        <FileWarning size={14} className="text-gray-400" />
        <span className="text-[11px] text-gray-500 font-['Nunito']">
          {error || "Applicant details unavailable."}
        </span>
      </div>
    );
  }

  const fields = Object.entries(applicant.fields || {});
  const masked = Object.entries(applicant.identifiers_masked || {});
  const others = applicant.other_cases || [];

  return (
    <div className="space-y-2">
      <div className="rounded-xl border border-gray-100 bg-white p-3">
        <div className="flex items-center gap-1.5 mb-2">
          <User size={13} className="text-[#000080]" />
          <span className="text-[11px] font-bold text-[#000080] font-['Mukta']">
            Applicant
          </span>
          <span className="text-[9px] text-gray-400 ml-auto font-['Nunito']">
            {applicant.fields_supplied} fields on file
          </span>
        </div>

        <div className="grid grid-cols-2 gap-x-3 gap-y-1">
          {fields.map(([k, v]) => (
            <div key={k} className="min-w-0">
              <p className="text-[9px] text-gray-400 font-['Nunito'] truncate">
                {k.replace(/_/g, " ")}
              </p>
              <p className="text-[11px] text-gray-800 font-['Nunito'] font-semibold truncate">
                {String(v)}
              </p>
            </div>
          ))}
        </div>

        {masked.length > 0 && (
          <div className="mt-2 pt-2 border-t border-gray-50">
            <p className="text-[9px] text-gray-400 font-['Nunito'] mb-1">
              Identifiers (last 4 digits shown)
            </p>
            <div className="flex flex-wrap gap-1.5">
              {masked.map(([k, v]) => (
                <span
                  key={k}
                  className="text-[10px] px-2 py-0.5 rounded-md bg-gray-100 text-gray-700 font-mono"
                  title={k.replace(/_/g, " ")}
                >
                  {v}
                </span>
              ))}
              {applicant.phone_masked && (
                <span className="text-[10px] px-2 py-0.5 rounded-md bg-gray-100 text-gray-700 font-mono">
                  {applicant.phone_masked}
                </span>
              )}
            </div>
          </div>
        )}
      </div>

      {/* One flag is noise; a pattern across schemes is a decision. */}
      {others.length > 0 && (
        <div className="rounded-xl border border-gray-100 bg-white p-3">
          <p className="text-[11px] font-bold text-[#000080] font-['Mukta'] mb-1.5">
            Other cases for this applicant ({others.length})
          </p>
          {others.map((o) => (
            <div key={o.id} className="flex items-center gap-2 py-1">
              <span
                className={`text-[9px] px-1.5 py-0.5 rounded-full border ${
                  STATUS_STYLE[o.status] || STATUS_STYLE.pending
                }`}
              >
                {o.status}
              </span>
              <span className="text-[11px] text-gray-700 font-['Nunito'] flex-1 truncate">
                {o.scheme}
              </span>
              <span className="text-[10px] text-gray-400 font-mono">{o.risk_score}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function CaseDetail({ creds, caseId, onBack, onDecided }) {
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await getReviewCase(creds, caseId);
      setDetail(res.data);
    } catch (err) {
      setError(apiError(err, "Could not load this case."));
    } finally {
      setLoading(false);
    }
  }, [creds, caseId]);

  useEffect(() => { load(); }, [load]);

  const act = async (action) => {
    // The backend enforces this too; checking here saves a round trip and lets
    // the reviewer fix it without losing what they typed.
    if (action === "rejected" && !note.trim()) {
      setError("A rejection needs a reason — the applicant is entitled to one.");
      return;
    }
    setBusy(action);
    setError("");
    try {
      if (action === "reopen") {
        await reopenReviewCase(creds, caseId, note.trim());
        toast.success("Case reopened");
      } else {
        await decideReviewCase(creds, caseId, action, note.trim());
        toast.success(action === "approved" ? "Approved" : "Rejected");
      }
      onDecided?.();
      onBack();
    } catch (err) {
      // 409 means someone else already decided it. Reload so the reviewer sees
      // the current state rather than acting on a stale view.
      if (err?.response?.status === 409) {
        setError(apiError(err, "This case was already decided."));
        load();
      } else {
        setError(apiError(err, "Could not record the decision."));
      }
    } finally {
      setBusy("");
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 size={22} className="animate-spin text-[#000080]" />
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="text-center py-12">
        <FileWarning size={28} className="text-gray-300 mx-auto mb-2" />
        <p className="text-sm text-gray-500 font-['Nunito']">{error || "Case not found."}</p>
        <button onClick={onBack} className="mt-3 text-xs text-[#000080] font-semibold underline">
          Back to queue
        </button>
      </div>
    );
  }

  const band = riskBand(detail.riskScore);
  const isPending = detail.status === "pending";

  return (
    <div data-testid="case-detail" className="animate-fade-in-up">
      <button
        onClick={onBack}
        className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700 mb-3"
      >
        <ArrowLeft size={13} /> Back to queue
      </button>

      <div className="bg-white rounded-xl border border-gray-100 p-4 mb-3">
        <div className="flex items-start gap-2">
          <div className="flex-1 min-w-0">
            <h2 className="text-sm font-bold text-[#000080] font-['Mukta'] leading-tight">
              {detail.schemeName}
            </h2>
            <p className="text-[10px] text-gray-400 font-['Nunito'] mt-0.5">
              Raised {timeAgo(detail.createdAt)} · outcome {detail.outcome}
            </p>
          </div>
          <div className="text-right flex-shrink-0">
            <span className={`text-xs font-bold px-2 py-1 rounded-lg ${band.cls}`}>
              {detail.riskScore}
            </span>
            <p className="text-[9px] text-gray-400 mt-0.5">{band.label} risk</p>
          </div>
        </div>

        {!isPending && (
          <div className={`mt-3 rounded-lg border p-2 ${STATUS_STYLE[detail.status]}`}>
            <p className="text-[11px] font-bold font-['Mukta']">
              {detail.status === "approved" ? "Approved" : "Rejected"} by {detail.reviewerId || "unknown"}
              {detail.reviewedAt ? ` · ${timeAgo(detail.reviewedAt)}` : ""}
            </p>
            {detail.reviewerNote && (
              <p className="text-[11px] font-['Nunito'] mt-0.5 opacity-90">
                {detail.reviewerNote}
              </p>
            )}
          </div>
        )}
      </div>

      <div className="mb-3">
        <p className="text-[11px] font-bold text-gray-600 font-['Mukta'] mb-1.5">
          Applicant details
        </p>
        <ApplicantPanel applicant={detail.applicant} error={detail.applicant_error} />
      </div>

      <div className="mb-3">
        <p className="text-[11px] font-bold text-gray-600 font-['Mukta'] mb-1.5">
          Identity evidence
        </p>
        <IdentityPanel identity={detail.identity} />
      </div>

      <div className="mb-3">
        <p className="text-[11px] font-bold text-gray-600 font-['Mukta'] mb-1.5">
          Why this was flagged ({(detail.signals || []).length})
        </p>
        <div className="space-y-2">
          {(detail.signals || []).map((s, i) => <SignalCard key={i} signal={s} />)}
          {(detail.signals || []).length === 0 && (
            <p className="text-[11px] text-gray-400 font-['Nunito']">
              No signals recorded on this case.
            </p>
          )}
        </div>
      </div>

      <div className="bg-white rounded-xl border border-gray-100 p-3">
        <label className="text-[11px] font-bold text-gray-600 font-['Mukta'] block mb-1.5">
          Reviewer note
          {isPending && (
            <span className="font-normal text-gray-400"> — required to reject</span>
          )}
        </label>
        <textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          rows={3}
          data-testid="reviewer-note"
          placeholder="What did you check, and what did you find?"
          className="w-full px-3 py-2 rounded-xl border border-gray-200 text-xs font-['Nunito'] focus:border-[#000080] focus:ring-1 focus:ring-[#000080] outline-none resize-none"
        />

        {error && (
          <p
            data-testid="decision-error"
            className="text-[11px] text-red-600 font-['Nunito'] mt-2 flex items-start gap-1"
          >
            <XCircle size={12} className="flex-shrink-0 mt-0.5" />
            {error}
          </p>
        )}

        <div className="flex gap-2 mt-3">
          {isPending ? (
            <>
              <button
                onClick={() => act("approved")}
                disabled={!!busy}
                data-testid="approve-btn"
                className="flex-1 py-2.5 rounded-xl bg-[#138808] text-white text-xs font-bold hover:bg-[#0f6b06] transition-colors disabled:opacity-40 flex items-center justify-center gap-1.5"
              >
                {busy === "approved" ? <Loader2 size={13} className="animate-spin" /> : <CheckCircle2 size={13} />}
                Approve
              </button>
              <button
                onClick={() => act("rejected")}
                disabled={!!busy}
                data-testid="reject-btn"
                className="flex-1 py-2.5 rounded-xl bg-red-600 text-white text-xs font-bold hover:bg-red-700 transition-colors disabled:opacity-40 flex items-center justify-center gap-1.5"
              >
                {busy === "rejected" ? <Loader2 size={13} className="animate-spin" /> : <XCircle size={13} />}
                Reject
              </button>
            </>
          ) : (
            <button
              onClick={() => act("reopen")}
              disabled={!!busy}
              data-testid="reopen-btn"
              className="flex-1 py-2.5 rounded-xl border border-gray-300 text-gray-700 text-xs font-bold hover:bg-gray-50 transition-colors disabled:opacity-40 flex items-center justify-center gap-1.5"
            >
              {busy === "reopen" ? <Loader2 size={13} className="animate-spin" /> : <RotateCcw size={13} />}
              Reopen this case
            </button>
          )}
        </div>

        {isPending && (
          <p className="text-[10px] text-gray-400 font-['Nunito'] mt-2 leading-snug">
            Approving releases the benefit for processing. Rejecting records your
            reason, which is shown to the applicant.
          </p>
        )}
      </div>
    </div>
  );
}

/* ─────────────── Queue list ─────────────── */

function QueueList({ creds, status, onOpen, refreshKey }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await getReviewQueue(creds, { status, limit: 100 });
      if (mounted.current) setData(res.data);
    } catch (err) {
      if (mounted.current) setError(apiError(err, "Could not load the queue."));
    } finally {
      if (mounted.current) setLoading(false);
    }
  }, [creds, status]);

  useEffect(() => { load(); }, [load, refreshKey]);

  if (loading && !data) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 size={22} className="animate-spin text-[#000080]" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-12">
        <AlertTriangle size={26} className="text-amber-400 mx-auto mb-2" />
        <p className="text-sm text-gray-600 font-['Nunito']">{error}</p>
        <button onClick={load} className="mt-3 text-xs text-[#000080] font-semibold underline">
          Try again
        </button>
      </div>
    );
  }

  const cases = (data?.cases || []).filter((c) => {
    if (!query.trim()) return true;
    const q = query.toLowerCase();
    const signals = (c.signals || []).map((s) => s.code || "").join(" ");
    return `${c.schemeName} ${signals}`.toLowerCase().includes(q);
  });

  return (
    <>
      <QueueSummary summary={data?.summary} />

      <div className="relative mb-3">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Filter by scheme or signal"
          data-testid="queue-filter"
          className="w-full pl-9 pr-3 py-2 rounded-xl border border-gray-200 text-xs font-['Nunito'] focus:border-[#000080] focus:ring-1 focus:ring-[#000080] outline-none"
        />
      </div>

      {cases.length === 0 ? (
        <div className="text-center py-12" data-testid="queue-empty">
          <Inbox size={30} className="text-gray-300 mx-auto mb-2" />
          <p className="text-sm text-gray-500 font-['Nunito']">
            {query.trim()
              ? "No cases match that filter."
              : status === "pending"
              ? "Nothing waiting for review."
              : `No ${status} cases.`}
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {cases.map((c) => {
            const band = riskBand(c.riskScore);
            return (
              <button
                key={c.id}
                onClick={() => onOpen(c.id)}
                data-testid={`case-row-${c.id}`}
                className={`w-full text-left bg-white rounded-xl border border-gray-100 p-3 hover:shadow-sm transition-all flex items-start gap-3 ring-1 ring-inset ${band.ring}`}
              >
                <div className={`px-2 py-1 rounded-lg flex-shrink-0 ${band.cls}`}>
                  <span className="text-xs font-bold">{c.riskScore}</span>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-bold text-gray-800 font-['Mukta'] truncate">
                    {c.schemeName}
                  </p>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {(c.signals || []).slice(0, 3).map((s, i) => (
                      <span
                        key={i}
                        className="text-[9px] px-1.5 py-0.5 rounded-full bg-gray-100 text-gray-600 font-['Nunito']"
                      >
                        {(s.code || "").replace(/_/g, " ")}
                      </span>
                    ))}
                    {(c.signals || []).length > 3 && (
                      <span className="text-[9px] text-gray-400">
                        +{(c.signals || []).length - 3}
                      </span>
                    )}
                  </div>
                  <p className="text-[10px] text-gray-400 font-['Nunito'] mt-1 flex items-center gap-1">
                    <Clock size={9} /> {timeAgo(c.createdAt)}
                    {c.status !== "pending" && ` · ${c.status} by ${c.reviewerId || "unknown"}`}
                  </p>
                </div>
                <ChevronRight size={15} className="text-gray-300 flex-shrink-0 mt-1" />
              </button>
            );
          })}
        </div>
      )}
    </>
  );
}

/* ─────────────── Page ─────────────── */

export default function ReviewPage() {
  const [creds, setCreds] = useState(loadCreds);
  const [status, setStatus] = useState("pending");
  const [openCaseId, setOpenCaseId] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);

  const signOut = () => {
    sessionStorage.removeItem(CRED_KEY);
    setCreds(null);
    setOpenCaseId(null);
  };

  if (!creds) return <ReviewerSignIn onSignIn={setCreds} />;

  return (
    <div data-testid="review-page" className="min-h-screen bg-gray-50 pb-10">
      <AppHeader title="समीक्षा / Review" />

      <div className="max-w-md mx-auto px-4 pt-4">
        <div className="flex items-center justify-between mb-3">
          <p className="text-[11px] text-gray-500 font-['Nunito'] truncate">
            Signed in as <span className="font-semibold">{creds.reviewerId}</span>
          </p>
          <div className="flex items-center gap-1 flex-shrink-0">
            <button
              onClick={() => setRefreshKey((k) => k + 1)}
              aria-label="Refresh queue"
              className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-500"
            >
              <RefreshCw size={13} />
            </button>
            <button
              onClick={signOut}
              aria-label="Sign out"
              data-testid="reviewer-signout"
              className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-500"
            >
              <LogOut size={13} />
            </button>
          </div>
        </div>

        {openCaseId ? (
          <CaseDetail
            creds={creds}
            caseId={openCaseId}
            onBack={() => setOpenCaseId(null)}
            onDecided={() => setRefreshKey((k) => k + 1)}
          />
        ) : (
          <>
            <div className="flex gap-1 bg-white rounded-xl p-1 border border-gray-100 mb-4">
              {STATUS_TABS.map(({ key, label, icon: Icon }) => (
                <button
                  key={key}
                  onClick={() => setStatus(key)}
                  data-testid={`tab-${key}`}
                  className={`flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg text-xs font-semibold transition-all ${
                    status === key
                      ? "bg-[#000080] text-white shadow-sm"
                      : "text-gray-500 hover:text-gray-700"
                  }`}
                >
                  <Icon size={13} />
                  {label}
                </button>
              ))}
            </div>

            <QueueList
              creds={creds}
              status={status}
              onOpen={setOpenCaseId}
              refreshKey={refreshKey}
            />
          </>
        )}
      </div>
    </div>
  );
}
