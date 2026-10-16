"use client";

import { useSyncExternalStore } from "react";

/**
 * Almacén global (sin Provider) con los colores de etiquetas del usuario, cargados de /api/tags.
 * Claves en minúsculas: { "backend": "#4f46e5", ... }. Solo incluye etiquetas con color explícito.
 *
 * Uso en componentes:  const colorMap = useTagColors();  ->  getTagStyle(nombre, colorMap)
 * Tras cambiar colores:  setTagColorLocal(nombre, hex)  o  refreshTagColors()
 * Al cerrar sesión:      clearTagColors()
 */

const RAW_BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
const BACKEND_URL = RAW_BACKEND_URL.replace(/\/+$/, "");

const EMPTY = {};
let colorMap = EMPTY;
let loaded = false;
let loading = null;
const listeners = new Set();

const emit = () => listeners.forEach((l) => l());

export async function refreshTagColors() {
    if (typeof window === "undefined") return;
    const token = localStorage.getItem("token");
    if (!token) return;
    if (loading) return loading;

    loading = (async () => {
        try {
            const res = await fetch(`${BACKEND_URL}/api/tags`, {
                headers: { Authorization: `Bearer ${token}` },
            });
            if (!res.ok) return;
            const data = await res.json();
            const next = {};
            for (const t of data.tags || []) {
                if (t.name && t.color) next[t.name.trim().toLowerCase()] = t.color;
            }
            colorMap = next;
            loaded = true;
            emit();
        } catch (err) {
            console.error("Error al cargar colores de etiquetas:", err);
        } finally {
            loading = null;
        }
    })();
    return loading;
}

export function setTagColorLocal(name, hex) {
    if (!name) return;
    colorMap = { ...colorMap, [name.trim().toLowerCase()]: hex };
    emit();
}

export function clearTagColors() {
    colorMap = EMPTY;
    loaded = false;
    emit();
}

function subscribe(listener) {
    listeners.add(listener);
    if (!loaded && !loading) refreshTagColors();
    return () => listeners.delete(listener);
}

const getSnapshot = () => colorMap;
const getServerSnapshot = () => EMPTY;

export function useTagColors() {
    return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}