import { useState } from "react";
import { Send } from "lucide-react";

export default function ChatInput({ onSend, isLoading }) {
  const [text, setText] = useState("");

  const handleSend = () => {
    const trimmed = text.trim();
    if (!trimmed || isLoading) return;
    onSend(trimmed);
    setText("");
  };

  const handleKeyDown = (e) => {
    // Send with Enter, new line with Shift+Enter
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div
      style={{
        padding: "16px",
        borderTop: "1px solid #e5e7eb",
        background: "white",
        display: "flex",
        gap: "10px",
        alignItems: "flex-end",
      }}
    >
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Escribe un mensaje... (Enter para enviar)"
        rows={1}
        style={{
          flex: 1,
          resize: "none",
          border: "1px solid #e5e7eb",
          borderRadius: "12px",
          padding: "10px 14px",
          fontSize: "14px",
          fontFamily: "inherit",
          outline: "none",
          lineHeight: "1.5",
          maxHeight: "120px",
          overflowY: "auto",
          color: "#111827",
          background: "#f9fafb",
          transition: "border-color 0.15s",
        }}
        onFocus={(e) => (e.target.style.borderColor = "#6366f1")}
        onBlur={(e) => (e.target.style.borderColor = "#e5e7eb")}
      />

      <button
        onClick={handleSend}
        disabled={!text.trim() || isLoading}
        style={{
          width: "40px",
          height: "40px",
          borderRadius: "10px",
          border: "none",
          background: !text.trim() || isLoading ? "#e5e7eb" : "#6366f1",
          color: "white",
          cursor: !text.trim() || isLoading ? "not-allowed" : "pointer",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
          transition: "background 0.15s",
          fontSize: "16px",
        }}
        aria-label="Enviar mensaje"
      >
        <Send size={16} />
        
      </button>
    </div>
  );
}
