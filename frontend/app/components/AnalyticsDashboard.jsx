"use client";

import { useState, useEffect } from "react";
import {
  BarChart3, BookOpen, Clock, Moon, Smile, Zap, Calendar, Award, Layers, Share2
} from "lucide-react";

// Importación de componentes modulares
import AcademicAnalysis from "./Analysis/AcademicAnalysis";
import TimeBreakdownAnalysis from "./Analysis/TimeBreakdownAnalysis";
import WellbeingAnalysis from "./Analysis/WellbeingAnalysis";
import PatternsAnalysis from "./Analysis/PatternsAnalysis";
import styles from "./AnalyticsDashboard.module.css";

const RAW_BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
const BACKEND_URL = RAW_BACKEND_URL.replace(/\/+$/, "");

export default function AnalyticsDashboard({ isOpen, onClose, isInline = false, isActive = true, clockifyConnected, followKey = 0, onOpenShareSettings }) {
  const [data, setData] = useState({
    analytics: [],
    wellbeing: {},
    patterns: {},
    study_plan: {},
    time_breakdown: {}
  });
  const [loading, setLoading] = useState(false);
  const [gradeInputs, setGradeInputs] = useState({});
  const [activeSubTab, setActiveSubTab] = useState("academic");
  const [selectedDays, setSelectedDays] = useState(7);

  // Selector de usuario (alimentado desde la API de seguidos)
  const [selectedUserId, setSelectedUserId] = useState("me");
  const [followedUsers, setFollowedUsers] = useState([]);

  const shouldRender = isOpen || isInline;

  useEffect(() => {
    if (shouldRender) {
      fetchAnalytics(selectedDays, selectedUserId);
      loadFollowedUsers();
    }
  }, [isOpen, isInline, isActive]);

  // Recarga la lista de seguidos cuando cambia followKey (nuevo seguido desde ajustes)
  useEffect(() => {
    if (shouldRender && followKey > 0) {
      loadFollowedUsers();
    }
  }, [followKey]);

  const loadFollowedUsers = async () => {
    const token = localStorage.getItem("token");
    if (!token) return;
    try {
      const res = await fetch(`${BACKEND_URL}/api/share/followed`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const followedData = await res.json();
        setFollowedUsers(followedData.followed || []);
      }
    } catch (err) {
      console.error("Error al cargar usuarios seguidos:", err);
    }
  };

  const fetchAnalytics = async (daysParam = selectedDays, userParam = selectedUserId) => {
    setLoading(true);
    const token = localStorage.getItem("token");
    if (!token) {
      setLoading(false);
      return;
    }

    let targetUser = typeof userParam === "string" ? userParam : "me";
    const isMe = !targetUser || targetUser === "me" || targetUser === "undefined" || targetUser === "null";
    const cleanDays = (typeof daysParam === "number" || typeof daysParam === "string") ? daysParam : 7;

    const endpoint = isMe
      ? `${BACKEND_URL}/api/dashboard/student-analytics?days=${cleanDays}`
      : `${BACKEND_URL}/api/share/${encodeURIComponent(targetUser)}/analytics?days=${cleanDays}`;

    try {
      const res = await fetch(endpoint, {
        method: "GET",
        headers: {
          "Authorization": `Bearer ${token}`,
          "Content-Type": "application/json"
        }
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
      console.error("Error de conexión:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectDays = (days) => {
    setSelectedDays(days);
    fetchAnalytics(days, selectedUserId);
  };

  const handleSelectUser = (userId) => {
    setSelectedUserId(userId);
    fetchAnalytics(selectedDays, userId);
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

  const isMe = !selectedUserId || selectedUserId === "me" || selectedUserId === "undefined" || selectedUserId === "null";
  const isClockifyActive = clockifyConnected !== undefined ? clockifyConnected : (typeof window !== "undefined" && localStorage.getItem("clockifyConnected") === "true");

  if (!isOpen && !isInline) return null;

  const TABS = [
    { id: "academic",  label: "Asignaturas",          Icon: BookOpen },
    { id: "breakdown", label: "Desglose de Tiempo",   Icon: Layers },
    { id: "wellbeing", label: "Bienestar y Descanso", Icon: Smile },
    { id: "patterns",  label: "Hábitos y Patrones",   Icon: Calendar },
  ];

  return (
    <div className={isInline ? styles.wrapperInline : styles.backdrop}>
      <div className={isInline ? styles.panelInline : styles.panelModal}>
        {/* Header Superior */}
        <div className={styles.header}>
          <div>
            <h2 className={styles.headerTitle}>
              Estadísticas de estudio y bienestar
            </h2>
            <p className={styles.headerSubtitle}>
              Análisis completo de asignaturas, tareas, tiempo dedicado y descanso
            </p>
          </div>
          <div className={styles.headerActions}>
            {/* Botón Compartir: abre Ajustes en la pestaña de privacidad/compartir */}
            {onOpenShareSettings && (
              <button
                type="button"
                onClick={onOpenShareSettings}
                title="Configurar cómo compartes tus estadísticas"
                className={styles.btnSecondary}
              >
                <Share2 size={14} /> Compartir
              </button>
            )}

            {/* Selector de usuario */}
            <select
              value={selectedUserId}
              onChange={(e) => handleSelectUser(e.target.value)}
              className={styles.selectUser}
            >
              <option value="me">Mis estadísticas</option>
              {followedUsers.map((u, idx) => {
                const uId = u.followed_user_id || u.target_user_id || u.user_id || u.id || u._id;
                const name = u.name || u.user_name || u.nombre;
                const email = u.email || u.user_email;

                let label = `Usuario ${idx + 1}`;
                if (name && email && name !== email) {
                  label = `${name} (${email})`;
                } else if (email) {
                  label = email;
                } else if (name) {
                  label = name;
                }

                if (!uId) return null;
                return (
                  <option key={uId} value={uId}>
                    {label}
                  </option>
                );
              })}
            </select>

            {/* Selector de periodo */}
            <div className={styles.periodGroup}>
              {[
                { label: "7 días", value: 7 },
                { label: "30 días", value: 30 },
                { label: "Histórico", value: 0 }
              ].map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => handleSelectDays(opt.value)}
                  className={`${styles.periodBtn} ${selectedDays === opt.value ? styles.periodBtnActive : ""}`}
                >
                  {opt.label}
                </button>
              ))}
            </div>

            {!isInline && (
              <button onClick={onClose} className={styles.btnClose}>
                &times;
              </button>
            )}
          </div>
        </div>

        {isMe && !isClockifyActive ? (
          <div className={styles.emptyState}>
            <div className={styles.emptyStateIcon}>
              <BarChart3 size={40} strokeWidth={1.5} />
            </div>
            <h3 className={styles.emptyStateTitle}>
              Estadísticas personales no disponibles sin Clockify
            </h3>
            <p className={styles.emptyStateText}>
              No has vinculado tu cuenta de Clockify para generar tus estadísticas de estudio.
              <br /><br />
            </p>
          </div>
        ) : (
          <>
            {/* Tarjetas KPI de Resumen General */}
            <div className={styles.kpiStrip}>
              <div className={styles.kpiItem}>
                <Clock size={16} style={{ color: "#1d4ed8" }} />
                <span className={styles.kpiLabel}>Total:</span>
                <strong className={styles.kpiValue}>{formatTime(totalHours)}</strong>
              </div>

              <div className={styles.kpiDivider} />

              <div className={styles.kpiItem}>
                <Award size={16} style={{ color: "#15803d" }} />
                <span className={styles.kpiLabel}>Nota Media:</span>
                <strong className={styles.kpiValue}>{avgGrade} / 10</strong>
              </div>

              <div className={styles.kpiDivider} />

              <div className={styles.kpiItem}>
                <Moon size={16} style={{ color: "#a21caf" }} />
                <span className={styles.kpiLabel}>Sueño Promedio:</span>
                <strong className={styles.kpiValue}>{avgSleep}</strong>
              </div>

              <div className={styles.kpiDivider} />

              <div className={styles.kpiItem}>
                <Zap size={16} style={{ color: "#c2410c" }} />
                <span className={styles.kpiLabel}>Concentración:</span>
                <strong className={styles.kpiValue}>{avgConc} {avgConc !== "N/A" ? "/ 5" : ""}</strong>
              </div>
            </div>

            {/* Navegación por Pestañas principales */}
            <div className={styles.tabs}>
              {TABS.map(({ id, label, Icon }) => (
                <button
                  key={id}
                  onClick={() => setActiveSubTab(id)}
                  className={`${styles.tab} ${activeSubTab === id ? styles.tabActive : ""}`}
                >
                  <Icon size={16} /> {label}
                </button>
              ))}
            </div>

            {/* Renderizado Condicional de las Pestañas */}
            {loading ? (
              <p className={styles.loading}>
                Cargando estadísticas...
              </p>
            ) : (
              <>
                {activeSubTab === "academic" && (
                  <AcademicAnalysis
                    analytics={analytics}
                    studyPlan={studyPlan}
                    gradeInputs={gradeInputs}
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
          </>
        )}

        {!isInline && (
          <div className={styles.footer}>
            <button onClick={onClose} className={styles.btnPrimary}>
              Cerrar Dashboard
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
