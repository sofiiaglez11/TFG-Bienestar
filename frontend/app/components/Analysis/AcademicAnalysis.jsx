"use client";

import {
  TrendingUp,
  TrendingDown,
  Clock,
  CheckSquare,
  Zap,
  AlertTriangle,
  Clock3
} from "lucide-react";
import styles from "./Analysis.module.css";

export default function AcademicAnalysis({
  analytics = [],
  studyPlan = {},
  gradeInputs = {},
  formatTime
}) {
  return (
    <div className={styles.root}>
      {/* Lista de Asignaturas */}
      <div>
        {analytics.length === 0 ? (
          <p className={styles.subjectsEmpty}>
            Aún no tienes asignaturas registradas. Puedes crearlas conversando con el tutor.
          </p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            {analytics.map((item) => {
              const wComp = item.weekly_comparison || {};
              const lastW = item.last_week_tasks || {};
              const isUp = wComp.change_pct > 0;
              const isDown = wComp.change_pct < 0;

              // Obtener la nota del backend o de gradeInputs
              const currentGrade =
                gradeInputs[item.id] !== undefined && gradeInputs[item.id] !== ""
                  ? gradeInputs[item.id]
                  : item.grade !== undefined && item.grade !== null
                    ? item.grade
                    : null;

              return (
                <div key={item.id} className={styles.cardLg}>
                  {/* Cabecera: Asignatura + Píldora de Tendencia + Nota Read-Only */}
                  <div className={styles.subjectHeader}>
                    <div className={styles.subjectNameRow}>
                      <h4 className={styles.subjectName}>{item.name}</h4>
                      <span className={styles.trendBadge}>
                        {isUp ? <TrendingUp size={12} style={{ color: "var(--brand)" }} /> : isDown ? <TrendingDown size={12} /> : null}
                        {wComp.change_pct > 0 ? `+${wComp.change_pct}%` : `${wComp.change_pct || 0}%`} vs sem. anterior
                      </span>
                    </div>

                    {/* Badge de Nota */}
                    <div className={styles.gradeBadge}>
                      <span className={styles.gradeLabel}>Nota:</span>
                      <span className={currentGrade !== null ? styles.gradeValue : styles.gradeValueEmpty}>
                        {currentGrade !== null ? currentGrade : "-"}
                      </span>
                    </div>
                  </div>

                  {/* Grid de Métricas */}
                  <div className={styles.metricsGrid}>
                    <div className={styles.metricItem}>
                      <span className={styles.metricLabel}>
                        <Clock size={12} /> Tiempo Total
                      </span>
                      <span className={styles.metricMain}>{formatTime(item.hours)}</span>
                      <span className={styles.metricSub}>
                        ({formatTime(wComp.current_week_hours || 0)} esta semana)
                      </span>
                    </div>

                    <div className={styles.metricItem}>
                      <span className={styles.metricLabel}>
                        <CheckSquare size={12} /> Tareas (Últimos 7 días)
                      </span>
                      <span className={styles.metricMain}>
                        <span>{lastW.completed || 0} completadas</span>
                        <span style={{ color: "var(--text-secondary)", fontWeight: "400" }}> / {lastW.pending || 0} pend.</span>
                      </span>
                      <span className={styles.metricSub}>
                        Histórico: {item.tasks_completed} de {item.total_tasks_created || (item.tasks_completed + item.tasks_pending)}
                      </span>
                    </div>

                    <div className={styles.metricItem}>
                      <span className={styles.metricLabel}>
                        <Zap size={12} /> Concentración Media
                      </span>
                      <span className={styles.metricMain}>
                        {item.avg_concentration !== null ? `${item.avg_concentration} / 5` : "Sin datos"}
                      </span>
                      <span className={styles.metricSub}>basado en sesiones</span>
                    </div>
                  </div>

                  {/* Desplegables de Alertas */}
                  {(item.overdue_tasks_count > 0 || item.neglected_tasks_count > 0) && (
                    <div className={styles.alertsGroup}>
                      {item.overdue_tasks_count > 0 && (
                        <details className={styles.alertDetails}>
                          <summary className={styles.alertSummaryRed}>
                            <AlertTriangle size={14} style={{ color: "var(--brand)", flexShrink: 0 }} />
                            <span>Tareas fuera de plazo o vencidas ({item.overdue_tasks_count})</span>
                          </summary>
                          <div className={styles.alertContent}>
                            <ul className={styles.alertList}>
                              {item.overdue_tasks.map((taskName, idx) => (
                                <li key={idx} className={styles.alertListItem}>{taskName}</li>
                              ))}
                            </ul>
                          </div>
                        </details>
                      )}

                      {item.neglected_tasks_count > 0 && (
                        <details className={styles.alertDetails}>
                          <summary className={styles.alertSummaryAmber}>
                            <Clock3 size={14} style={{ color: "var(--brand)", flexShrink: 0 }} />
                            <span>Tareas desatendidas (&lt; 15 min registrados) ({item.neglected_tasks_count})</span>
                          </summary>
                          <div className={styles.alertContent}>
                            <ul className={styles.alertList}>
                              {item.neglected_tasks.map((taskName, idx) => (
                                <li key={idx} className={styles.alertListItem}>{taskName}</li>
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
