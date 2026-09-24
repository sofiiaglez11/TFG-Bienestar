"use client";

import { useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";

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
        <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
            {/* Distribución de Horas por Día */}
            <div>
                <h3 style={{ fontSize: "1.05rem", fontWeight: "600", marginBottom: "12px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <span>Distribución Diaria de Horas</span>
                    <span style={{ fontSize: "12px", fontWeight: "500", color: "var(--text-secondary)", backgroundColor: "var(--bg-page)", padding: "2px 8px", borderRadius: "12px", border: "1px solid var(--border)" }}>
                        {periodLabel}
                    </span>
                </h3>

                <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                    {paginatedHours.length === 0 ? (
                        <p style={{ color: "var(--text-secondary)", fontSize: "13px", margin: 0 }}>
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
                                    style={{
                                        padding: "12px 16px",
                                        borderRadius: "10px",
                                        backgroundColor: "var(--bg-input)",
                                        border: "1px solid var(--border)",
                                        display: "flex",
                                        justifyContent: "space-between",
                                        alignItems: "center",
                                        gap: "12px"
                                    }}
                                >
                                    <div style={{ display: "flex", flexDirection: "column", gap: "4px", width: "130px", flexShrink: 0 }}>
                                        <span style={{ fontSize: "14px", fontWeight: "700", color: "var(--text-primary)" }}>
                                            {dayData.day_name}, {formattedDate}
                                        </span>
                                    </div>

                                    <div style={{ flex: 1, backgroundColor: "var(--border)", height: "10px", borderRadius: "5px", overflow: "hidden" }}>
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

                                    <div style={{ whiteSpace: "nowrap", width: "70px", textAlign: "right" }}>
                                        <span style={{ fontSize: "14px", color: "var(--brand)", fontWeight: "700" }}>
                                            {formatTime(hrs)}
                                        </span>
                                    </div>
                                </div>
                            );
                        })
                    )}
                </div>

                {/* Controles de Paginación */}
                {recentHoursList.length > PATTERNS_PER_PAGE && (
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "12px" }}>
                        <button
                            disabled={patternsPage === 0}
                            onClick={() => setPatternsPage((prev) => prev - 1)}
                            style={{
                                padding: "6px 12px",
                                borderRadius: "6px",
                                border: "1px solid var(--border)",
                                backgroundColor: "var(--bg-input)",
                                color: "var(--text-primary)",
                                cursor: patternsPage === 0 ? "not-allowed" : "pointer",
                                opacity: patternsPage === 0 ? 0.5 : 1,
                                display: "flex",
                                alignItems: "center",
                                gap: "4px",
                                fontSize: "12px",
                                fontWeight: "600"
                            }}
                        >
                            <ChevronLeft size={14} /> Anterior
                        </button>

                        <span style={{ fontSize: "12px", color: "var(--text-secondary)", fontWeight: "500" }}>
                            Página {patternsPage + 1} de {totalPages}
                        </span>

                        <button
                            disabled={patternsPage >= totalPages - 1}
                            onClick={() => setPatternsPage((prev) => prev + 1)}
                            style={{
                                padding: "6px 12px",
                                borderRadius: "6px",
                                border: "1px solid var(--border)",
                                backgroundColor: "var(--bg-input)",
                                color: "var(--text-primary)",
                                cursor: patternsPage >= totalPages - 1 ? "not-allowed" : "pointer",
                                opacity: patternsPage >= totalPages - 1 ? 0.5 : 1,
                                display: "flex",
                                alignItems: "center",
                                gap: "4px",
                                fontSize: "12px",
                                fontWeight: "600"
                            }}
                        >
                            Siguiente <ChevronRight size={14} />
                        </button>
                    </div>
                )}
            </div>

            {/* Horario Preferido de Estudio */}
            <div>
                <h3 style={{ fontSize: "1.05rem", fontWeight: "600", marginBottom: "12px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <span>Horario Preferido de Estudio</span>
                    <span style={{ fontSize: "12px", fontWeight: "500", color: "var(--text-secondary)", backgroundColor: "var(--bg-page)", padding: "2px 8px", borderRadius: "12px", border: "1px solid var(--border)" }}>
                        {periodLabel}
                    </span>
                </h3>
                <div style={{ padding: "16px", borderRadius: "10px", backgroundColor: "var(--bg-input)", border: "1px solid var(--border)", display: "flex", flexDirection: "column", gap: "8px" }}>
                    <div style={{ display: "flex", alignItems: "flex-end", height: "120px", gap: "2px" }}>
                        {minutesByHour.map((mins, idx) => {
                            const hPct = Math.min(100, Math.max(0, (mins / maxMinsByHour) * 100));
                            return (
                                <div key={idx} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "flex-end", height: "100%" }}>
                                    {mins > 0 && (
                                        <span style={{ fontSize: "9px", color: "var(--text-secondary)", marginBottom: "2px" }}>
                                            {mins}m
                                        </span>
                                    )}
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
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: "11px", color: "var(--text-secondary)", marginTop: "6px", paddingLeft: "0" }}>
                        {[0, 3, 6, 9, 12, 15, 18, 21, 23].map((h) => (
                            <span key={h} style={{ flex: h === 23 ? "none" : undefined }}>{`${String(h).padStart(2, "0")}h`}</span>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
}