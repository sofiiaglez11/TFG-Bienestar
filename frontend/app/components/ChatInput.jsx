import { useState, useRef, useEffect } from "react";
import { Send } from "lucide-react";

export default function ChatInput({ onSend, isLoading, disabled = false }) {
  const [text, setText] = useState("");
  const textareaRef = useRef(null);

  // Recalcular la altura en función del texto ingresado
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "42px";
      const scrollH = textareaRef.current.scrollHeight;
      const maxH = window.innerHeight * 0.2;

      if (scrollH > maxH) {
        textareaRef.current.style.height = `${maxH}px`;
        textareaRef.current.style.overflowY = "auto";
      } else {
        textareaRef.current.style.height = `${scrollH}px`;
        textareaRef.current.style.overflowY = "hidden";
      }
    }
  }, [text]);

  const handleSend = () => {
    const trimmed = text.trim();
    if (!trimmed || isLoading || disabled) return;
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
        borderTop: "1px solid var(--border)",
        background: "var(--bg-surface)",
        display: "flex",
        gap: "10px",
        alignItems: "flex-end",
      }}
    >
      <textarea
        ref={textareaRef}
        value={disabled ? "" : text}
        onChange={(e) => { if (!disabled) setText(e.target.value); }}
        onKeyDown={handleKeyDown}
        readOnly={disabled}
        placeholder={
          disabled
            ? "⚠️ Configura Clockify desde tu perfil para empezar a chatear..."
            : "Escribe un mensaje... (Enter para enviar)"
        }
        style={{
          flex: 1,
          resize: "none",
          border: `1px solid ${disabled ? "var(--border)" : "var(--border)"}`,
          borderRadius: "12px",
          padding: "10px 14px",
          fontSize: "14px",
          fontFamily: "inherit",
          outline: "none",
          lineHeight: "1.5",
          minHeight: "42px",
          maxHeight: "20vh",
          overflowY: "hidden",
          color: disabled ? "var(--text-secondary)" : "var(--text-primary)",
          background: disabled ? "var(--bg-page)" : "var(--bg-input)",
          transition: "border-color 0.15s",
          boxSizing: "border-box",
          cursor: disabled ? "not-allowed" : "text",
          opacity: disabled ? 0.6 : 1,
        }}
        onFocus={(e) => {
          if (!disabled) e.target.style.borderColor = "var(--border-focus)";
        }}
        onBlur={(e) => (e.target.style.borderColor = "var(--border)")}
      />

      <button
        onClick={handleSend}
        disabled={!text.trim() || isLoading || disabled}
        style={{
          width: "40px",
          height: "40px",
          borderRadius: "10px",
          border: "none",
          background: !text.trim() || isLoading || disabled ? "var(--bg-input)" : "var(--brand)",
          color: "var(--text-primary)",
          cursor: !text.trim() || isLoading || disabled ? "not-allowed" : "pointer",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
          transition: "background 0.15s",
          fontSize: "16px",
          opacity: disabled ? 0.5 : 1,
        }}
        aria-label="Enviar mensaje"
      >
        <Send size={16} />
      </button>
    </div>
  );
}
