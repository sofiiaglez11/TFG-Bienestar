"use client";

import { useState } from "react";
import { ListChecks } from "lucide-react";
import TagBadge from "../TagBadge";
import styles from "./Analysis.module.css";

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
        <div className={styles.root}>
            {/* Filtros */}
            <div className={styles.filtersBar}>
                <span style={{ fontSize: "14px", fontWeight: "700", color: "var(--text-primary)" }}>Filtros</span>

                <div className={styles.filterRow}>
                    <label className={styles.filterLabel}>Asignatura</label>
                    <select
                        value={subjectFilter}
                        onChange={(e) => setSubjectFilter(e.target.value)}
                        className={styles.filterSelect}
                    >
                        {availableSubjects.map((s) => (
                            <option key={s} value={s}>{s === "All" ? "Todas" : s}</option>
                        ))}
                    </select>
                </div>

                <div className={styles.filterRow}>
                    <label className={styles.filterLabel}>Etiqueta</label>
                    <select
                        value={tagFilter}
                        onChange={(e) => setTagFilter(e.target.value)}
                        className={styles.filterSelect}
                    >
                        {availableTags.map((t) => (
                            <option key={t} value={t}>{t === "All" ? "Todas" : t}</option>
                        ))}
                    </select>
                </div>

                <div className={styles.filterRowRight}>
                    <span className={styles.filterLabel}>Tiempo Total Filtrado</span>
                    <span className={styles.totalTime}>
                        {formatTime(filteredTotalHoursRaw)}
                    </span>
                </div>
            </div>

            {/* Lista Unificada de Tareas */}
            <div>
                <h4 className={styles.taskListHeader}>
                    <ListChecks size={18} /> Sesiones de Trabajo y Tareas
                </h4>
                {filteredTasks.length === 0 ? (
                    <p style={{ color: "var(--text-secondary)", fontSize: "14px" }}>No hay registros de tareas con los filtros seleccionados.</p>
                ) : (
                    <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                        {filteredTasks.map((item, idx) => (
                            <div key={idx} className={styles.taskItem}>
                                <div className={styles.taskLeft}>
                                    <span className={styles.taskSubject}>
                                        {item.subject}
                                    </span>
                                    <span className={styles.taskSeparator}>|</span>

                                    <div className={styles.taskMeta}>
                                        <span className={styles.taskTitle}>{item.title}</span>
                                        {item.tags && item.tags.length > 0 && (
                                            <div className={styles.taskTagsRow}>
                                                {item.tags.map((tag) => (
                                                    <TagBadge key={tag} name={tag} size="sm" />
                                                ))}
                                            </div>
                                        )}
                                    </div>
                                </div>
                                <div>
                                    <span className={styles.taskTime}>
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
