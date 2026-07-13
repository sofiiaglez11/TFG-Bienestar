"use client";

import { useState } from "react";
import ChatWindow from "../components/ChatWindow";
import ChatInput from "../components/ChatInput";

const BACKEND_URL = "http://localhost:8000";

// TODO: añadir apartado de configuración, autodetectar modo oscuro/ modo diurno para intercambiar colores

export default function ChatPage() {
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const sendMessage = async (text) => {
    // Add the user's message to the chat history
    const userMessage = { role: "user", content: text };
    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);
    setError(null);

    try {
      const res = await fetch(`${BACKEND_URL}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text }),
      });

      if (!res.ok) {
        throw new Error(`Error del servidor: ${res.status}`);
      }

      const data = await res.json();

      // Add the assistant's response to the chat history
      const assistantMessage = { role: "assistant", content: data.response };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      setError("eRROR EN EL SERVIDOR"); 
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100vh",
        background: "var(--bg-page)",
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: "14px 20px",
          borderBottom: "1px solid var(--border)",
          background: "var(--bg-header)",
          display: "flex",
          alignItems: "center",
          gap: "10px",
        }}
      >
        <div
          style={{
            width: "32px",
            height: "32px",
            borderRadius: "50%",
            background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
          }}
        />
        <div>
          <div style={{ fontWeight: 600, fontSize: "14px", color: "var(--text-primary)" }}>
            Asistente de bienestar
          </div>
          <div style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
            Conectado a Clockify
          </div>
        </div>
      </div>

      {/* Message Area */}
      <ChatWindow messages={messages} isLoading={isLoading} />

      {/* Error */}
      {error && (
        <div
          style={{
            margin: "0 16px 8px",
            padding: "10px 14px",
            background: "#fef2f2",
            border: "1px solid #fecaca",
            borderRadius: "8px",
            color: "#dc2626",
            fontSize: "13px",
          }}
        >
          {error}
        </div>
      )}

      {/* Input */}
      <ChatInput onSend={sendMessage} isLoading={isLoading} />

      {/* Animation of the loading dots */}
      <style>{`
        @keyframes bounce {
          0%, 60%, 100% { transform: translateY(0); }
          30% { transform: translateY(-4px); }
        }
      `}</style>
    </div>
  );
}
