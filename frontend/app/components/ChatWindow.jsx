import { useEffect, useRef } from "react";
import MessageBubble from "./MessageBubble";

export default function ChatWindow({ messages, isLoading }) {
  const bottomRef = useRef(null);

  // Auto-scroll to the last message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  return (
    <div
      style={{
        flex: 1,
        overflowY: "auto",
        padding: "24px 16px",
        display: "flex",
        flexDirection: "column",
      }}
    >
      {messages.length === 0 && (
        <div
          style={{
            margin: "auto",
            textAlign: "center",
            color: "var(--text-secondary)",
          }}
        >
          <div style={{ fontSize: "40px", marginBottom: "12px" }}>💬</div>
          <p style={{ fontSize: "15px" }}>
            Escríbeme algo para empezar. Puedo ayudarte a gestionar tu tiempo de estudio con Clockify.
          </p>
        </div>
      )}

      {messages.map((msg, index) => (
        <MessageBubble key={index} message={msg} />
      ))}

      {isLoading && (
        <div style={{ 
          display: "flex", 
          alignItems: "center", 
          gap: "6px", 
          padding: "4px 0"
          }}>
          <div
            style={{
              width: "28px",
              height: "28px",
              borderRadius: "50%",
              background: "linear-gradient(135deg, var(--brand), var(--brand))",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "12px",
              color: "var(--text-primary)",
              flexShrink: 0,
            }}
          >
            IA
          </div>
          <div
            style={{
              padding: "10px 14px",
              borderRadius: "18px 18px 18px 4px",
              background: "var(--bg-input)",
              display: "flex",
              gap: "4px",
              alignItems: "center",
            }}
          >
            {[0, 1, 2].map((i) => (
              <span
                key={i}
                style={{
                  width: "6px",
                  height: "6px",
                  borderRadius: "50%",
                  background: "var(--text-secondary)",
                  animation: "bounce 1.2s infinite",
                  animationDelay: `${i * 0.2}s`,
                  display: "inline-block",
                }}
              />
            ))}
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}
