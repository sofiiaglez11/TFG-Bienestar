"use client";

import { useState } from "react";
import { ListChecks, Tag } from "lucide-react";

export default function TimeBreakdownAnalysis({ timeBreakdown = {}, formatTime }) {
    const [subjectFilter, setSubjectFilter] = useState("All");
    const [tagFilter, setTagFilter] = useState("All");

    const unifiedTasks = timeBreakdown.unified_tasks || [];

    const availableSubjects = ["All", ...new Set(unifiedTasks.map((t) => t.subject).filter(Boolean))];
    const availableTags = ["All", ...new Set(unifiedTasks.flatMap((t) => t.tags || []).filter(Boolean))];

    const filteredTasks = unifiedTasks.filter((t) => {
        const matchSubject = subjectFilter === "All" || t.subject === subjectFilter;
        const matchTag = tagFilter === "All" || (t.tags && t.tags.includes(tagFilter));
        return matchSubject && matchTag;
    });

    const filteredTotalHoursRaw = filteredTasks.reduce((acc, t) => acc + (t.hours || 0) + ((t.minutes || 0) / 60), 0);

    return (
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
                        {availableSubjects.map((s) => (
                            <option key={s} value={s}>{s === "All" ? "Todas" : s}</option>
                        ))}
                    </select>
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                    <label style={{ fontSize: "12px", fontWeight: "600", color: "var(--text-secondary)" }}>Etiqueta</label>
                    <select
                        value={tagFilter}
                        onChange={(e) => setTagFilter(e.target.value)}
                        style={{ padding: "6px 12px", borderRadius: "6px", border: "1px solid var(--border)", backgroundColor: "var(--bg-surface)", color: "var(--text-primary)", fontSize: "13px" }}
                    >
                        {availableTags.map((t) => (
                            <option key={t} value={t}>{t === "All" ? "Todas" : t}</option>
                        ))}
                    </select>
                </div>

                <div style={{ marginLeft: "auto", display: "flex", flexDirection: "column", alignItems: "flex-end" }}>
                    <span style={{ fontSize: "12px", color: "var(--text-secondary)", fontWeight: "600" }}>Tiempo Total Filtrado</span>
                    <span style={{ fontSize: "18px", fontWeight: "700", color: "var(--brand)" }}>
                        {formatTime(filteredTotalHoursRaw)}
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
                            <div
                                key={idx}
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
                                <div style={{ display: "flex", alignItems: "flex-start", gap: "8px" }}>
                                    <span style={{ fontSize: "13px", fontWeight: "700", color: "var(--brand)", marginTop: "1px" }}>
                                        {item.subject}
                                    </span>
                                    <span style={{ fontSize: "14px", color: "var(--text-secondary)" }}>|</span>

                                    <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                                        <span style={{ fontSize: "14px", fontWeight: "600" }}>{item.title}</span>
                                        {item.tags && item.tags.length > 0 && (
                                            <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
                                                {item.tags.map((tag) => (
                                                    <span
                                                        key={tag}
                                                        style={{
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
                                                        }}
                                                    >
                                                        <Tag size={10} /> {tag}
                                                    </span>
                                                ))}
                                            </div>
                                        )}
                                    </div>
                                </div>
                                <div style={{ whiteSpace: "nowrap" }}>
                                    <span style={{ fontSize: "14px", color: "var(--brand)", fontWeight: "700" }}>
                                        {formatTime(item.hours)}
                                    </span>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}