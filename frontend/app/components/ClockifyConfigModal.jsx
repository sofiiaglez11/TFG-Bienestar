"use client";

import ClockifyConfigPanel from "./ClockifyConfigPanel";

export default function ClockifyConfigModal({ isOpen, onClose, onSuccess }) {
  if (!isOpen) return null;

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
          <ClockifyConfigPanel isActive={isOpen} onSuccess={onSuccess} onCancel={onClose} />
        </div>
      </div>
    </div>
  );
}