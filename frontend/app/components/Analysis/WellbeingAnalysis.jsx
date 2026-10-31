"use client";

import { useState } from "react";
import { Moon, Smile, Zap, ChevronLeft, ChevronRight } from "lucide-react";
import styles from "./Analysis.module.css";

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
        <div className={styles.root}>
            {/* Registro de Bienestar */}
            <div>
                <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                    {paginatedDays.length === 0 ? (
                        <p className={styles.empty}>
                            No hay registros de bienestar en este periodo.
                        </p>
                    ) : (
                        paginatedDays.map((dayData, idx) => {
                            const sleepVal = dayData.sleep;
                            const moodVal = dayData.mood;
                            const energyVal = dayData.energy;
                            const formattedDate = formatDate(dayData.date) || dayData.date;

                            return (
                                <div key={dayData.date || idx} className={styles.card}>
                                    <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                                        <span className={styles.dateName}>
                                            {dayData.day_name}, {formattedDate}
                                        </span>
                                    </div>

                                    <div className={styles.chipsRow}>
                                        <div className={styles.chipSleep}>
                                            <Moon size={14} />
                                            <span>
                                                {sleepVal !== null && sleepVal !== undefined ? `${sleepVal}h Sueño` : "Sin datos"}
                                            </span>
                                        </div>
                                        <div className={styles.chipMood}>
                                            <Smile size={14} />
                                            <span>
                                                {moodVal !== null && moodVal !== undefined ? `Ánimo ${moodVal}/5` : "Sin datos"}
                                            </span>
                                        </div>
                                        <div className={styles.chipEnergy}>
                                            <Zap size={14} />
                                            <span>
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
                    <div className={styles.pagination}>
                        <button
                            disabled={wellbeingPage === 0}
                            onClick={() => setWellbeingPage((prev) => prev - 1)}
                            className={styles.paginationBtn}
                        >
                            <ChevronLeft size={14} /> Anterior
                        </button>

                        <span className={styles.paginationInfo}>
                            Página {wellbeingPage + 1} de {totalPages}
                        </span>

                        <button
                            disabled={wellbeingPage >= totalPages - 1}
                            onClick={() => setWellbeingPage((prev) => prev + 1)}
                            className={styles.paginationBtn}
                        >
                            Siguiente <ChevronRight size={14} />
                        </button>
                    </div>
                )}
            </div>

            <div className={styles.infoBox}>
                <strong>Registro de Bienestar:</strong> Para guardar tus horas de descanso diarias o tu estado de ánimo, simplemente coméntaselo al Asistente Inteligente en el chat (ej: <em>&quot;Hoy he dormido 7 horas y me siento descansado&quot;</em>).
            </div>
        </div>
    );
}
