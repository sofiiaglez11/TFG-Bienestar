"use client";

import { useState, useEffect } from "react";
import {
  BarChart3,
  BookOpen,
  Clock,
  Moon,
  Smile,
  Zap,
  Calendar,
  Award,
  Printer,
  Layers
} from "lucide-react";

// Importación de los componentes modulares
import AcademicAnalysis from "./Analysis/AcademicAnalysis";
import TimeBreakdownAnalysis from "./Analysis/TimeBreakdownAnalysis";
import WellbeingAnalysis from "./Analysis/WellbeingAnalysis";
import PatternsAnalysis from "./Analysis/PatternsAnalysis";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

export default function StudentDashboard({ isOpen, onClose, isInline = false, isActive = false }) {
  const [data, setData] = useState({
    analytics: [],
    wellbeing: {},
    patterns: {},
    study_plan: {},
    time_breakdown: {}
  });
  const [loading, setLoading] = useState(false);
  const [savingGradeId, setSavingGradeId] = useState(null);
  const [gradeInputs, setGradeInputs] = useState({});
  const [activeSubTab, setActiveSubTab] = useState("academic"); // "academic" | "breakdown" | "wellbeing" | "patterns"
  const [selectedDays, setSelectedDays] = useState(7); // 7, 30, 0=histórico

  useEffect(() => {
    if (isOpen || (isInline && isActive)) {
      fetchAnalytics(selectedDays);
    }
  }, [isOpen, isInline, isActive, selectedDays]);

  const fetchAnalytics = async (days = selectedDays) => {
    setLoading(true);
    const token = localStorage.getItem("token");
    if (!token) return;
    try {
      const res = await fetch(`${BACKEND_URL}/api/dashboard/student-analytics?days=${days}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const resData = await res.json();
        setData({
          analytics: resData.analytics || [],
          wellbeing: resData.wellbeing || {},
          patterns: resData.patterns || {},
          study_plan: resData.study_plan || {},
          time_breakdown: resData.time_breakdown || {}
        });
        const initialGrades = {};
        (resData.analytics || []).forEach((item) => {
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
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({ grade: val })
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

  const analytics = data.analytics || [];
  const wellbeing = data.wellbeing || {};
  const patterns = data.patterns || {};
  const studyPlan = data.study_plan || {};
  const timeBreakdown = data.time_breakdown || {};

  const formatDate = (isoDate) => {
    if (!isoDate) return null;
    try {
      const [year, month, day] = isoDate.split("-");
      const months = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
      return `${parseInt(day)} ${months[parseInt(month) - 1]} ${year}`;
    } catch {
      return isoDate;
    }
  };

  const formatTime = (hours) => {
    const h = Math.floor(hours);
    const m = Math.round((hours - h) * 60);
    if (h === 0 && m === 0) return "0 min";
    if (h === 0) return `${m} min`;
    if (m === 0) return `${h} h`;
    return `${h} h ${m} min`;
  };

  const totalHours = analytics.reduce((acc, curr) => acc + (curr.hours || 0), 0);
  const gradedSubjects = analytics.filter((s) => s.grade !== null && s.grade !== undefined && s.grade !== "");
  const avgGrade = gradedSubjects.length > 0
    ? (gradedSubjects.reduce((acc, curr) => acc + Number(curr.grade), 0) / gradedSubjects.length).toFixed(2)
    : "N/A";

  const concSubjects = analytics.filter((s) => s.avg_concentration !== null && s.avg_concentration !== undefined);
  const avgConc = concSubjects.length > 0
    ? (concSubjects.reduce((acc, curr) => acc + Number(curr.avg_concentration), 0) / concSubjects.length).toFixed(1)
    : "N/A";

  const avgSleep = wellbeing.avg_sleep_hours ? `${wellbeing.avg_sleep_hours} h` : "N/D";

  const periodLabel = selectedDays === 0 ? "Histórico" : selectedDays === 7 ? "7 días" : "30 días";

  const handlePrintReport = () => {
    window.print();
  };

  if (!isOpen && !isInline) return null;

  return (
    <div
      style={
        isInline
          ? { width: "100%", height: "100%", display: "flex", flexDirection: "column", color: "var(--text-primary)" }
          : {
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
          }
      }
    >
      <div
        style={
          isInline
            ? {
              backgroundColor: "var(--bg-surface)",
              border: "1px solid var(--border)",
              borderRadius: "16px",
              padding: "28px",
              width: "100%",
              height: "100%",
              overflowY: "auto",
              boxShadow: "none",
              color: "var(--text-primary)"
            }
            : {
              backgroundColor: "var(--bg-surface)",
              borderRadius: "16px",
              padding: "28px",
              width: "100%",
              maxWidth: "920px",
              maxHeight: "90vh",
              overflowY: "auto",
              boxShadow: "0 20px 30px rgba(0,0,0,0.25)",
              color: "var(--text-primary)",
              border: "1px solid var(--border)"
            }
        }
      >
        {/* Header Superior */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
          <div>
            <h2 style={{ margin: 0, fontSize: "1.4rem", fontWeight: "700", display: "flex", alignItems: "center", gap: "10px" }}>
              <BarChart3 size={24} color="var(--brand)" />
              Dashboard de Rendimiento y Bienestar
            </h2>
            <p style={{ margin: "4px 0 0 0", color: "var(--text-secondary)", fontSize: "14px" }}>
              Análisis completo de asignaturas, tareas, tiempo dedicado y descanso
            </p>
          </div>
          <div style={{ display: "flex", gap: "10px" }}>
            {/* Selector de periodo */}
            <div style={{ display: "flex", gap: "4px", backgroundColor: "var(--bg-input)", borderRadius: "8px", padding: "3px", border: "1px solid var(--border)" }}>
              {[
                { label: "7 días", value: 7 },
                { label: "30 días", value: 30 },
                { label: "Histórico", value: 0 }
              ].map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => setSelectedDays(opt.value)}
                  style={{
                    padding: "5px 10px",
                    borderRadius: "6px",
                    border: "none",
                    fontSize: "12px",
                    fontWeight: "600",
                    cursor: "pointer",
                    transition: "all 0.2s",
                    backgroundColor: selectedDays === opt.value ? "var(--brand)" : "transparent",
                    color: selectedDays === opt.value ? "#fff" : "var(--text-secondary)"
                  }}
                >
                  {opt.label}
                </button>
              ))}
            </div>
            <button
              onClick={handlePrintReport}
              style={{
                padding: "8px 14px",
                borderRadius: "8px",
                border: "1px solid var(--border)",
                backgroundColor: "var(--bg-input)",
                color: "var(--text-primary)",
                cursor: "pointer",
                fontWeight: "500",
                fontSize: "13px",
                display: "flex",
                alignItems: "center",
                gap: "6px"
              }}
            >
              <Printer size={16} /> Exportar PDF
            </button>
            {!isInline && (
              <button
                onClick={onClose}
                style={{ background: "none", border: "none", fontSize: "1.5rem", cursor: "pointer", color: "var(--text-secondary)" }}
              >
                &times;
              </button>
            )}
          </div>
        </div>

        {/* Tarjetas KPI de Resumen General */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "14px", marginBottom: "24px" }}>
          <div style={{ padding: "16px", borderRadius: "12px", backgroundColor: "#eff6ff", border: "1px solid #bfdbfe" }}>
            <div style={{ fontSize: "12px", color: "#1e40af", fontWeight: "600", display: "flex", alignItems: "center", gap: "6px" }}>
              <Clock size={16} /> Total Horas
            </div>
            <div style={{ fontSize: "1.6rem", fontWeight: "700", color: "#1d4ed8", marginTop: "4px" }}>{formatTime(totalHours)}</div>
          </div>
          <div style={{ padding: "16px", borderRadius: "12px", backgroundColor: "#f0fdf4", border: "1px solid #bbf7d0" }}>
            <div style={{ fontSize: "12px", color: "#166534", fontWeight: "600", display: "flex", alignItems: "center", gap: "6px" }}>
              <Award size={16} /> Nota Media
            </div>
            <div style={{ fontSize: "1.6rem", fontWeight: "700", color: "#15803d", marginTop: "4px" }}>{avgGrade} / 10</div>
          </div>
          <div style={{ padding: "16px", borderRadius: "12px", backgroundColor: "#fdf4ff", border: "1px solid #f5d0fe" }}>
            <div style={{ fontSize: "12px", color: "#86198f", fontWeight: "600", display: "flex", alignItems: "center", gap: "6px" }}>
              <Moon size={16} /> Sueño Promedio
            </div>
            <div style={{ fontSize: "1.6rem", fontWeight: "700", color: "#a21caf", marginTop: "4px" }}>{avgSleep}</div>
          </div>
          <div style={{ padding: "16px", borderRadius: "12px", backgroundColor: "#fff7ed", border: "1px solid #ffedd5" }}>
            <div style={{ fontSize: "12px", color: "#9a3412", fontWeight: "600", display: "flex", alignItems: "center", gap: "6px" }}>
              <Zap size={16} /> Concentración
            </div>
            <div style={{ fontSize: "1.6rem", fontWeight: "700", color: "#c2410c", marginTop: "4px" }}>
              {avgConc} {avgConc !== "N/A" ? "/ 5" : ""}
            </div>
          </div>
        </div>

        {/* Navegación por Pestañas principales */}
        <div
          style={{
            display: "flex",
            gap: "8px",
            borderBottom: "1px solid var(--border)",
            paddingBottom: "8px",
            marginBottom: "20px",
            overflowX: "auto"
          }}
        >
          <button
            onClick={() => setActiveSubTab("academic")}
            style={{
              padding: "8px 16px",
              borderRadius: "8px",
              border: "none",
              backgroundColor: activeSubTab === "academic" ? "var(--brand)" : "transparent",
              color: activeSubTab === "academic" ? "#ffffff" : "var(--text-secondary)",
              fontWeight: "600",
              fontSize: "14px",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "8px",
              transition: "all 0.2s"
            }}
          >
            <BookOpen size={16} /> Académico y Asignaturas
          </button>
          <button
            onClick={() => setActiveSubTab("breakdown")}
            style={{
              padding: "8px 16px",
              borderRadius: "8px",
              border: "none",
              backgroundColor: activeSubTab === "breakdown" ? "var(--brand)" : "transparent",
              color: activeSubTab === "breakdown" ? "#ffffff" : "var(--text-secondary)",
              fontWeight: "600",
              fontSize: "14px",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "8px",
              transition: "all 0.2s"
            }}
          >
            <Layers size={16} /> Desglose de Tiempo
          </button>
          <button
            onClick={() => setActiveSubTab("wellbeing")}
            style={{
              padding: "8px 16px",
              borderRadius: "8px",
              border: "none",
              backgroundColor: activeSubTab === "wellbeing" ? "var(--brand)" : "transparent",
              color: activeSubTab === "wellbeing" ? "#ffffff" : "var(--text-secondary)",
              fontWeight: "600",
              fontSize: "14px",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "8px",
              transition: "all 0.2s"
            }}
          >
            <Smile size={16} /> Bienestar y Descanso
          </button>
          <button
            onClick={() => setActiveSubTab("patterns")}
            style={{
              padding: "8px 16px",
              borderRadius: "8px",
              border: "none",
              backgroundColor: activeSubTab === "patterns" ? "var(--brand)" : "transparent",
              color: activeSubTab === "patterns" ? "#ffffff" : "var(--text-secondary)",
              fontWeight: "600",
              fontSize: "14px",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "8px",
              transition: "all 0.2s"
            }}
          >
            <Calendar size={16} /> Hábitos y Patrones
          </button>
        </div>

        {/* Renderizado Condicional de las Pestañas */}
        {loading ? (
          <p style={{ color: "var(--text-secondary)", fontStyle: "italic", textAlign: "center", padding: "40px 0" }}>
            Cargando analíticas...
          </p>
        ) : (
          <>
            {activeSubTab === "academic" && (
              <AcademicAnalysis
                analytics={analytics}
                studyPlan={studyPlan}
                gradeInputs={gradeInputs}
                handleGradeChange={handleGradeChange}
                saveGrade={saveGrade}
                savingGradeId={savingGradeId}
                formatTime={formatTime}
              />
            )}
            {activeSubTab === "breakdown" && (
              <TimeBreakdownAnalysis
                timeBreakdown={timeBreakdown}
                formatTime={formatTime}
              />
            )}
            {activeSubTab === "wellbeing" && (
              <WellbeingAnalysis
                wellbeing={wellbeing}
                periodLabel={periodLabel}
                formatDate={formatDate}
              />
            )}
            {activeSubTab === "patterns" && (
              <PatternsAnalysis
                patterns={patterns}
                periodLabel={periodLabel}
                formatDate={formatDate}
                formatTime={formatTime}
              />
            )}
          </>
        )}

        {!isInline && (
          <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "24px" }}>
            <button
              onClick={onClose}
              style={{
                padding: "10px 20px",
                borderRadius: "8px",
                border: "none",
                backgroundColor: "var(--brand)",
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