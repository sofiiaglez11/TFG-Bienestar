import { useState } from 'react';
import { Users, GraduationCap, Calendar } from 'lucide-react';
import MarkdownContent from '../MarkdownContent';

/* CONFIGURACIÓN */

export const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
export const YEAR_OPTIONS = ["2024/25", "2025/26", "2026/27", "2027/28", "2028/29"];
export const getToken = () => (typeof window !== "undefined" ? localStorage.getItem("token") : null);
export const authHeaders = (token) => ({ Authorization: `Bearer ${token}` });

/* COMPONENTES PEQUEÑOS*/

export function Badge({ children, color = "#6366f1" }) {
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: "4px",
      padding: "2px 10px", borderRadius: "20px", fontSize: "11px", fontWeight: "600",
      background: `${color}20`, color, border: `1px solid ${color}40`
    }}>{children}</span>
  );
}

export function StatBadge({ label, value, color = "#6366f1" }) {
  return (
    <div style={{
      background: `${color}12`, border: `1px solid ${color}30`,
      borderRadius: "12px", padding: "12px 16px", textAlign: "center", minWidth: "100px"
    }}>
      <div style={{ fontSize: "20px", fontWeight: "800", color }}>{value ?? "—"}</div>
      <div style={{ fontSize: "11px", color: "var(--text-secondary)", marginTop: "2px", fontWeight: "500" }}>{label}</div>
    </div>
  );
}

export function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = () => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };
  return (
    <button
      onClick={handleCopy}
      style={{
        padding: "6px 14px", borderRadius: "8px", border: "1px solid var(--border)",
        background: copied ? "#10b981" : "var(--bg-input)", color: copied ? "#fff" : "var(--text-primary)",
        fontSize: "12px", fontWeight: "600", cursor: "pointer", transition: "all 0.2s"
      }}
    >
      {copied ? "Copiado" : "Copiar"}
    </button>
  );
}

export function BackButton({ onClick, children }) {
  return (
    <button
      onClick={onClick}
      style={{
        background: "none", border: "none", color: "var(--text-secondary)",
        fontSize: "13px", cursor: "pointer", padding: "0 0 16px 0",
        display: "flex", alignItems: "center", gap: "6px"
      }}
    >
      {children}
    </button>
  );
}

export function ErrorBanner({ message, style }) {
  if (!message) return null;
  return (
    <div style={{
      padding: "12px 16px", background: "#fef2f2", border: "1px solid #fecaca",
      borderRadius: "10px", color: "#dc2626", fontSize: "13px", ...style
    }}>
      {message}
    </div>
  );
}

export function EmptyState({ emoji, icon, padding = "40px", children }) {
  return (
    <div style={{
      textAlign: "center", padding, background: "var(--bg-surface)",
      border: "1px dashed var(--border)", borderRadius: "16px"
    }}>
      {icon && <div style={{ display: "flex", justifyContent: "center", marginBottom: "12px", color: "var(--text-secondary)" }}>{icon}</div>}
      {!icon && emoji && <div style={{ fontSize: "40px", marginBottom: "12px" }}>{emoji}</div>}
      <p style={{ margin: 0, color: "var(--text-secondary)", fontSize: "14px" }}>{children}</p>
    </div>
  );
}

export function Modal({ children, maxWidth = "480px" }) {
  return (
    <div style={{
      position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", backdropFilter: "blur(4px)",
      display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000, padding: "20px"
    }}>
      <div style={{
        background: "var(--bg-surface)", border: "1px solid var(--border)",
        borderRadius: "20px", padding: "32px", width: "100%", maxWidth,
        boxShadow: "0 20px 60px rgba(0,0,0,0.3)"
      }}>
        {children}
      </div>
    </div>
  );
}

/* LAYOUT DE PÁGINA */

const shellStyle = {
  backgroundColor: "var(--bg-surface)",
  border: "1px solid var(--border)",
  borderRadius: "16px",
  padding: "28px",
  width: "100%",
  height: "100%",
  overflowY: "auto",
  color: "var(--text-primary)",
  fontFamily: "'Inter', 'Segoe UI', sans-serif",
};

/** Contenedor común. maxWidth centra el contenido; center lo centra en ambos ejes (carga/error). */
export function PageShell({ children, maxWidth, center = false }) {
  const style = center
    ? { ...shellStyle, display: "flex", alignItems: "center", justifyContent: "center" }
    : shellStyle;
  return (
    <div style={style}>
      {maxWidth ? <div style={{ maxWidth, margin: "0 auto" }}>{children}</div> : children}
    </div>
  );
}

