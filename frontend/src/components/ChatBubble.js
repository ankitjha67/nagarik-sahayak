import { CheckCheck } from "lucide-react";

export const ChatBubble = ({ message }) => {
  const isUser = message.role === "user";
  const isRead = message.status === "read";
  const isBot = message.role === "assistant";

  return (
    <div
      data-testid={`chat-bubble-${message.role}`}
      className={`flex ${isUser ? "justify-end" : "justify-start"} animate-fade-in-up`}
    >
      <div
        className={`relative max-w-[85%] px-4 py-2.5 ${
          isUser
            ? "bg-[#FFF0E0] rounded-2xl rounded-tr-sm border border-orange-100"
            : "bg-white rounded-2xl rounded-tl-sm border border-gray-100 shadow-sm"
        }`}
      >
        {!isUser && (
          <div className="flex items-center gap-1.5 mb-1">
            <div className="w-1.5 h-1.5 rounded-full bg-[#FF9933]" />
            <span className="text-[11px] font-semibold text-[#000080] font-['Mukta']">
              नागरिक सहायक
            </span>
          </div>
        )}

        <p className="text-sm text-gray-800 leading-relaxed whitespace-pre-line font-['Nunito']">
          {message.content}
        </p>

        <div className="flex items-center justify-end gap-1 mt-1">
          <span className="text-[10px] text-gray-400">
            {formatTime(message.created_at)}
          </span>
          {isUser && (
            <CheckCheck
              size={14}
              data-testid={`tick-${isRead ? "blue" : isBot ? "blue" : "grey"}`}
              className={`${
                isRead ? "text-[#000080]" : "text-gray-400"
              } transition-colors`}
            />
          )}
        </div>
      </div>
    </div>
  );
};

function formatTime(isoString) {
  if (!isoString) return "";
  const d = new Date(isoString);
  return d.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", hour12: true });
}

export const TypingIndicator = () => (
  <div data-testid="typing-indicator" className="flex justify-start animate-fade-in-up">
    <div className="bg-white rounded-2xl rounded-tl-sm px-4 py-3 border border-gray-100 shadow-sm">
      <div className="flex items-center gap-1.5 mb-1">
        <div className="w-1.5 h-1.5 rounded-full bg-[#FF9933]" />
        <span className="text-[11px] font-semibold text-[#000080] font-['Mukta']">
          नागरिक सहायक
        </span>
      </div>
      <div className="flex gap-1.5 py-1">
        <div className="w-2 h-2 rounded-full bg-gray-400 typing-dot" />
        <div className="w-2 h-2 rounded-full bg-gray-400 typing-dot" />
        <div className="w-2 h-2 rounded-full bg-gray-400 typing-dot" />
      </div>
    </div>
  </div>
);
