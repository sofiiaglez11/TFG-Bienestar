import React from "react";
import { Tag as TagIcon } from "lucide-react";
import { getTagStyle } from "../utils/tagUtils";
import { useTagColors } from "../utils/tagColorStore";

/**
 * Componente Badge reutilizable para renderizar etiquetas con estilo consistente.
 * Si onClick se proporciona, permite ser interactivo o desplegar el selector de color.
 */
export default function TagBadge({ name, color, customColorMap = {}, onClick, showIcon = true, size = "md" }) {
    // Colores guardados del usuario (global) < customColorMap explícito < prop `color`
    const storedColors = useTagColors();
    const map = { ...storedColors, ...customColorMap, ...(color ? { [name]: color } : {}) };
    const style = getTagStyle(name, map);

    const isSmall = size === "sm";

    return (
        <span
            onClick={onClick ? (e) => onClick(e, name) : undefined}
            style={{
                display: "inline-flex",
                alignItems: "center",
                gap: isSmall ? "3px" : "5px",
                background: style.bg,
                color: style.text,
                border: `1px solid ${style.border}`,
                borderRadius: "9999px",
                padding: isSmall ? "2px 8px" : "3px 10px",
                fontSize: isSmall ? "11px" : "12px",
                fontWeight: "600",
                whiteSpace: "nowrap",
                cursor: onClick ? "pointer" : "default",
                transition: "all 0.15s ease",
            }}
            className={onClick ? "hover:brightness-95 hover:scale-105" : ""}
            title={onClick ? `Haz clic para cambiar el color de #${name}` : `#${name}`}
        >
            {showIcon && <TagIcon size={isSmall ? 10 : 12} style={{ color: style.text }} />}
            {name}
        </span>
    );
}