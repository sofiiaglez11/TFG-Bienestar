"use client";

import {
  BookOpen,
  TrendingUp,
  TrendingDown,
  Clock,
  CheckSquare,
  Zap,
  AlertTriangle,
  Clock3
} from "lucide-react";

export default function AcademicAnalysis({
  analytics = [],
  studyPlan = {},
  gradeInputs = {},
  handleGradeChange,
  saveGrade,
  savingGradeId,
  formatTime
}) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
      {/* Plan de Estudio Activo */}
      {studyPlan.has_active_plan && (
        <div
          style={{
            padding: "16px 20px",
            borderRadius: "12px",
            border: "1px solid var(--border)",
            backgroundColor: "var(--bg-surface)",
            display: "flex",
            flexDirection: "column",
            gap: "10px"
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <span
                style={{
                  fontSize: "11px",
                  fontWeight: "700",
                  color: "var(--brand)",
                  textTransform: "uppercase",
                  letterSpacing: "0.5px"
                }}
              >
                Plan de Estudio Activo
              </span>
              <h3 style={{ margin: "2px 0 0 0", fontSize: "15px", fontWeight: "700", color: "var(--text-primary)" }}>
                {studyPlan.plan_title}
              </h3>
            </div>
            <div style={{ textAlign: "right" }}>
              <span style={{ fontSize: "18px", fontWeight: "800", color: "var(--brand)" }}>
                {studyPlan.overall_progress_pct}%
              </span>
              <div style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
                {formatTime(studyPlan.total_actual_hours || 0)} / {formatTime(studyPlan.total_planned_hours || 0)}
              </div>
            </div>
          </div>
          <div style={{ width: "100%", backgroundColor: "var(--border)", height: "6px", borderRadius: "3px", overflow: "hidden" }}>
            <div
              style={{
                width: `${Math.min(100, studyPlan.overall_progress_pct || 0)}%`,
                backgroundColor: "var(--brand)",
                height: "100%",
                borderRadius: "3px",
                transition: "width 0.4s ease"
              }}
            />
          </div>
        </div>
      )}

      {/* Lista de Asignaturas */}
      <div>
        <h3
          style={{
            fontSize: "1.05rem",
            fontWeight: "600",
            marginBottom: "14px",
            display: "flex",
            alignItems: "center",
            gap: "8px",
            color: "var(--text-primary)"
          }}
        >
          <BookOpen size={18} style={{ color: "var(--brand)" }} /> Mis Asignaturas
        </h3>

        {analytics.length === 0 ? (
          <p
            style={{
              color: "var(--text-secondary)",
              backgroundColor: "var(--bg-input)",
              padding: "16px",
              borderRadius: "8px",
              margin: 0,
              border: "1px solid var(--border)"
            }}
          >
            Aún no tienes asignaturas registradas. Puedes crearlas conversando con el tutor.
          </p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            {analytics.map((item) => {
              const wComp = item.weekly_comparison || {};
              const lastW = item.last_week_tasks || {};
              const isUp = wComp.change_pct > 0;
              const isDown = wComp.change_pct < 0;
              const isSaving = savingGradeId === item.id;

              return (
                <div
                  key={item.id}
                  style={{
                    padding: "16px 20px",
                    borderRadius: "12px",
                    border: "1px solid var(--border)",
                    backgroundColor: "var(--bg-input)",
                    display: "flex",
                    flexDirection: "column",
                    gap: "14px"
                  }}
                >
                  {/* Cabecera: Asignatura + Píldora de Tendencia + Nota */}
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "12px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                      <h4 style={{ margin: 0, fontSize: "1.05rem", fontWeight: "700", color: "var(--text-primary)" }}>
                        {item.name}
                      </h4>
                      <span
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "4px",
                          fontWeight: "600",
                          color: "var(--text-secondary)",
                          fontSize: "11px",
                          padding: "2px 8px",
                          borderRadius: "12px",
                          backgroundColor: "var(--bg-surface)",
                          border: "1px solid var(--border)"
                        }}
                      >
                        {isUp ? <TrendingUp size={12} style={{ color: "var(--brand)" }} /> : isDown ? <TrendingDown size={12} /> : null}
                        {wComp.change_pct > 0 ? `+${wComp.change_pct}%` : `${wComp.change_pct || 0}%`} vs sem. anterior
                      </span>
                    </div>

                    {/* Input de Nota Integrado */}
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "6px",
                        backgroundColor: "var(--bg-surface)",
                        padding: "3px 4px 3px 10px",
                        borderRadius: "8px",
                        border: "1px solid var(--border)"
                      }}
                    >
                      <span style={{ fontSize: "12px", fontWeight: "600", color: "var(--text-secondary)" }}>Nota:</span>
                      <input
                        type="number"
                        step="0.1"
                        min="0"
                        max="10"
                        value={gradeInputs[item.id] !== undefined ? gradeInputs[item.id] : ""}
                        onChange={(e) => handleGradeChange(item.id, e.target.value)}
                        placeholder="0.0"
                        style={{
                          width: "45px",
                          padding: "2px 4px",
                          borderRadius: "4px",
                          border: "none",
                          backgroundColor: "transparent",
                          color: "var(--text-primary)",
                          textAlign: "center",
                          fontSize: "13px",
                          fontWeight: "700",
                          outline: "none"
                        }}
                      />
                      <button
                        onClick={() => saveGrade(item.id)}
                        disabled={isSaving}
                        style={{
                          padding: "4px 10px",
                          borderRadius: "6px",
                          border: "none",
                          backgroundColor: "var(--brand)",
                          color: "#ffffff",
                          cursor: isSaving ? "wait" : "pointer",
                          fontSize: "11px",
                          fontWeight: "600"
                        }}
                      >
                        {isSaving ? "..." : "Guardar"}
                      </button>
                    </div>
                  </div>

                  {/* Grid de Métricas */}
                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
                      gap: "16px",
                      paddingTop: "10px",
                      borderTop: "1px solid var(--border)"
                    }}
                  >
                    <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
                      <span style={{ fontSize: "11px", color: "var(--text-secondary)", fontWeight: "600", display: "flex", alignItems: "center", gap: "4px" }}>
                        <Clock size={12} /> Tiempo Total
                      </span>
                      <span style={{ fontSize: "14px", fontWeight: "700", color: "var(--text-primary)" }}>
                        {formatTime(item.hours)}
                      </span>
                      <span style={{ fontSize: "11px", color: "var(--text-secondary)" }}>
                        ({formatTime(wComp.current_week_hours || 0)} esta semana)
                      </span>
                    </div>

                    <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
                      <span style={{ fontSize: "11px", color: "var(--text-secondary)", fontWeight: "600", display: "flex", alignItems: "center", gap: "4px" }}>
                        <CheckSquare size={12} /> Tareas (Últimos 7 días)
                      </span>
                      <span style={{ fontSize: "14px", fontWeight: "700", color: "var(--text-primary)" }}>
                        <span>{lastW.completed || 0} completadas</span>
                        <span style={{ color: "var(--text-secondary)", fontWeight: "400" }}> / {lastW.pending || 0} pend.</span>
                      </span>
                      <span style={{ fontSize: "11px", color: "var(--text-secondary)" }}>
                        Histórico: {item.tasks_completed} de {item.total_tasks_created || (item.tasks_completed + item.tasks_pending)}
                      </span>
                    </div>

                    <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
                      <span style={{ fontSize: "11px", color: "var(--text-secondary)", fontWeight: "600", display: "flex", alignItems: "center", gap: "4px" }}>
                        <Zap size={12} /> Concentración Media
                      </span>
                      <span style={{ fontSize: "14px", fontWeight: "700", color: "var(--text-primary)" }}>
                        {item.avg_concentration !== null ? `${item.avg_concentration} / 5` : "Sin datos"}
                      </span>
                      <span style={{ fontSize: "11px", color: "var(--text-secondary)" }}>
                        basado en sesiones
                      </span>
                    </div>
                  </div>

                  {/* Desplegables de Alertas */}
                  {(item.overdue_tasks_count > 0 || item.neglected_tasks_count > 0) && (
                    <div style={{ display: "flex", flexDirection: "column", gap: "8px", paddingTop: "4px" }}>
                      {item.overdue_tasks_count > 0 && (
                        <details style={{ borderRadius: "8px", border: "1px solid var(--border)", backgroundColor: "var(--bg-surface)", overflow: "hidden" }}>
                          <summary
                            style={{
                              padding: "8px 12px",
                              fontSize: "12px",
                              fontWeight: "600",
                              cursor: "pointer",
                              display: "flex",
                              alignItems: "center",
                              gap: "6px",
                              userSelect: "none",
                              color: "var(--text-primary)",
                              backgroundColor: "rgba(239, 68, 68, 0.12)"
                            }}
                          >
                            <AlertTriangle size={14} style={{ color: "var(--brand)", flexShrink: 0 }} />
                            <span>Tareas fuera de plazo o vencidas ({item.overdue_tasks_count})</span>
                          </summary>
                          <div style={{ padding: "10px 14px", borderTop: "1px solid var(--border)", backgroundColor: "var(--bg-input)" }}>
                            <ul style={{ margin: 0, paddingLeft: "18px", fontSize: "12px", color: "var(--text-secondary)", display: "flex", flexDirection: "column", gap: "4px" }}>
                              {item.overdue_tasks.map((taskName, idx) => (
                                <li key={idx} style={{ color: "var(--text-primary)" }}>{taskName}</li>
                              ))}
                            </ul>
                          </div>
                        </details>
                      )}

                      {item.neglected_tasks_count > 0 && (
                        <details style={{ borderRadius: "8px", border: "1px solid var(--border)", backgroundColor: "var(--bg-surface)", overflow: "hidden" }}>
                          <summary
                            style={{
                              padding: "8px 12px",
                              fontSize: "12px",
                              fontWeight: "600",
                              cursor: "pointer",
                              display: "flex",
                              alignItems: "center",
                              gap: "6px",
                              userSelect: "none",
                              color: "var(--text-primary)",
                              backgroundColor: "rgba(245, 158, 11, 0.12)"
                            }}
                          >
                            <Clock3 size={14} style={{ color: "var(--brand)", flexShrink: 0 }} />
                            <span>Tareas desatendidas (&lt; 15 min registrados) ({item.neglected_tasks_count})</span>
                          </summary>
                          <div style={{ padding: "10px 14px", borderTop: "1px solid var(--border)", backgroundColor: "var(--bg-input)" }}>
                            <ul style={{ margin: 0, paddingLeft: "18px", fontSize: "12px", color: "var(--text-secondary)", display: "flex", flexDirection: "column", gap: "4px" }}>
                              {item.neglected_tasks.map((taskName, idx) => (
                                <li key={idx} style={{ color: "var(--text-primary)" }}>{taskName}</li>
                              ))}
                            </ul>
                          </div>
                        </details>
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
  );
}