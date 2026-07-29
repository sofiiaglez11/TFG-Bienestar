"use client";

import { useState, useEffect } from "react";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

export default function StudentDashboard({ isOpen, onClose, isInline = false }) {
  const [analytics, setAnalytics] = useState([]);
  const [loading, setLoading] = useState(false);
  const [savingGradeId, setSavingGradeId] = useState(null);
  const [gradeInputs, setGradeInputs] = useState({});

  useEffect(() => {
    if (isOpen || isInline) {
      fetchAnalytics();
    }
  }, [isOpen, isInline]);

  const fetchAnalytics = async () => {
    setLoading(true);
    const token = localStorage.getItem("token");
    if (!token) return;
    try {
      const res = await fetch(`${BACKEND_URL}/api/dashboard/student-analytics`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setAnalytics(data.analytics || []);
        const initialGrades = {};
        (data.analytics || []).forEach((item) => {
          initialGrades[item.id] = item.grade !== undefined && item.grade !== null ? item.grade : "";
        });
        setGradeInputs(initialGrades);
      }
    } catch (err) {
      console.error("Error al cargar analíticas:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleGradeChange = (subjectId, val) => {
    setGradeInputs((prev) => ({ ...prev, [subjectId]: val }));
  };

  const saveGrade = async (subjectId) => {
    const token = localStorage.getItem("token");
    const val = parseFloat(gradeInputs[subjectId]);
    if (isNaN(val) || val < 0 || val > 10) {
      alert("Por favor introduce una nota válida entre 0 y 10.");
      return;
    }
    setSavingGradeId(subjectId);
    try {
      const res = await fetch(`${BACKEND_URL}/api/subjects/${subjectId}/grades`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ grade: val }),
      });
      if (res.ok) {
        fetchAnalytics();
      }
    } catch (err) {
      console.error(err);
    } finally {
      setSavingGradeId(null);
    }
  };

  const totalHours = analytics.reduce((acc, curr) => acc + (curr.hours || 0), 0);
  const gradedSubjects = analytics.filter((s) => s.grade !== null && s.grade !== undefined && s.grade !== "");
  const avgGrade = gradedSubjects.length > 0
    ? (gradedSubjects.reduce((acc, curr) => acc + Number(curr.grade), 0) / gradedSubjects.length).toFixed(2)
    : "N/A";

  const handlePrintReport = () => {
    window.print();
  };

  if (!isOpen && !isInline) return null;

  return (
    <div style={isInline ? {
      width: "100%",
      height: "100%",
      display: "flex",
      flexDirection: "column",
      color: "var(--text-primary)"
    } : {
      position: "fixed",
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      backgroundColor: "rgba(0,0,0,0.6)",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      zIndex: 1000,
      padding: "20px"
    }}>
      <div style={isInline ? {
        backgroundColor: "var(--bg-header)",
        border: "1px solid var(--border)",
        borderRadius: "16px",
        padding: "28px",
        width: "100%",
        height: "100%",
        overflowY: "auto",
        boxShadow: "none",
        color: "var(--text-primary)"
      } : {
        backgroundColor: "#ffffff",
        borderRadius: "16px",
        padding: "28px",
        width: "100%",
        maxWidth: "800px",
        maxHeight: "90vh",
        overflowY: "auto",
        boxShadow: "0 20px 30px rgba(0,0,0,0.25)",
        color: "#0f172a"
      }}>
        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
          <div>
            <h2 style={{ margin: 0, fontSize: "1.5rem", fontWeight: "700" }}>📊 Dashboard del Alumno</h2>
            <p style={{ margin: "4px 0 0 0", color: "var(--text-secondary)", fontSize: "14px" }}>
              Relación entre Horas de Estudio (Clockify) vs. Rendimiento (Notas)
            </p>
          </div>
          <div style={{ display: "flex", gap: "10px" }}>
            <button
              onClick={handlePrintReport}
              style={{
                padding: "8px 14px",
                borderRadius: "8px",
                border: "1px solid var(--border)",
                backgroundColor: "var(--bg-page)",
                color: "var(--text-primary)",
                cursor: "pointer",
                fontWeight: "500",
                fontSize: "13px"
              }}
            >
              📄 Exportar PDF
            </button>
            {!isInline && (
              <button
                onClick={onClose}
                style={{ background: "none", border: "none", fontSize: "1.5rem", cursor: "pointer", color: "#64748b" }}
              >
                &times;
              </button>
            )}
          </div>
        </div>

        {/* Tarjetas KPI */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "16px", marginBottom: "24px" }}>
          <div style={{ padding: "16px", borderRadius: "12px", backgroundColor: "#eff6ff", border: "1px solid #bfdbfe" }}>
            <div style={{ fontSize: "13px", color: "#1e40af", fontWeight: "600" }}>Total Horas Estudadas</div>
            <div style={{ fontSize: "1.8rem", fontWeight: "700", color: "#1d4ed8", marginTop: "4px" }}>{totalHours.toFixed(1)} h</div>
          </div>
          <div style={{ padding: "16px", borderRadius: "12px", backgroundColor: "#f0fdf4", border: "1px solid #bbf7d0" }}>
            <div style={{ fontSize: "13px", color: "#166534", fontWeight: "600" }}>Nota Media</div>
            <div style={{ fontSize: "1.8rem", fontWeight: "700", color: "#15803d", marginTop: "4px" }}>{avgGrade} / 10</div>
          </div>
          <div style={{ padding: "16px", borderRadius: "12px", backgroundColor: "#faf5ff", border: "1px solid #e9d5ff" }}>
            <div style={{ fontSize: "13px", color: "#6b21a8", fontWeight: "600" }}>Asignaturas Registradas</div>
            <div style={{ fontSize: "1.8rem", fontWeight: "700", color: "#7e22ce", marginTop: "4px" }}>{analytics.length}</div>
          </div>
        </div>

        {/* Visualización Cruzada Horas vs Nota */}
        <h3 style={{ fontSize: "1.1rem", fontWeight: "600", marginBottom: "12px" }}>Análisis por Asignatura</h3>

        {loading ? (
          <p style={{ color: "#64748b", fontStyle: "italic" }}>Cargando analíticas...</p>
        ) : analytics.length === 0 ? (
          <p style={{ color: "#64748b", backgroundColor: "#f8fafc", padding: "16px", borderRadius: "8px" }}>
            Aún no tienes asignaturas registradas. Pregúntale al bot para añadir tus asignaturas o registrar horas.
          </p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "14px", marginBottom: "24px" }}>
            {analytics.map((item) => {
              const maxHours = Math.max(...analytics.map(a => a.hours), 10);
              const barPercent = Math.min(100, Math.max(5, (item.hours / maxHours) * 100));

              return (
                <div key={item.id} style={{
                  padding: "16px",
                  borderRadius: "10px",
                  border: "1px solid #e2e8f0",
                  backgroundColor: "#f8fafc",
                  display: "flex",
                  flexDirection: "column",
                  gap: "10px"
                }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <span style={{ fontWeight: "600", fontSize: "15px" }}>{item.name}</span>
                    <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                      <span style={{ fontSize: "13px", color: "#475569" }}>⏱️ {item.hours} hrs</span>
                      <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                        <span style={{ fontSize: "13px", fontWeight: "500" }}>Nota:</span>
                        <input
                          type="number"
                          step="0.1"
                          min="0"
                          max="10"
                          value={gradeInputs[item.id] !== undefined ? gradeInputs[item.id] : ""}
                          onChange={(e) => handleGradeChange(item.id, e.target.value)}
                          placeholder="0.0"
                          style={{
                            width: "60px",
                            padding: "4px 8px",
                            borderRadius: "6px",
                            border: "1px solid #cbd5e1",
                            textAlign: "center",
                            fontSize: "14px"
                          }}
                        />
                        <button
                          onClick={() => saveGrade(item.id)}
                          disabled={savingGradeId === item.id}
                          style={{
                            padding: "4px 10px",
                            borderRadius: "6px",
                            border: "none",
                            backgroundColor: "#3b82f6",
                            color: "#ffffff",
                            cursor: "pointer",
                            fontSize: "12px",
                            fontWeight: "500"
                          }}
                        >
                          {savingGradeId === item.id ? "..." : "Guardar"}
                        </button>
                      </div>
                    </div>
                  </div>

                  {/* Barra de progreso visual de horas de estudio */}
                  <div style={{ width: "100%", backgroundColor: "#e2e8f0", height: "10px", borderRadius: "5px", overflow: "hidden" }}>
                    <div style={{
                      width: `${barPercent}%`,
                      backgroundColor: item.grade >= 5 ? "#22c55e" : item.grade !== null && item.grade !== undefined ? "#eab308" : "#3b82f6",
                      height: "100%",
                      borderRadius: "5px",
                      transition: "width 0.4s ease"
                    }} />
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {!isInline && (
          <div style={{ display: "flex", justifyContent: "flex-end" }}>
            <button
              onClick={onClose}
              style={{
                padding: "10px 20px",
                borderRadius: "8px",
                border: "none",
                backgroundColor: "#0f172a",
                color: "#ffffff",
                fontWeight: "600",
                cursor: "pointer"
              }}
            >
              Cerrar Dashboard
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
