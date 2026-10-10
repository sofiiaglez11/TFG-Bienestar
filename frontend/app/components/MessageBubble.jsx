import React from "react";
import MarkdownContent from "./MarkdownContent";

export default function MessageBubble({ message }) {
  const isUser = message.role === "user";

  const formatDateTime = (ts) => {
    if (!ts) return "";
    try {
      const date = new Date(ts);
      if (isNaN(date.getTime())) return "";

      const now = new Date();
      const isToday =
        date.getDate() === now.getDate() &&
        date.getMonth() === now.getMonth() &&
        date.getFullYear() === now.getFullYear();

      const timeStr = date.toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      });

      if (isToday) {
        return timeStr;
      } else {
        const isSameYear = date.getFullYear() === now.getFullYear();
        const dateStr = date.toLocaleDateString("es-ES", {
          day: "numeric",
          month: "short",
          ...(isSameYear ? {} : { year: "numeric" }),
        });
        return `${dateStr}, ${timeStr}`;
      }
    } catch {
      return "";
    }
  };

  const formattedTime = formatDateTime(message.timestamp);

  return (
    <div
      style={{
        display: "flex",
        justifyContent: isUser ? "flex-end" : "flex-start",
        marginBottom: "12px",
      }}
    >
      {!isUser && (
        <div
          style={{
            width: "28px",
            height: "28px",
            borderRadius: "50%",
            background: "var(--avatar-ai-bg)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: "12px",
            color: "white",
            marginRight: "8px",
            flexShrink: 0,
            marginTop: "4px",
          }}
        >
          IA
        </div>
      )}

      <div
        style={{
          maxWidth: "70%",
          padding: "10px 14px",
          borderRadius: isUser ? "18px 18px 4px 18px" : "18px 18px 18px 4px",
          background: isUser ? "var(--bubble-user-bg)" : "var(--bubble-ai-bg)",
          color: isUser ? "var(--bubble-user-text)" : "var(--text-primary)",
          fontSize: "14px",
          lineHeight: "1.6",
          wordBreak: "break-word",
          display: "flex",
          flexDirection: "column",
        }}
      >
        <div>
          {isUser ? (
            // Mensajes del usuario: texto plano con saltos de línea
            <span style={{ whiteSpace: "pre-wrap" }}>{message.content}</span>
          ) : (
            // Mensajes del asistente: markdown completo
            <MarkdownContent>{message.content}</MarkdownContent>
          )}
        </div>

        {formattedTime && (
          <div
            style={{
              fontSize: "11px",
              opacity: 0.7,
              marginTop: "4px",
              textAlign: "right",
              userSelect: "none",
            }}
          >
            {formattedTime}
          </div>
        )}
      </div>
    </div>
  );
}