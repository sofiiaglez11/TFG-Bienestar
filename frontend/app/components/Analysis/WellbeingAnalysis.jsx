"use client";

import { useState } from "react";
import { AlertTriangle, Moon, Smile, Zap, ChevronLeft, ChevronRight } from "lucide-react";

export default function WellbeingAnalysis({ wellbeing = {}, periodLabel, formatDate }) {
    const [wellbeingPage, setWellbeingPage] = useState(0);
    const WELLBEING_PER_PAGE = 7;

    const recentDays = wellbeing.recent_days || [];
    const totalPages = Math.ceil(recentDays.length / WELLBEING_PER_PAGE) || 1;
    const paginatedDays = recentDays.slice(
        wellbeingPage * WELLBEING_PER_PAGE,
        (wellbeingPage + 1) * WELLBEING_PER_PAGE
    );

    return (
        <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
            {wellbeing.worst_day && (
                <div
                    style={{
                        padding: "14px 16px",
                        borderRadius: "10px",
                        backgroundColor: "#fef2f2",
                        border: "1px solid #fecaca",
                        color: "#991b1b",
                        fontSize: "14px",
                        display: "flex",
                        alignItems: "center",
                        gap: "10px"
                    }}
                >
                    <AlertTriangle size={20} />
                    <div>
                        <strong>Día crítico detectado:</strong> El <strong>{wellbeing.worst_day}</strong> registraste el menor nivel de estado de ánimo. Recuerda programar pausas de recuperación.
                    </div>
                </div>
            )}

            {/* Registro de Bienestar */}
            <div>
                <h3 style={{ fontSize: "1.05rem", fontWeight: "600", marginBottom: "12px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <span style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        <Moon size={18} /> Registro de Bienestar y Sueño
                    </span>
                    <span style={{ fontSize: "12px", fontWeight: "500", color: "var(--text-secondary)", backgroundColor: "var(--bg-page)", padding: "2px 8px", borderRadius: "12px", border: "1px solid var(--border)" }}>
                        {periodLabel}
                    </span>
                </h3>

                <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                    {paginatedDays.length === 0 ? (
                        <p style={{ color: "var(--text-secondary)", fontSize: "13px", margin: 0 }}>
                            No hay registros de bienestar en este periodo.
                        </p>
                    ) : (
                        paginatedDays.map((dayData, idx) => {
                            const sleepVal = dayData.sleep;
                            const moodVal = dayData.mood;
                            const energyVal = dayData.energy;
                            const formattedDate = formatDate(dayData.date) || dayData.date;

                            return (
                                <div
                                    key={dayData.date || idx}
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
                                    <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                                        <span style={{ fontSize: "14px", fontWeight: "700", color: "var(--text-primary)" }}>
                                            {dayData.day_name}, {formattedDate}
                                        </span>
                                    </div>

                                    <div style={{ display: "flex", gap: "16px", flexWrap: "wrap", justifyContent: "flex-end" }}>
                                        <div style={{ display: "flex", alignItems: "center", gap: "6px", backgroundColor: "#eff6ff", color: "#2563eb", padding: "4px 10px", borderRadius: "12px", border: "1px solid #dbeafe" }}>
                                            <Moon size={14} />
                                            <span style={{ fontSize: "12px", fontWeight: "600" }}>
                                                {sleepVal !== null && sleepVal !== undefined ? `${sleepVal}h Sueño` : "Sin datos"}
                                            </span>
                                        </div>
                                        <div style={{ display: "flex", alignItems: "center", gap: "6px", backgroundColor: "#fef3c7", color: "#d97706", padding: "4px 10px", borderRadius: "12px", border: "1px solid #fde68a" }}>
                                            <Smile size={14} />
                                            <span style={{ fontSize: "12px", fontWeight: "600" }}>
                                                {moodVal !== null && moodVal !== undefined ? `Ánimo ${moodVal}/5` : "Sin datos"}
                                            </span>
                                        </div>
                                        <div style={{ display: "flex", alignItems: "center", gap: "6px", backgroundColor: "#dcfce7", color: "#16a34a", padding: "4px 10px", borderRadius: "12px", border: "1px solid #bbf7d0" }}>
                                            <Zap size={14} />
                                            <span style={{ fontSize: "12px", fontWeight: "600" }}>
                                                {energyVal !== null && energyVal !== undefined ? `Energía ${energyVal}/5` : "Sin datos"}
                                            </span>
                                        </div>
                                    </div>
                                </div>
                            );
                        })
                    )}
                </div>

                {/* Controles de Paginación */}
                {recentDays.length > WELLBEING_PER_PAGE && (
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "12px" }}>
                        <button
                            disabled={wellbeingPage === 0}
                            onClick={() => setWellbeingPage((prev) => prev - 1)}
                            style={{
                                padding: "6px 12px",
                                borderRadius: "6px",
                                border: "1px solid var(--border)",
                                backgroundColor: "var(--bg-input)",
                                color: "var(--text-primary)",
                                cursor: wellbeingPage === 0 ? "not-allowed" : "pointer",
                                opacity: wellbeingPage === 0 ? 0.5 : 1,
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
                            Página {wellbeingPage + 1} de {totalPages}
                        </span>

                        <button
                            disabled={wellbeingPage >= totalPages - 1}
                            onClick={() => setWellbeingPage((prev) => prev + 1)}
                            style={{
                                padding: "6px 12px",
                                borderRadius: "6px",
                                border: "1px solid var(--border)",
                                backgroundColor: "var(--bg-input)",
                                color: "var(--text-primary)",
                                cursor: wellbeingPage >= totalPages - 1 ? "not-allowed" : "pointer",
                                opacity: wellbeingPage >= totalPages - 1 ? 0.5 : 1,
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

            <div
                style={{
                    padding: "16px",
                    borderRadius: "10px",
                    border: "1px solid var(--border)",
                    backgroundColor: "var(--bg-input)",
                    fontSize: "13px",
                    color: "var(--text-primary)",
                    lineHeight: "1.5"
                }}
            >
                <strong>Registro de Bienestar:</strong> Para guardar tus horas de descanso diarias o tu estado de ánimo, simplemente coméntaselo al tutor de bienestar en el chat (ej: <em>"Hoy he dormido 7 horas y me siento descansado"</em>).
            </div>
        </div>
    );
}