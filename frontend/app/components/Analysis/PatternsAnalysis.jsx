"use client";

import { useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import styles from "./Analysis.module.css";

export default function PatternsAnalysis({ patterns = {}, periodLabel, formatDate, formatTime }) {
    const [patternsPage, setPatternsPage] = useState(0);
    const PATTERNS_PER_PAGE = 7;

    const recentHoursList = patterns.recent_hours_list || [];
    const minutesByHour = patterns.minutes_by_hour || Array(24).fill(0);
    const maxMinsByHour = Math.max(...minutesByHour, 10);

    const totalPages = Math.ceil(recentHoursList.length / PATTERNS_PER_PAGE) || 1;
    const paginatedHours = recentHoursList.slice(
        patternsPage * PATTERNS_PER_PAGE,
        (patternsPage + 1) * PATTERNS_PER_PAGE
    );

    return (
        <div className={styles.root}>
            {/* Distribución de Horas por Día */}
            <div>
                <h3 className={styles.sectionTitle}>
                    <span>Distribución Diaria de Horas</span>
                </h3>

                <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                    {paginatedHours.length === 0 ? (
                        <p className={styles.empty}>
                            No hay registros de horas en este periodo.
                        </p>
                    ) : (
                        paginatedHours.map((dayData) => {
                            const hrs = dayData.hours || 0;
                            const maxH = Math.max(...recentHoursList.map((d) => d.hours), 5);
                            const pct = Math.min(100, Math.max(0, (hrs / maxH) * 100));
                            const formattedDate = formatDate(dayData.date) || dayData.date;

                            return (
                                <div
                                    key={dayData.date || dayData.day_name}
                                    className={styles.card}
                                >
                                    <div className={styles.dateLabel}>
                                        <span className={styles.dateName}>
                                            {dayData.day_name}, {formattedDate}
                                        </span>
                                    </div>

                                    {/* Barra de progreso: el contenedor es .progressBar, el fill es inline (depende del %) */}
                                    <div className={styles.progressBar}>
                                        <div
                                            style={{
                                                width: `${pct}%`,
                                                backgroundColor: "var(--brand)",
                                                height: "100%",
                                                borderRadius: "5px",
                                                transition: "width 0.4s ease"
                                            }}
                                        />
                                    </div>

                                    <div className={styles.timeValue}>
                                        {formatTime(hrs)}
                                    </div>
                                </div>
                            );
                        })
                    )}
                </div>

                {/* Controles de Paginación */}
                {recentHoursList.length > PATTERNS_PER_PAGE && (
                    <div className={styles.pagination}>
                        <button
                            disabled={patternsPage === 0}
                            onClick={() => setPatternsPage((prev) => prev - 1)}
                            className={styles.paginationBtn}
                        >
                            <ChevronLeft size={14} /> Anterior
                        </button>

                        <span className={styles.paginationInfo}>
                            Página {patternsPage + 1} de {totalPages}
                        </span>

                        <button
                            disabled={patternsPage >= totalPages - 1}
                            onClick={() => setPatternsPage((prev) => prev + 1)}
                            className={styles.paginationBtn}
                        >
                            Siguiente <ChevronRight size={14} />
                        </button>
                    </div>
                )}
            </div>

            {/* Horario Preferido de Estudio */}
            <div>
                <h3 className={styles.sectionTitle}>
                    <span>Horario Preferido de Estudio</span>
                    <span className={styles.periodBadge}>{periodLabel}</span>
                </h3>
                <div className={styles.chartContainer}>
                    <div className={styles.chartBars}>
                        {minutesByHour.map((mins, idx) => {
                            const hPct = Math.min(100, Math.max(0, (mins / maxMinsByHour) * 100));
                            return (
                                <div key={idx} className={styles.chartBarWrapper}>
                                    {mins > 0 && (
                                        <span className={styles.chartBarLabel}>{mins}m</span>
                                    )}
                                    {/* Fill del bar: inline porque depende del % */}
                                    <div
                                        style={{
                                            width: "100%",
                                            height: `${hPct}%`,
                                            backgroundColor: "var(--brand)",
                                            borderRadius: "3px 3px 0 0",
                                            transition: "height 0.4s ease",
                                            minHeight: mins > 0 ? "2px" : "0px"
                                        }}
                                        title={`${idx}:00 - ${mins} mins`}
                                    />
                                </div>
                            );
                        })}
                    </div>
                    <div className={styles.chartXAxis}>
                        {[0, 3, 6, 9, 12, 15, 18, 21, 23].map((h) => (
                            <span key={h}>{`${String(h).padStart(2, "0")}h`}</span>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
}
