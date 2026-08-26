"use client";

import { useState, useEffect } from "react";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

export default function ClockifyConfigModal({ isOpen, onClose, onSuccess }) {
  const [token, setToken] = useState("");
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState(null);
  const [showKey, setShowKey] = useState(false);
  const [showGuide, setShowGuide] = useState(false);

  useEffect(() => {
    if (isOpen) {
      fetchStatus();
      setMessage(null);
      setToken("");
      setShowKey(false);
    }
  }, [isOpen]);

  const fetchStatus = async () => {
    const jwt = localStorage.getItem("token");
    if (!jwt) return;
    try {
      const res = await fetch(`${BACKEND_URL}/api/user/clockify-status`, {
        headers: { Authorization: `Bearer ${jwt}` },
      });
      if (res.ok) {
        const data = await res.json();
        setStatus(data);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMessage(null);

    const jwt = localStorage.getItem("token");
    try {
      const res = await fetch(`${BACKEND_URL}/api/user/clockify-credentials`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${jwt}`,
        },
        body: JSON.stringify({ token, auth_type: "api_key" }),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || "Error al conectar con Clockify");
      }

      setMessage({ type: "success", text: "¡Cuenta de Clockify vinculada correctamente!" });
      setToken("");
      fetchStatus();
      if (onSuccess) onSuccess();
    } catch (err) {
      setMessage({ type: "error", text: err.message });
    } finally {
      setLoading(false);
    }
  };

  const handleDisconnect = async () => {
    const jwt = localStorage.getItem("token");
    if (!jwt) return;
    setLoading(true);
    try {
      await fetch(`${BACKEND_URL}/api/user/clockify-credentials`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${jwt}` },
      });
      setStatus(null);
      setMessage({ type: "success", text: "Cuenta de Clockify desconectada." });
    } catch {
      setMessage({ type: "error", text: "Error al desconectar. Inténtalo de nuevo." });
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  const isConnected = status?.connected;

  const steps = [
    {
      step: "1",
      text: "Inicia sesión en ",
      link: { label: "Clockify", href: "https://app.clockify.me" }
    },
    {
      step: "2",
      text: "Genera tu clave en ",
      link: { label: "Settings > Manage Api Keys", href: "https://app.clockify.me/manage-api-keys" }
    },
  ];

  return (
    <div
      onClick={(e) => e.target === e.currentTarget && onClose()}
      style={{
        position: "fixed",
        inset: 0,
        backgroundColor: "rgba(0,0,0,0.55)",
        backdropFilter: "blur(4px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 1000,
        padding: "16px",
      }}
    >
      <div
        style={{
          backgroundColor: "var(--bg-surface)",
          borderRadius: "16px",
          width: "100%",
          maxWidth: "500px",
          boxShadow: "0 24px 48px rgba(0,0,0,0.3)",
          overflow: "hidden",
          border: "1px solid var(--border)",
        }}
      >
        {/* Header con gradiente */}
        <div
          style={{
            background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
            padding: "20px 24px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>

            <div>
              <h3 style={{ margin: 0, fontSize: "1.1rem", fontWeight: "700", color: "#fff" }}>
                Conectar Clockify
              </h3>
              <p style={{ margin: 0, fontSize: "12px", color: "rgba(255,255,255,0.75)" }}>
                Vincula tu cuenta para el análisis de hábitos
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label="Cerrar"
            style={{
              background: "rgba(255,255,255,0.15)",
              border: "none",
              borderRadius: "8px",
              width: "32px",
              height: "32px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              cursor: "pointer",
              color: "#fff",
              fontSize: "18px",
              lineHeight: 1,
              transition: "background 0.15s",
            }}
            onMouseOver={(e) => (e.currentTarget.style.background = "rgba(255,255,255,0.25)")}
            onMouseOut={(e) => (e.currentTarget.style.background = "rgba(255,255,255,0.15)")}
          >
            ×
          </button>
        </div>

        <div style={{ padding: "24px" }}>
          {/* Badge de estado */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "10px",
              padding: "12px 16px",
              borderRadius: "10px",
              marginBottom: "20px",
              backgroundColor: isConnected ? "rgba(34,197,94,0.1)" : "rgba(239,68,68,0.08)",
              border: `1px solid ${isConnected ? "rgba(34,197,94,0.3)" : "rgba(239,68,68,0.2)"}`,
            }}
          >

            <div style={{ flex: 1 }}>
              <div style={{ fontSize: "13px", fontWeight: "600", color: "var(--text-primary)" }}>
                {isConnected ? "Cuenta conectada" : "Sin cuenta vinculada"}
              </div>
              {isConnected && status?.workspace_name && (
                <div style={{ fontSize: "12px", color: "var(--text-secondary)", marginTop: "2px" }}>
                  Espacio:{" "}
                  <strong style={{ color: "var(--text-primary)" }}>{status.workspace_name}</strong>
                </div>
              )}
              {!isConnected && (
                <div style={{ fontSize: "12px", color: "var(--text-secondary)", marginTop: "2px" }}>
                  Introduce tu API Key para comenzar
                </div>
              )}
            </div>

          </div>



          {/* Guía paso a paso (desplegable) */}
          <div
            style={{
              borderRadius: "10px",
              border: "1px solid var(--border)",
              overflow: "hidden",
              marginBottom: "20px",
            }}
          >
            <button
              type="button"
              onClick={() => setShowGuide((v) => !v)}
              style={{
                width: "100%",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "11px 14px",
                backgroundColor: "var(--bg-input)",
                borderBottom: showGuide ? "1px solid var(--border)" : "none",
                borderTop: "none",
                borderLeft: "none",
                borderRight: "none",
                cursor: "pointer",
                fontSize: "11px",
                fontWeight: "700",
                color: "var(--text-secondary)",
                textTransform: "uppercase",
                letterSpacing: "0.06em",
                textAlign: "left",
                transition: "background 0.15s",
              }}
              onMouseOver={(e) => (e.currentTarget.style.backgroundColor = "var(--border)")}
              onMouseOut={(e) => (e.currentTarget.style.backgroundColor = "var(--bg-input)")}
            >
              <span>¿Cómo obtengo mi API Key de Clockify?</span>
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                style={{
                  flexShrink: 0,
                  transform: showGuide ? "rotate(180deg)" : "rotate(0deg)",
                  transition: "transform 0.2s ease",
                }}
              >
                <polyline points="6 9 12 15 18 9"></polyline>
              </svg>
            </button>
            {showGuide && steps.map((item, i) => (
              <div
                key={item.step}
                style={{
                  display: "flex",
                  alignItems: "flex-start",
                  gap: "12px",
                  padding: "10px 14px",
                  borderBottom: i < steps.length - 1 ? "1px solid var(--border)" : "none",
                  backgroundColor: "var(--bg-surface)",
                }}
              >
                <span
                  style={{
                    flexShrink: 0,
                    width: "22px",
                    height: "22px",
                    borderRadius: "50%",
                    background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
                    color: "#fff",
                    fontSize: "11px",
                    fontWeight: "700",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    marginTop: "1px",
                  }}
                >
                  {item.step}
                </span>
                <span style={{ fontSize: "13px", color: "var(--text-primary)", lineHeight: "1.6" }}>
                  {item.text}
                  {item.link && (
                    <a
                      href={item.link.href}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{ color: "var(--brand)", textDecoration: "underline" }}
                    >
                      {item.link.label}
                    </a>
                  )}
                </span>
              </div>
            ))}
          </div>

          {/* Formulario */}
          <form onSubmit={handleSubmit}>
            <div style={{ marginBottom: "16px" }}>
              <label
                htmlFor="clockify-api-key"
                style={{
                  display: "block",
                  fontSize: "13px",
                  fontWeight: "600",
                  marginBottom: "6px",
                  color: "var(--text-primary)",
                }}
              >
                API Key de Clockify
              </label>
              <div style={{ position: "relative" }}>
                <input
                  id="clockify-api-key"
                  type={showKey ? "text" : "password"}
                  value={token}
                  onChange={(e) => setToken(e.target.value)}
                  placeholder="Pega aquí tu API Key…"
                  required
                  autoComplete="off"
                  style={{
                    width: "100%",
                    padding: "10px 44px 10px 12px",
                    borderRadius: "8px",
                    border: "1px solid var(--border)",
                    backgroundColor: "var(--bg-input)",
                    color: "var(--text-primary)",
                    fontSize: "14px",
                    boxSizing: "border-box",
                    outline: "none",
                    transition: "border-color 0.15s",
                    fontFamily: showKey ? "monospace" : "inherit",
                  }}
                  onFocus={(e) => (e.target.style.borderColor = "var(--border-focus)")}
                  onBlur={(e) => (e.target.style.borderColor = "var(--border)")}
                />
                <button
                  type="button"
                  onClick={() => setShowKey((v) => !v)}
                  title={showKey ? "Ocultar" : "Mostrar"}
                  style={{
                    position: "absolute",
                    right: "10px",
                    top: "50%",
                    transform: "translateY(-50%)",
                    background: "transparent",
                    border: "none",
                    cursor: "pointer",
                    padding: "4px",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "var(--text-secondary)",
                  }}
                >
                  {showKey ? (
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path>
                      <line x1="1" y1="1" x2="23" y2="23"></line>
                    </svg>
                  ) : (
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                      <circle cx="12" cy="12" r="3"></circle>
                    </svg>
                  )}
                </button>
              </div>
            </div>

            {/* Mensaje feedback */}
            {message && (
              <div
                style={{
                  padding: "10px 14px",
                  borderRadius: "8px",
                  marginBottom: "16px",
                  fontSize: "13px",
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                  backgroundColor: message.type === "success" ? "rgba(34,197,94,0.1)" : "rgba(239,68,68,0.1)",
                  color: message.type === "success" ? "#16a34a" : "#dc2626",
                  border: `1px solid ${message.type === "success" ? "rgba(34,197,94,0.25)" : "rgba(239,68,68,0.25)"}`,
                }}
              >
                {message.text}
              </div>
            )}

            <div style={{ display: "flex", gap: "10px", justifyContent: "flex-end" }}>
              <button
                type="button"
                onClick={onClose}
                style={{
                  padding: "9px 18px",
                  borderRadius: "8px",
                  border: "1px solid var(--border)",
                  backgroundColor: "transparent",
                  color: "var(--text-primary)",
                  cursor: "pointer",
                  fontSize: "14px",
                  fontWeight: "500",
                  transition: "background 0.15s",
                }}
                onMouseOver={(e) => (e.currentTarget.style.backgroundColor = "var(--bg-input)")}
                onMouseOut={(e) => (e.currentTarget.style.backgroundColor = "transparent")}
              >
                Cancelar
              </button>
              <button
                type="submit"
                disabled={loading || !token.trim()}
                style={{
                  padding: "9px 20px",
                  borderRadius: "8px",
                  border: "none",
                  background: loading || !token.trim()
                    ? "var(--bg-input)"
                    : "linear-gradient(135deg, #6366f1, #8b5cf6)",
                  color: loading || !token.trim() ? "var(--text-secondary)" : "#ffffff",
                  cursor: loading || !token.trim() ? "not-allowed" : "pointer",
                  fontWeight: "600",
                  fontSize: "14px",
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                  transition: "opacity 0.15s",
                }}
              >
                {loading ? "Verificando…" : ` ${isConnected ? "Actualizar clave" : "Conectar cuenta"}`}
              </button>
            </div>
          </form>


        </div>
      </div>
    </div>
  );
}
