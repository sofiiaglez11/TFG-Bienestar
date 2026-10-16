// Paleta curada de colores accesible y armónica
export const TAG_COLOR_PALETTE = [
    { id: "sky", hex: "#0284c7", label: "Celeste" },
    { id: "indigo", hex: "#4f46e5", label: "Índigo" },
    { id: "purple", hex: "#9333ea", label: "Púrpura" },
    { id: "pink", hex: "#db2777", label: "Rosa" },
    { id: "rose", hex: "#e11d48", label: "Rosa Fuerte" },
    { id: "orange", hex: "#ea580c", label: "Naranja" },
    { id: "amber", hex: "#d97706", label: "Ámbar" },
    { id: "emerald", hex: "#059669", label: "Esmeralda" },
    { id: "teal", hex: "#0d9488", label: "Turquesa" },
    { id: "slate", hex: "#475569", label: "Gris Sombra" },
];

/**
 * Convierte un hex a valores RGBA con opacidad dada.
 */
export function hexToRgba(hex, alpha = 0.15) {
    if (!hex || typeof hex !== "string" || !hex.startsWith("#")) {
        return `rgba(100, 116, 139, ${alpha})`;
    }
    const cleanHex = hex.replace("#", "");
    let r = 0, g = 0, b = 0;
    if (cleanHex.length === 3) {
        r = parseInt(cleanHex[0] + cleanHex[0], 16);
        g = parseInt(cleanHex[1] + cleanHex[1], 16);
        b = parseInt(cleanHex[2] + cleanHex[2], 16);
    } else if (cleanHex.length === 6) {
        r = parseInt(cleanHex.substring(0, 2), 16);
        g = parseInt(cleanHex.substring(2, 4), 16);
        b = parseInt(cleanHex.substring(4, 6), 16);
    }
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

/**
 * Genera el objeto de estilos { bg, text, border } a partir de un color asignado o determinista según el nombre.
 */
export function getTagStyle(tagText, customColorMap = {}) {
    if (!tagText) {
        return { bg: "rgba(100, 116, 139, 0.15)", text: "#475569", border: "rgba(100, 116, 139, 0.4)" };
    }

    const cleanName = tagText.trim();

    // Color explícito asignado por el usuario (búsqueda sin distinguir mayúsculas)
    let hex = customColorMap ? customColorMap[cleanName] : null;
    if (!hex && customColorMap) {
        const key = Object.keys(customColorMap).find(
            (k) => k.trim().toLowerCase() === cleanName.toLowerCase()
        );
        if (key) hex = customColorMap[key];
    }
    if (hex) {
        return {
            bg: hexToRgba(hex, 0.15),
            text: hex,
            border: hexToRgba(hex, 0.4)
        };
    }

    // Fallback determinista (hash de la cadena)
    const lower = cleanName.toLowerCase();
    let hash = 0;
    for (let i = 0; i < lower.length; i++) {
        hash = lower.charCodeAt(i) + ((hash << 5) - hash);
    }
    const chosenColor = TAG_COLOR_PALETTE[Math.abs(hash) % TAG_COLOR_PALETTE.length].hex;

    return {
        bg: hexToRgba(chosenColor, 0.15),
        text: chosenColor,
        border: hexToRgba(chosenColor, 0.4)
    };
}