import { useState } from "react";
import { IndianFlag } from "../components/IndianFlag";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import {
  InputOTP,
  InputOTPGroup,
  InputOTPSlot,
} from "../components/ui/input-otp";
import { sendOTP, verifyOTP } from "../lib/api";
import { toast } from "sonner";
import { Phone, ShieldCheck, ArrowRight, Loader2 } from "lucide-react";

export default function LoginPage({ onLogin }) {
  const [step, setStep] = useState("phone"); // phone | otp
  const [phone, setPhone] = useState("");
  const [otp, setOtp] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSendOTP = async () => {
    if (phone.length < 10) {
      toast.error("Please enter a valid 10-digit phone number");
      return;
    }
    setLoading(true);
    try {
      const res = await sendOTP(phone);
      if (res.data.success) {
        toast.success("OTP भेजा गया! (Use 1234)");
        setStep("otp");
      }
    } catch {
      toast.error("Failed to send OTP");
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOTP = async () => {
    if (otp.length !== 4) return;
    setLoading(true);
    try {
      const res = await verifyOTP(phone, otp);
      if (res.data.success) {
        toast.success("सत्यापित! Welcome");
        onLogin(res.data.user_id, res.data.phone);
      } else {
        toast.error(res.data.message || "Invalid OTP");
      }
    } catch {
      toast.error("Verification failed");
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
          <div className="inline-flex items-center justify-center mb-6">
            <div className="bg-white rounded-2xl p-4 shadow-md border border-orange-50">
              <IndianFlag size={56} />
            </div>
          </div>
          <h1
            data-testid="login-title"
            className="text-3xl font-bold text-[#000080] font-['Mukta'] mb-1"
          >
            नागरिक सहायक
          </h1>
          <p className="text-gray-500 text-sm font-['Nunito']">
            Your Digital Citizen Assistant
          </p>
        </div>

        {step === "phone" ? (
          <div className="space-y-5 animate-fade-in-up" style={{ animationDelay: "0.1s" }}>
            <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
              <div className="flex items-center gap-2 mb-4">
                <Phone size={18} className="text-[#FF9933]" />
                <span className="text-sm font-semibold text-gray-700 font-['Mukta']">
                  मोबाइल नंबर दर्ज करें
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
                  OTP भेजें
                  <ArrowRight size={18} />
                </>
              )}
            </Button>

            <p className="text-center text-xs text-gray-400 font-['Nunito']">
              Demo: Any number works. OTP is always 1234
            </p>
          </div>
        ) : (
          <div className="space-y-5 animate-fade-in-up">
            <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
              <div className="flex items-center gap-2 mb-2">
                <ShieldCheck size={18} className="text-[#138808]" />
                <span className="text-sm font-semibold text-gray-700 font-['Mukta']">
                  OTP सत्यापित करें
                </span>
              </div>
              <p className="text-xs text-gray-400 mb-5 font-['Nunito']">
                +91 {phone} पर भेजा गया
              </p>
              <div className="flex justify-center">
                <InputOTP
                  data-testid="otp-input"
                  maxLength={4}
                  value={otp}
                  onChange={setOtp}
                >
                  <InputOTPGroup>
                    <InputOTPSlot
                      index={0}
                      className="w-14 h-14 text-xl font-bold text-[#000080] border-gray-200 rounded-xl"
                    />
                    <InputOTPSlot
                      index={1}
                      className="w-14 h-14 text-xl font-bold text-[#000080] border-gray-200 rounded-xl"
                    />
                    <InputOTPSlot
                      index={2}
                      className="w-14 h-14 text-xl font-bold text-[#000080] border-gray-200 rounded-xl"
                    />
                    <InputOTPSlot
                      index={3}
                      className="w-14 h-14 text-xl font-bold text-[#000080] border-gray-200 rounded-xl"
                    />
                  </InputOTPGroup>
                </InputOTP>
              </div>
            </div>

            <Button
              data-testid="verify-otp-btn"
              onClick={handleVerifyOTP}
              disabled={otp.length !== 4 || loading}
              className="w-full h-12 rounded-full bg-[#000080] hover:bg-[#000066] text-white font-semibold text-base shadow-lg shadow-blue-200 transition-all duration-200 hover:-translate-y-0.5"
            >
              {loading ? (
                <Loader2 className="animate-spin" size={20} />
              ) : (
                <>
                  सत्यापित करें
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
              नंबर बदलें
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
