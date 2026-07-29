"use client";

import { useState, useEffect } from "react";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

export default function ClockifyConfigModal({ isOpen, onClose }) {
  const [authType, setAuthType] = useState("api_key");
  const [token, setToken] = useState("");
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState(null);

  useEffect(() => {
    if (isOpen) {
      fetchStatus();
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
        if (data.auth_type) setAuthType(data.auth_type);
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
        body: JSON.stringify({ token, auth_type: authType }),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || "Error al conectar con Clockify");
      }

      setMessage({ type: "success", text: "¡Cuenta de Clockify vinculada correctamente!" });
      setToken("");
      fetchStatus();
    } catch (err) {
      setMessage({ type: "error", text: err.message });
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div style={{
      position: "fixed",
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      backgroundColor: "rgba(0, 0, 0, 0.5)",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      zIndex: 1000
    }}>
      <div style={{
        backgroundColor: "#ffffff",
        borderRadius: "12px",
        padding: "24px",
        width: "90%",
        maxWidth: "480px",
        boxShadow: "0 10px 25px rgba(0,0,0,0.2)",
        color: "#1e293b"
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
          <h3 style={{ margin: 0, fontSize: "1.25rem", fontWeight: "600" }}>Conexión con Clockify</h3>
          <button
            onClick={onClose}
            style={{ background: "none", border: "none", fontSize: "1.5rem", cursor: "pointer", color: "#64748b" }}
          >
            &times;
          </button>
        </div>

        {/* Estado actual */}
        <div style={{
          padding: "12px 16px",
          borderRadius: "8px",
          backgroundColor: status?.connected ? "#f0fdf4" : "#fef2f2",
          border: `1px solid ${status?.connected ? "#bbf7d0" : "#fecaca"}`,
          marginBottom: "16px",
          fontSize: "14px"
        }}>
          <strong>Estado: </strong>
          {status?.connected ? (
            <span style={{ color: "#166534" }}>✅ Conectado </span>
          ) : (
            <span style={{ color: "#991b1b" }}>❌ No conectado a ningún espacio de Clockify</span>
          )}
        </div>

        {message && (
          <div style={{
            padding: "10px 14px",
            borderRadius: "6px",
            marginBottom: "14px",
            fontSize: "13px",
            backgroundColor: message.type === "success" ? "#ecfdf5" : "#fff1f2",
            color: message.type === "success" ? "#047857" : "#be123c",
          }}>
            {message.text}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: "16px" }}>
            <label style={{ display: "block", fontSize: "13px", fontWeight: "500", marginBottom: "4px" }}>
              API Key de Clockify:
            </label>
            <input
              type="password"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder={"Pega tu API Key de Clockify"}
              required
              style={{
                width: "100%",
                padding: "10px 12px",
                borderRadius: "6px",
                border: "1px solid #cbd5e1",
                fontSize: "14px",
                boxSizing: "border-box"
              }}
            />
            <small style={{ color: "#64748b", fontSize: "12px", display: "block", marginTop: "4px" }}>
              Consigue tu API Key personal en tu{" "}
              <a
                href="https://app.clockify.me/manage-api-keys"
                target="_blank"
                rel="noopener noreferrer"
                style={{ color: "#2563eb", textDecoration: "underline" }}
              >
                Perfil de Clockify aquí
              </a>
            </small>
          </div>

          <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px" }}>
            <button
              type="button"
              onClick={onClose}
              style={{
                padding: "8px 16px",
                borderRadius: "6px",
                border: "1px solid #cbd5e1",
                backgroundColor: "#f1f5f9",
                color: "#475569",
                cursor: "pointer",
                fontSize: "14px"
              }}
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={loading}
              style={{
                padding: "8px 16px",
                borderRadius: "6px",
                border: "none",
                backgroundColor: "#2563eb",
                color: "#ffffff",
                cursor: loading ? "not-allowed" : "pointer",
                fontWeight: "500",
                fontSize: "14px"
              }}
            >
              {loading ? "Verificando..." : "Guardar y Conectar"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