/** Mensaje a pantalla completa (cargando / error). Con onBack muestra botón para volver. */
export function FullPageMessage({ emoji, icon, children, error = false, onBack, backLabel = "← Volver" }) {
  return (
    <PageShell center>
      <div style={error
        ? { textAlign: "center", color: "#ef4444", background: "var(--bg-surface)", padding: "32px", borderRadius: "16px", border: "1px solid var(--border)" }
        : { textAlign: "center", color: "var(--text-secondary)" }
      }>
        {icon && <div style={{ display: "flex", justifyContent: "center", marginBottom: "12px" }}>{icon}</div>}
        {!icon && emoji && <div style={{ fontSize: "40px", marginBottom: "12px" }}>{emoji}</div>}
        {children}
        {onBack && (
          <>
            <br />
            <button
              onClick={onBack}
              style={{ marginTop: "16px", padding: "8px 16px", borderRadius: "8px", border: "1px solid var(--border)", background: "none", cursor: "pointer", color: "var(--text-primary)" }}
            >
              {backLabel}
            </button>
          </>
        )}
      </div>
    </PageShell>
  );
}

/** Cabecera de un curso (la usan la página del profesor y la del alumno). Los botones van como children. */
export function CourseHeader({ course, isTeacher, studentsCount = 0, summariesCount = 0, children }) {
  return (
    <div style={{
      background: "var(--bg-surface)", border: "1px solid var(--border)",
      borderRadius: "20px", padding: "28px", marginBottom: "24px",
      position: "relative", overflow: "hidden"
    }}>
      <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: "4px", background: "linear-gradient(90deg, #6366f1, #8b5cf6, #ec4899)" }} />

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "16px" }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "8px" }}>
            {isTeacher ? <Users size={32} color="var(--brand)" /> : <GraduationCap size={32} color="var(--brand)" />}
            <div>
              <h1 style={{ margin: 0, fontSize: "24px", fontWeight: "800", color: "var(--text-primary)" }}>{course?.name}</h1>
              {course?.academic_year && (
                <span style={{ fontSize: "13px", color: "var(--text-secondary)", fontWeight: "500", display: "flex", alignItems: "center", gap: "4px" }}>
                  <Calendar size={13} />
                  Curso {course.academic_year}
                </span>
              )}
            </div>
          </div>

          {course?.description && (
            <p style={{ margin: "0 0 16px", fontSize: "14px", color: "var(--text-secondary)", lineHeight: "1.6", maxWidth: "500px" }}>
              {course.description}
            </p>
          )}

          {isTeacher && (
            <div style={{ display: "flex", alignItems: "center", gap: "10px", padding: "10px 16px", background: "var(--bg-page)", borderRadius: "10px", border: "1px solid var(--border)", width: "fit-content" }}>
              <span style={{ fontSize: "13px", color: "var(--text-secondary)", fontWeight: "500" }}>Código de inscripción:</span>
              <span style={{ fontFamily: "monospace", fontSize: "16px", fontWeight: "800", color: "var(--text-primary)", letterSpacing: "3px" }}>
                {course?.enrollment_code}
              </span>
              <CopyButton text={course?.enrollment_code} />
            </div>
          )}
        </div>

        {isTeacher && (
          <div style={{ display: "flex", gap: "12px", flexWrap: "wrap" }}>
            <StatBadge label="Alumnos" value={studentsCount} color="#6366f1" />
            {/*<StatBadge label="Con resumen" value={summariesCount} color="#10b981" />*/}
          </div>
        )}
      </div>

      {children && (
        <div style={{ display: "flex", gap: "10px", marginTop: "20px", flexWrap: "wrap" }}>{children}</div>
      )}
    </div>
  );
}

/* MARKDOWN
   La lógica de renderizado vive en ../MarkdownContent (la misma que usa MessageBubble).
   Aquí solo se aplica el estilo de texto del contenedor. */

/** Uso: <MarkdownText>{texto}</MarkdownText> */
export function MarkdownText({ children }) {
  return (
    <div style={{ fontSize: "14px", lineHeight: "1.6", color: "var(--text-primary)", wordBreak: "break-word" }}>
      <MarkdownContent>{children}</MarkdownContent>
    </div>
  );
}