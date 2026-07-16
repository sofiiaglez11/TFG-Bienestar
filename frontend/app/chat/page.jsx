"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import ChatWindow from "../components/ChatWindow";
import ChatInput from "../components/ChatInput";

const BACKEND_URL = "http://localhost:8000";

// TODO: añadir apartado de configuración, autodetectar modo oscuro/ modo diurno para intercambiar colores

export default function ChatPage() {
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const router = useRouter();

  // si no se ha iniciado sesión (no hay token), redirige al usuario a la página de inicio de sesión
  useEffect(() => {
    const token = localStorage.getItem("token"); // obtener el token del localStorage
    if (!token) {
      router.push("/login"); // redirigir a la página de inicio de sesión
    }
  }, [router]); // si cambia el router, se ejecuta de nuevo

  const sendMessage = async (text) => {

    const token = localStorage.getItem("token"); // obtener el token del localStorage
    if (!token) {
      router.push("/login"); // redirigir a la página de inicio de sesión
      return;
    }



    // Agregar el mensaje del usuario al historial de chat
    const userMessage = { role: "user", content: text };
    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);
    setError(null);

    try {
      const res = await fetch(`${BACKEND_URL}/api/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
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

  const handleLogout = () => {
    localStorage.removeItem("token");
    router.push("/login");
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

        {/* Botón de cerrar sesión */}
        <button
          onClick={handleLogout}
          style={{
            marginLeft: "auto",
            padding: "6px 12px",
            background: "transparent",
            border: "1px solid var(--border)",
            borderRadius: "6px",
            color: "var(--text-secondary)",
            fontSize: "13px",
            cursor: "pointer",
            transition: "all 0.2s",
          }}
          onMouseOver={(e) => {
            e.currentTarget.style.color = "var(--text-primary)";
            e.currentTarget.style.borderColor = "var(--text-primary)";
          }}
          onMouseOut={(e) => {
            e.currentTarget.style.color = "var(--text-secondary)";
            e.currentTarget.style.borderColor = "var(--border)";
          }}
        >
          Cerrar sesión
        </button>
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
