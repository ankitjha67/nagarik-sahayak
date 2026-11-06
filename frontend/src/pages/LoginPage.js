import { useState } from "react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import {
  InputOTP,
  InputOTPGroup,
  InputOTPSlot,
} from "../components/ui/input-otp";
import { sendOTP, verifyOTP, storeSession } from "../lib/api";
import { toast } from "sonner";
import { Phone, ShieldCheck, ArrowRight, Loader2 } from "lucide-react";
import { useLanguage } from "../lib/i18n";

export default function LoginPage({ onLogin }) {
  const { tx } = useLanguage();
  const [step, setStep] = useState("phone"); // phone | otp
  const [phone, setPhone] = useState("");
  const [otp, setOtp] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSendOTP = async () => {
    if (phone.length < 10) {
      toast.error(tx("login.invalidPhone"));
      return;
    }
    setLoading(true);
    try {
      const res = await sendOTP(phone);
      if (res.data.success) {
        toast.success(tx("login.otpSent"));
        setStep("otp");
      }
    } catch {
      toast.error(tx("login.sendFailed"));
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOTP = async () => {
    if (otp.length !== 6) return;
    setLoading(true);
    try {
      const res = await verifyOTP(phone, otp);
      if (res.data.success) {
        // Keep the tokens before anything renders that needs them.
        storeSession(res.data);
        toast.success(tx("login.verified"));
        onLogin(res.data.user_id, res.data.phone);
      } else {
        toast.error(res.data.message || tx("login.invalidOtp"));
      }
    } catch (err) {
      // A wrong or expired code is a 401 with a reason; a locked number a 429.
      const detail = err?.response?.data?.detail;
      toast.error(detail || tx("login.verifyFailed"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      data-testid="login-page"
      className="min-h-screen bg-gradient-to-b from-[#FFF8F0] to-white flex flex-col items-center justify-center px-6"
    >
      <div className="w-full max-w-sm">
        {/* Header */}
        <div className="text-center mb-10 animate-fade-in-up">
          <div className="inline-flex items-center justify-center mb-4">
            <img src="/logo.png" alt="Nagarik Sahayak" className="w-48 h-auto object-contain" />
          </div>
        </div>

        {step === "phone" ? (
          <div className="space-y-5 animate-fade-in-up" style={{ animationDelay: "0.1s" }}>
            <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
              <div className="flex items-center gap-2 mb-4">
                <Phone size={18} className="text-[#FF9933]" />
                <span className="text-sm font-semibold text-gray-700 font-['Mukta']">
                  {tx("login.enterMobile")}
                </span>
              </div>
              <div className="flex gap-2">
                <div className="flex items-center px-3 bg-gray-50 rounded-xl border border-gray-200 text-sm text-gray-600 font-medium">
                  +91
                </div>
                <Input
                  data-testid="phone-input"
                  type="tel"
                  maxLength={10}
                  placeholder="9876543210"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value.replace(/\D/g, ""))}
                  className="h-12 rounded-xl text-base font-['Nunito'] border-gray-200 focus:ring-[#FF9933] focus:border-[#FF9933]"
                />
              </div>
            </div>

            <Button
              data-testid="send-otp-btn"
              onClick={handleSendOTP}
              disabled={phone.length < 10 || loading}
              className="w-full h-12 rounded-full bg-[#FF9933] hover:bg-[#E68A00] text-white font-semibold text-base shadow-lg shadow-orange-200 transition-all duration-200 hover:-translate-y-0.5"
            >
              {loading ? (
                <Loader2 className="animate-spin" size={20} />
              ) : (
                <>
                  {tx("login.sendOtp")}
                  <ArrowRight size={18} />
                </>
              )}
            </Button>

          </div>
        ) : (
          <div className="space-y-5 animate-fade-in-up">
            <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
              <div className="flex items-center gap-2 mb-2">
                <ShieldCheck size={18} className="text-[#138808]" />
                <span className="text-sm font-semibold text-gray-700 font-['Mukta']">
                  {tx("login.enterOtp")}
                </span>
              </div>
              <p className="text-xs text-gray-400 mb-5 font-['Nunito']">
                {tx("login.sentTo")} +91 {phone}
              </p>
              <div className="flex justify-center">
                <InputOTP
                  data-testid="otp-input"
                  maxLength={6}
                  value={otp}
                  onChange={setOtp}
                >
                  <InputOTPGroup>
                    <InputOTPSlot
                      index={0}
                      className="w-12 h-12 text-xl font-bold text-[#000080] border-gray-200 rounded-xl"
                    />
                    <InputOTPSlot
                      index={1}
                      className="w-12 h-12 text-xl font-bold text-[#000080] border-gray-200 rounded-xl"
                    />
                    <InputOTPSlot
                      index={2}
                      className="w-12 h-12 text-xl font-bold text-[#000080] border-gray-200 rounded-xl"
                    />
                    <InputOTPSlot
                      index={3}
                      className="w-12 h-12 text-xl font-bold text-[#000080] border-gray-200 rounded-xl"
                    />
                    <InputOTPSlot
                      index={4}
                      className="w-12 h-12 text-xl font-bold text-[#000080] border-gray-200 rounded-xl"
                    />
                    <InputOTPSlot
                      index={5}
                      className="w-12 h-12 text-xl font-bold text-[#000080] border-gray-200 rounded-xl"
                    />
                  </InputOTPGroup>
                </InputOTP>
              </div>
            </div>

            <Button
              data-testid="verify-otp-btn"
              onClick={handleVerifyOTP}
              disabled={otp.length !== 6 || loading}
              className="w-full h-12 rounded-full bg-[#000080] hover:bg-[#000066] text-white font-semibold text-base shadow-lg shadow-blue-200 transition-all duration-200 hover:-translate-y-0.5"
            >
              {loading ? (
                <Loader2 className="animate-spin" size={20} />
              ) : (
                <>
                  {tx("login.verify")}
                  <ShieldCheck size={18} />
                </>
              )}
            </Button>

            <button
              data-testid="change-number-btn"
              onClick={() => {
                setStep("phone");
                setOtp("");
              }}
              className="block mx-auto text-sm text-[#000080] font-medium hover:underline font-['Nunito']"
            >
              {tx("login.changeNumber")}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
