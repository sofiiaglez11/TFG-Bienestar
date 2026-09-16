"use client";

import { useState, useEffect } from "react";
import {
  BarChart3,
  BookOpen,
  Clock,
  CheckCircle2,
  AlertCircle,
  TrendingUp,
  TrendingDown,
  Tag,
  Moon,
  Smile,
  Zap,
  FileText,
  Calendar,
  AlertTriangle,
  Award,
  ListChecks,
  Printer,
  ChevronRight,
  Sparkles,
  Layers,
  CheckSquare,
  Clock3
} from "lucide-react";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

export default function StudentDashboard({ isOpen, onClose, isInline = false }) {
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
  const [subjectFilter, setSubjectFilter] = useState("All");
  const [tagFilter, setTagFilter] = useState("All");

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

  const analytics = data.analytics || [];
  const wellbeing = data.wellbeing || {};
  const patterns = data.patterns || {};
  const studyPlan = data.study_plan || {};
  const timeBreakdown = data.time_breakdown || {};

  // Formatea "YYYY-MM-DD" -> "14 sep 2026"
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

  const handlePrintReport = () => {
    window.print();
  };

  if (!isOpen && !isInline) return null;

  const WEEKDAYS_ORDER = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"];
  const reportsByDay = wellbeing.reports_by_weekday || {};
  const hoursByDay = patterns.hours_by_weekday || {};

  const unifiedTasks = timeBreakdown.unified_tasks || [];

  const availableSubjects = ["All", ...new Set(unifiedTasks.map(t => t.subject).filter(Boolean))];
  const availableTags = ["All", ...new Set(unifiedTasks.flatMap(t => t.tags || []).filter(Boolean))];

  const filteredTasks = unifiedTasks.filter(t => {
    const matchSubject = subjectFilter === "All" || t.subject === subjectFilter;
    const matchTag = tagFilter === "All" || (t.tags && t.tags.includes(tagFilter));
    return matchSubject && matchTag;
  });

  const filteredTotalHoursRaw = filteredTasks.reduce((acc, t) => acc + t.hours + (t.minutes / 60), 0);
  const filteredTotalHours = Math.floor(filteredTotalHoursRaw);
  const filteredTotalMins = Math.round((filteredTotalHoursRaw - filteredTotalHours) * 60);

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
        backgroundColor: "var(--bg-surface)",
        border: "1px solid var(--border)",
        borderRadius: "16px",
        padding: "28px",
        width: "100%",
        height: "100%",
        overflowY: "auto",
        boxShadow: "none",
        color: "var(--text-primary)"
      } : {
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
      }}>
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
            <div style={{ fontSize: "1.6rem", fontWeight: "700", color: "#1d4ed8", marginTop: "4px" }}>{totalHours.toFixed(1)} h</div>
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
            <div style={{ fontSize: "1.6rem", fontWeight: "700", color: "#c2410c", marginTop: "4px" }}>{avgConc} {avgConc !== "N/A" ? "/ 5" : ""}</div>
          </div>
        </div>

        {/* Navegación por Pestañas principales */}
        <div style={{
          display: "flex",
          gap: "8px",
          borderBottom: "1px solid var(--border)",
          paddingBottom: "8px",
          marginBottom: "20px",
          overflowX: "auto"
        }}>
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

        {loading ? (
          <p style={{ color: "var(--text-secondary)", fontStyle: "italic", textAlign: "center", padding: "40px 0" }}>
            Cargando analíticas...
          </p>
        ) : (
          <>
            {/* PESTAÑA 1: ACADÉMICO Y ASIGNATURAS */}
            {activeSubTab === "academic" && (
              <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
                {/* Plan de Estudio Activo */}
                {studyPlan.has_active_plan && (
                  <div style={{
                    padding: "18px",
                    borderRadius: "12px",
                    border: "1px solid var(--border)",
                    background: "linear-gradient(135deg, rgba(99, 102, 241, 0.08), rgba(139, 92, 246, 0.05))",
                    display: "flex",
                    flexDirection: "column",
                    gap: "12px"
                  }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <div>
                        <span style={{ fontSize: "11px", fontWeight: "700", color: "var(--brand)", textTransform: "uppercase", letterSpacing: "0.5px" }}>
                          Plan de Estudio Activo
                        </span>
                        <h3 style={{ margin: "2px 0 0 0", fontSize: "16px", fontWeight: "700" }}>{studyPlan.plan_title}</h3>
                      </div>
                      <div style={{ textAlign: "right" }}>
                        <span style={{ fontSize: "18px", fontWeight: "700", color: "var(--brand)" }}>
                          {studyPlan.overall_progress_pct}%
                        </span>
                        <div style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
                          {studyPlan.total_actual_hours}h / {studyPlan.total_planned_hours}h planificadas
                        </div>
                      </div>
                    </div>
                    <div style={{ width: "100%", backgroundColor: "var(--border)", height: "8px", borderRadius: "4px", overflow: "hidden" }}>
                      <div style={{
                        width: `${Math.min(100, studyPlan.overall_progress_pct || 0)}%`,
                        backgroundColor: "var(--brand)",
                        height: "100%",
                        borderRadius: "4px",
                        transition: "width 0.4s ease"
                      }} />
                    </div>
                  </div>
                )}

                {/* Lista detallada de Asignaturas */}
                <div>
                  <h3 style={{ fontSize: "1.05rem", fontWeight: "600", marginBottom: "14px", display: "flex", alignItems: "center", gap: "8px" }}>
                    <BookOpen size={18} /> Rendimiento y Tareas por Asignatura
                  </h3>

                  {analytics.length === 0 ? (
                    <p style={{ color: "var(--text-secondary)", backgroundColor: "var(--bg-input)", padding: "16px", borderRadius: "8px" }}>
                      Aún no tienes asignaturas registradas. Puedes crearlas conversando con el tutor.
                    </p>
                  ) : (
                    <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
                      {analytics.map((item) => {
                        const wComp = item.weekly_comparison || {};
                        const lastW = item.last_week_tasks || {};
                        const isUp = wComp.change_pct > 0;
                        const isDown = wComp.change_pct < 0;

                        return (
                          <div key={item.id} style={{
                            padding: "20px",
                            borderRadius: "14px",
                            border: "1px solid var(--border)",
                            backgroundColor: "var(--bg-input)",
                            display: "flex",
                            flexDirection: "column",
                            gap: "14px"
                          }}>
                            {/* Cabecera de la asignatura */}
                            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "12px" }}>
                              <div>
                                <h4 style={{ margin: 0, fontSize: "1.1rem", fontWeight: "700" }}>{item.name}</h4>
                                <div style={{ display: "flex", alignItems: "center", gap: "14px", marginTop: "6px", fontSize: "13px", color: "var(--text-secondary)", flexWrap: "wrap" }}>
                                  <span style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                                    <Clock size={14} /> {item.hours} hrs totales
                                  </span>

                                  {/* Comparativa semanal */}
                                  <span style={{
                                    display: "inline-flex",
                                    alignItems: "center",
                                    gap: "4px",
                                    fontWeight: "600",
                                    color: isUp ? "#16a34a" : isDown ? "#dc2626" : "var(--text-secondary)",
                                    fontSize: "12px",
                                    padding: "2px 8px",
                                    borderRadius: "12px",
                                    backgroundColor: isUp ? "#f0fdf4" : isDown ? "#fef2f2" : "transparent",
                                    border: isUp ? "1px solid #bbf7d0" : isDown ? "1px solid #fecaca" : "none"
                                  }}>
                                    {isUp ? <TrendingUp size={14} /> : isDown ? <TrendingDown size={14} /> : null}
                                    {wComp.current_week_hours || 0}h esta semana ({wComp.change_pct > 0 ? `+${wComp.change_pct}%` : `${wComp.change_pct}%`} vs sem. anterior)
                                  </span>
                                </div>
                              </div>

                              {/* Nota asignatura */}
                              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
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
                                    border: "1px solid var(--border)",
                                    backgroundColor: "var(--bg-surface)",
                                    color: "var(--text-primary)",
                                    textAlign: "center",
                                    fontSize: "14px"
                                  }}
                                />
                                <button
                                  onClick={() => saveGrade(item.id)}
                                  disabled={savingGradeId === item.id}
                                  style={{
                                    padding: "4px 12px",
                                    borderRadius: "6px",
                                    border: "none",
                                    backgroundColor: "var(--brand)",
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

                            {/* Estadísticas de Tareas por Asignatura */}
                            <div style={{
                              display: "grid",
                              gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
                              gap: "10px",
                              padding: "12px",
                              borderRadius: "10px",
                              backgroundColor: "var(--bg-surface)",
                              border: "1px solid var(--border)"
                            }}>
                              <div>
                                <span style={{ fontSize: "11px", color: "var(--text-secondary)", fontWeight: "600", display: "flex", alignItems: "center", gap: "4px" }}>
                                  <Calendar size={12} /> Última Semana (7 días)
                                </span>
                                <div style={{ fontSize: "13px", fontWeight: "600", marginTop: "2px" }}>
                                  <span style={{ color: "#16a34a" }}>{lastW.completed || 0} completadas</span>
                                  {" / "}
                                  <span style={{ color: "var(--text-secondary)" }}>{lastW.pending || 0} pendientes</span>
                                </div>
                              </div>

                              <div>
                                <span style={{ fontSize: "11px", color: "var(--text-secondary)", fontWeight: "600", display: "flex", alignItems: "center", gap: "4px" }}>
                                  <CheckSquare size={12} /> Total Creadas (Histórico)
                                </span>
                                <div style={{ fontSize: "13px", fontWeight: "600", marginTop: "2px" }}>
                                  {item.tasks_completed} completadas de {item.total_tasks_created || (item.tasks_completed + item.tasks_pending)}
                                </div>
                              </div>

                              <div>
                                <span style={{ fontSize: "11px", color: "var(--text-secondary)", fontWeight: "600", display: "flex", alignItems: "center", gap: "4px" }}>
                                  <Zap size={12} /> Concentración Media
                                </span>
                                <div style={{ fontSize: "13px", fontWeight: "600", marginTop: "2px", color: "#c2410c" }}>
                                  {item.avg_concentration !== null ? `${item.avg_concentration} / 5` : "Sin informes"}
                                </div>
                              </div>
                            </div>

                            {/* Alertas de Tareas Pospuestas / Fuera de Plazo o Desatendidas */}
                            {(item.overdue_tasks_count > 0 || item.neglected_tasks_count > 0) && (
                              <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                                {item.overdue_tasks_count > 0 && (
                                  <div style={{
                                    fontSize: "12px",
                                    color: "#dc2626",
                                    backgroundColor: "#fef2f2",
                                    padding: "8px 12px",
                                    borderRadius: "8px",
                                    border: "1px solid #fecaca",
                                    display: "flex",
                                    alignItems: "center",
                                    gap: "6px"
                                  }}>
                                    <AlertTriangle size={14} />
                                    <span>
                                      <strong>{item.overdue_tasks_count} tareas entregadas fuera de plazo o vencidas:</strong> {item.overdue_tasks.join(", ")}
                                    </span>
                                  </div>
                                )}

                                {item.neglected_tasks_count > 0 && (
                                  <div style={{
                                    fontSize: "12px",
                                    color: "#d97706",
                                    backgroundColor: "#fffbe6",
                                    padding: "8px 12px",
                                    borderRadius: "8px",
                                    border: "1px solid #ffe58f",
                                    display: "flex",
                                    alignItems: "center",
                                    gap: "6px"
                                  }}>
                                    <Clock3 size={14} />
                                    <span>
                                      <strong>{item.neglected_tasks_count} tareas desatendidas (&lt; 15 min tiempo registrado):</strong> {item.neglected_tasks.join(", ")}
                                    </span>
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* PESTAÑA 2: DESGLOSE DE TIEMPO */}
            {activeSubTab === "breakdown" && (
              <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
                {/* Filtros */}
                <div style={{ display: "flex", gap: "12px", alignItems: "center", flexWrap: "wrap", backgroundColor: "var(--bg-input)", padding: "12px", borderRadius: "10px", border: "1px solid var(--border)" }}>
                  <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                    <label style={{ fontSize: "12px", fontWeight: "600", color: "var(--text-secondary)" }}>Asignatura</label>
                    <select
                      value={subjectFilter}
                      onChange={(e) => setSubjectFilter(e.target.value)}
                      style={{ padding: "6px 12px", borderRadius: "6px", border: "1px solid var(--border)", backgroundColor: "var(--bg-surface)", color: "var(--text-primary)", fontSize: "13px" }}
                    >
                      {availableSubjects.map(s => <option key={s} value={s}>{s === "All" ? "Todas" : s}</option>)}
                    </select>
                  </div>

                  <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                    <label style={{ fontSize: "12px", fontWeight: "600", color: "var(--text-secondary)" }}>Etiqueta</label>
                    <select
                      value={tagFilter}
                      onChange={(e) => setTagFilter(e.target.value)}
                      style={{ padding: "6px 12px", borderRadius: "6px", border: "1px solid var(--border)", backgroundColor: "var(--bg-surface)", color: "var(--text-primary)", fontSize: "13px" }}
                    >
                      {availableTags.map(t => <option key={t} value={t}>{t === "All" ? "Todas" : t}</option>)}
                    </select>
                  </div>

                  <div style={{ marginLeft: "auto", display: "flex", flexDirection: "column", alignItems: "flex-end" }}>
                    <span style={{ fontSize: "12px", color: "var(--text-secondary)", fontWeight: "600" }}>Tiempo Total Filtrado</span>
                    <span style={{ fontSize: "18px", fontWeight: "700", color: "var(--brand)" }}>
                      {filteredTotalHours} h {filteredTotalMins} min
                    </span>
                  </div>
                </div>

                {/* Lista Unificada de Tareas */}
                <div>
                  <h4 style={{ margin: "0 0 12px 0", fontSize: "15px", fontWeight: "600", display: "flex", alignItems: "center", gap: "8px" }}>
                    <ListChecks size={18} /> Sesiones de Trabajo y Tareas
                  </h4>
                  {filteredTasks.length === 0 ? (
                    <p style={{ color: "var(--text-secondary)", fontSize: "14px" }}>No hay registros de tareas con los filtros seleccionados.</p>
                  ) : (
                    <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                      {filteredTasks.map((item, idx) => (
                        <div key={idx} style={{
                          padding: "12px 16px",
                          borderRadius: "10px",
                          backgroundColor: "var(--bg-input)",
                          border: "1px solid var(--border)",
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                          gap: "12px"
                        }}>
                          <div style={{ display: "flex", alignItems: "flex-start", gap: "8px" }}>
                            <span style={{ fontSize: "13px", fontWeight: "700", color: "var(--brand)", marginTop: "1px" }}>
                              {item.subject}
                            </span>
                            <span style={{ fontSize: "14px", color: "var(--text-secondary)" }}>|</span>

                            <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                              <span style={{ fontSize: "14px", fontWeight: "600" }}>{item.title}</span>
                              {item.tags && item.tags.length > 0 && (
                                <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
                                  {item.tags.map(tag => (
                                    <span key={tag} style={{
                                      fontSize: "11px",
                                      padding: "2px 8px",
                                      borderRadius: "12px",
                                      backgroundColor: "#f3e8ff",
                                      color: "#7e22ce",
                                      border: "1px solid #e9d5ff",
                                      fontWeight: "600",
                                      display: "flex",
                                      alignItems: "center",
                                      gap: "4px"
                                    }}>
                                      <Tag size={10} /> {tag}
                                    </span>
                                  ))}
                                </div>
                              )}
                            </div>
                          </div>
                          <div style={{ whiteSpace: "nowrap" }}>
                            <span style={{ fontSize: "14px", color: "var(--brand)", fontWeight: "700" }}>
                              {item.hours} h {item.minutes > 0 ? `(${item.minutes} min)` : ""}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* PESTAÑA 3: BIENESTAR Y DESCANSO */}
            {activeSubTab === "wellbeing" && (
              <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
                {wellbeing.worst_day && (
                  <div style={{
                    padding: "14px 16px",
                    borderRadius: "10px",
                    backgroundColor: "#fef2f2",
                    border: "1px solid #fecaca",
                    color: "#991b1b",
                    fontSize: "14px",
                    display: "flex",
                    alignItems: "center",
                    gap: "10px"
                  }}>
                    <AlertTriangle size={20} />
                    <div>
                      <strong>Día crítico detectado:</strong> El <strong>{wellbeing.worst_day}</strong> registraste el menor nivel de estado de ánimo. Recuerda programar pausas de recuperación.
                    </div>
                  </div>
                )}

                <div>
                  <h3 style={{ fontSize: "1.05rem", fontWeight: "600", marginBottom: "12px", display: "flex", alignItems: "center", gap: "8px" }}>
                    <Moon size={18} /> Registro Semanal de Bienestar
                  </h3>

                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(110px, 1fr))", gap: "10px" }}>
                    {WEEKDAYS_ORDER.map((day) => {
                      const dayData = reportsByDay[day];
                      const sleepVal = dayData?.sleep;
                      const moodVal = dayData?.mood;
                      const energyVal = dayData?.energy;

                      return (
                        <div key={day} style={{
                          padding: "12px",
                          borderRadius: "10px",
                          border: "1px solid var(--border)",
                          backgroundColor: "var(--bg-input)",
                          textAlign: "center",
                          display: "flex",
                          flexDirection: "column",
                          gap: "8px"
                        }}>
                          <span style={{ fontWeight: "700", fontSize: "13px", color: "var(--text-primary)" }}>{day}</span>

                          <div style={{ display: "flex", flexDirection: "column", gap: "6px", fontSize: "12px" }}>
                            <div style={{ color: "#2563eb", fontWeight: "500", display: "flex", alignItems: "center", justifyContent: "center", gap: "4px" }}>
                              <Moon size={12} /> {sleepVal !== null && sleepVal !== undefined ? `${sleepVal}h` : "-"}
                            </div>
                            <div style={{ color: "#d97706", fontWeight: "500", display: "flex", alignItems: "center", justifyContent: "center", gap: "4px" }}>
                              <Smile size={12} /> {moodVal !== null && moodVal !== undefined ? `${moodVal}/5` : "-"}
                            </div>
                            <div style={{ color: "#16a34a", fontWeight: "500", display: "flex", alignItems: "center", justifyContent: "center", gap: "4px" }}>
                              <Zap size={12} /> {energyVal !== null && energyVal !== undefined ? `${energyVal}/5` : "-"}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                <div style={{
                  padding: "16px",
                  borderRadius: "10px",
                  border: "1px solid var(--border)",
                  backgroundColor: "var(--bg-input)",
                  fontSize: "13px",
                  color: "var(--text-secondary)",
                  lineHeight: "1.5"
                }}>
                  <strong>Registro de Bienestar:</strong> Para guardar tus horas de descanso diarias o tu estado de ánimo, simplemente coméntaselo al tutor de bienestar en el chat (ej: <em>"Hoy he dormido 7 horas y me siento descansado"</em>).
                </div>
              </div>
            )}

            {/* PESTAÑA 4: HÁBITOS Y PATRONES */}
            {activeSubTab === "patterns" && (
              <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "14px" }}>
                  <div style={{ padding: "16px", borderRadius: "12px", backgroundColor: "#f0fdf4", border: "1px solid #bbf7d0" }}>
                    <span style={{ fontSize: "12px", color: "#166534", fontWeight: "600", display: "flex", alignItems: "center", gap: "6px" }}>
                      <TrendingUp size={16} /> Día Más Productivo
                    </span>
                    <div style={{ fontSize: "1.3rem", fontWeight: "700", color: "#15803d", marginTop: "4px" }}>
                      {patterns.most_productive_weekday || "Sin datos suficientes"}
                    </div>
                    {formatDate(patterns.most_productive_date) && (
                      <div style={{ fontSize: "12px", color: "#166534", marginTop: "2px", opacity: 0.8 }}>
                        {formatDate(patterns.most_productive_date)}
                      </div>
                    )}
                  </div>
                  <div style={{ padding: "16px", borderRadius: "12px", backgroundColor: "#fff7ed", border: "1px solid #ffedd5" }}>
                    <span style={{ fontSize: "12px", color: "#9a3412", fontWeight: "600", display: "flex", alignItems: "center", gap: "6px" }}>
                      <TrendingDown size={16} /> Día Menos Productivo
                    </span>
                    <div style={{ fontSize: "1.3rem", fontWeight: "700", color: "#c2410c", marginTop: "4px" }}>
                      {patterns.least_productive_weekday || "Sin datos suficientes"}
                    </div>
                    {formatDate(patterns.least_productive_date) && (
                      <div style={{ fontSize: "12px", color: "#9a3412", marginTop: "2px", opacity: 0.8 }}>
                        {formatDate(patterns.least_productive_date)}
                      </div>
                    )}
                  </div>
                </div>

                {/* Sesiones Nocturnas */}
                <div>
                  <h3 style={{ fontSize: "1.05rem", fontWeight: "600", marginBottom: "12px", display: "flex", alignItems: "center", gap: "8px" }}>
                    <Clock size={18} /> Higiene del Sueño y Horarios
                  </h3>
                  {patterns.late_night_sessions && patterns.late_night_sessions.length > 0 ? (
                    <div style={{
                      padding: "16px",
                      borderRadius: "12px",
                      backgroundColor: "#fef2f2",
                      border: "1px solid #fecaca",
                      color: "#991b1b",
                      fontSize: "14px"
                    }}>
                      <div style={{ fontWeight: "700", marginBottom: "6px", display: "flex", alignItems: "center", gap: "6px" }}>
                        <Moon size={16} /> Sesiones nocturnas detectadas ({patterns.late_night_sessions.length})
                      </div>
                      <p style={{ margin: "0 0 8px 0", fontSize: "13px" }}>
                        Se registraron sesiones de estudio de madrugada. El estudio tardío continuado puede afectar negativamente a la retención de memoria y la salud.
                      </p>
                      <ul style={{ margin: 0, paddingLeft: "20px", fontSize: "12px" }}>
                        {patterns.late_night_sessions.map((sess, idx) => (
                          <li key={idx}>{sess}</li>
                        ))}
                      </ul>
                    </div>
                  ) : (
                    <div style={{
                      padding: "16px",
                      borderRadius: "12px",
                      backgroundColor: "#f0fdf4",
                      border: "1px solid #bbf7d0",
                      color: "#166534",
                      fontSize: "14px",
                      display: "flex",
                      alignItems: "center",
                      gap: "8px"
                    }}>
                      <CheckCircle2 size={18} /> <strong>Excelente higiene horaria:</strong> No se han detectado sesiones de estudio de madrugada esta semana.
                    </div>
                  )}
                </div>

                {/* Distribución de Horas por Día de la Semana */}
                <div>
                  <h3 style={{ fontSize: "1.05rem", fontWeight: "600", marginBottom: "12px" }}>Distribución Diaria de Horas</h3>
                  <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                    {WEEKDAYS_ORDER.map((day) => {
                      const hrs = hoursByDay[day] || 0;
                      const maxH = Math.max(...Object.values(hoursByDay).map(Number), 5);
                      const pct = Math.min(100, Math.max(0, (hrs / maxH) * 100));

                      return (
                        <div key={day} style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                          <span style={{ width: "80px", fontSize: "13px", fontWeight: "500", color: "var(--text-secondary)" }}>{day}</span>
                          <div style={{ flex: 1, backgroundColor: "var(--border)", height: "10px", borderRadius: "5px", overflow: "hidden" }}>
                            <div style={{
                              width: `${pct}%`,
                              backgroundColor: "var(--brand)",
                              height: "100%",
                              borderRadius: "5px",
                              transition: "width 0.4s ease"
                            }} />
                          </div>
                          <span style={{ width: "50px", fontSize: "13px", fontWeight: "600", textAlign: "right" }}>{hrs} h</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
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
