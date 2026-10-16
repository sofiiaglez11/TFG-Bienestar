import React, { Children } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { getTagStyle } from "../utils/tagUtils";
import { useTagColors } from "../utils/tagColorStore";
import remarkChatTokens from "../utils/remarkChatTokens";
import TagBadge from "./TagBadge";

/**
 * Renderizado markdown común para todo lo que escribe la IA
 * (burbujas del chat y resúmenes de cursos).
 *
 * No añade estilos de texto propios (tamaño, color...): los hereda del contenedor.
 * Uso: <MarkdownContent>{texto}</MarkdownContent>
 */

// FORMATO ANTIGUO ([etiqueta] y !fecha!): solo se mantiene en tablas para mensajes ya guardados en el historial.
const renderBadges = (text, colorMap = {}) => {
    if (typeof text !== "string") return text;

    // 1. Interpretar <br> o <br/> como saltos de línea reales de React
    if (text.includes("<br")) {
        const parts = text.split(/<br\s*\/?>/gi);
        return parts.reduce((acc, part, i) => {
            if (i === 0) return [renderBadges(part, colorMap)];
            return [...acc, <br key={`br-${i}`} />, renderBadges(part, colorMap)];
        }, []);
    }

    // 2. Regex para !texto! (fechas) y [texto] (etiquetas)
    const regex = /!([^!]+)!|\[([^\]]+)\]/g;
    const parts = [];
    let lastIndex = 0;
    let match;

    while ((match = regex.exec(text)) !== null) {
        if (match.index > lastIndex) {
            parts.push(text.slice(lastIndex, match.index));
        }

        if (match[1] !== undefined) {
            // Fecha vencida (!texto!) -> Texto en rojo, negrita y sin romper línea
            parts.push(
                <span
                    key={match.index}
                    style={{ color: "#dc2626", fontWeight: "700", whiteSpace: "nowrap" }}
                >
                    {match[1].trim()}
                </span>
            );
        } else if (match[2] !== undefined && /^\d+$/.test(match[2].trim())) {
            // [1], [2]... (prioridad en mensajes antiguos): se muestra el número sin píldora
            parts.push(match[2].trim());
        } else if (match[2] !== undefined) {
            // Píldoras ([texto]) -> Si la IA manda [backend, prompt], lo dividimos por comas
            const subTags = match[2].trim().split(",").map((t) => t.trim()).filter(Boolean);

            subTags.forEach((tagText, subIdx) => {
                const style = getTagStyle(tagText, colorMap);
                parts.push(
                    <span
                        key={`${match.index}-${subIdx}`}
                        style={{
                            display: "inline-block",
                            background: style.bg,
                            color: style.text,
                            border: `1px solid ${style.border}`,
                            borderRadius: "9999px",
                            padding: "2px 8px",
                            fontSize: "11px",
                            fontWeight: "600",
                            margin: "1px 2px",
                            whiteSpace: "nowrap",
                        }}
                    >
                        {tagText}
                    </span>
                );
            });
        }

        lastIndex = regex.lastIndex;
    }

    if (lastIndex < text.length) {
        parts.push(text.slice(lastIndex));
    }

    return parts.length > 0 ? parts : text;
};

// // Componente para hacer que los <li> con sublistas sean desplegables/colapsables
// // (desactivado: para usarlo, importar useState de "react" y poner `li: CollapsibleLi` abajo)
// function CollapsibleLi({ children }) {
//   const [open, setOpen] = useState(true);
//
//   const childrenArray = Children.toArray(children);
//
//   const sublists = [];
//   const content = [];
//
//   childrenArray.forEach((child) => {
//     if (
//       child &&
//       child.props &&
//       (child.props.node?.tagName === "ul" ||
//         child.props.node?.tagName === "ol" ||
//         child.type === "ul" ||
//         child.type === "ol")
//     ) {
//       sublists.push(child);
//     } else {
//       content.push(child);
//     }
//   });
//
//   if (sublists.length === 0) {
//     return <li style={{ marginBottom: "2px" }}>{children}</li>;
//   }
//
//   return (
//     <li style={{ listStyle: "none", marginBottom: "4px", marginLeft: "-14px" }}>
//       <div
//         style={{ display: "flex", alignItems: "flex-start", gap: "6px", cursor: "pointer", userSelect: "none" }}
//         onClick={(e) => { e.stopPropagation(); setOpen(!open); }}
//       >
//         <span
//           style={{
//             fontSize: "10px", display: "inline-flex", alignItems: "center", justifyContent: "center",
//             width: "12px", height: "12px", transform: open ? "rotate(90deg)" : "rotate(0deg)",
//             transition: "transform 0.15s ease", marginTop: "5px", opacity: 0.7,
//           }}
//         >
//           ▶
//         </span>
//         <div style={{ flex: 1 }}>{content}</div>
//       </div>
//       {open && <div style={{ paddingLeft: "14px", marginTop: "2px" }}>{sublists}</div>}
//     </li>
//   );
// }

// Celda de tabla: convierte [etiquetas] y !fechas! en badges usando los colores guardados del usuario
function TableCell({ children }) {
    const colorMap = useTagColors();
    return (
        <td style={{ border: "1px solid var(--border)", padding: "6px 8px", verticalAlign: "middle" }}>
            {Children.map(children, (child) =>
                typeof child === "string" ? renderBadges(child, colorMap) : child
            )}
        </td>
    );
}

// Marcadores universales {{tag:nombre}} y {{expired:fecha}} (ver utils/remarkChatTokens.js)
function TagToken({ children }) {
    const name = Children.toArray(children).join("").trim();
    return <TagBadge name={name} size="sm" showIcon={false} />;
}

function ExpiredDateToken({ children }) {
    return (
        <span style={{ color: "#dc2626", fontWeight: "700", whiteSpace: "nowrap" }}>
            {children}
        </span>
    );
}

const markdownComponents = {
    "tag-badge": TagToken,
    "expired-date": ExpiredDateToken,

    // Párrafos
    p: ({ children }) => <p style={{ margin: "0 0 8px 0" }}>{children}</p>,

    // Listas
    ul: ({ children }) => <ul style={{ margin: "4px 0 8px 0", paddingLeft: "20px" }}>{children}</ul>,
    ol: ({ children }) => <ol style={{ margin: "4px 0 8px 0", paddingLeft: "20px" }}>{children}</ol>,
    li: ({ children }) => <li style={{ marginBottom: "2px" }}>{children}</li>,
    //li: CollapsibleLi,

    // Código: en línea con fondo propio; los bloques los estiliza <pre>.
    // Se detecta por `language-` o saltos de línea (react-markdown v9 ya no pasa `inline`).
    code: ({ className, children }) => {
        const isBlock = /language-/.test(className || "") || String(children).includes("\n");
        return isBlock ? (
            <code>{children}</code>
        ) : (
            <code
                style={{
                    background: "rgba(0,0,0,0.12)",
                    borderRadius: "4px",
                    padding: "1px 5px",
                    fontSize: "13px",
                    fontFamily: "monospace",
                }}
            >
                {children}
            </code>
        );
    },
    pre: ({ children }) => (
        <pre
            style={{
                background: "rgba(0,0,0,0.15)",
                borderRadius: "6px",
                padding: "10px 12px",
                overflowX: "auto",
                fontSize: "13px",
                fontFamily: "monospace",
                margin: "6px 0",
            }}
        >
            {children}
        </pre>
    ),

    // Encabezados
    h1: ({ children }) => <h1 style={{ fontSize: "18px", fontWeight: "700", margin: "8px 0 4px" }}>{children}</h1>,
    h2: ({ children }) => <h2 style={{ fontSize: "16px", fontWeight: "700", margin: "8px 0 4px" }}>{children}</h2>,
    h3: ({ children }) => <h3 style={{ fontSize: "15px", fontWeight: "600", margin: "6px 0 4px" }}>{children}</h3>,
    h4: ({ children }) => <h4 style={{ fontSize: "14px", fontWeight: "600", margin: "6px 0 4px" }}>{children}</h4>,

    // Negrita, cursiva, separador, enlaces
    strong: ({ children }) => <strong style={{ fontWeight: "700" }}>{children}</strong>,
    em: ({ children }) => <em>{children}</em>,
    hr: () => <hr style={{ border: "none", borderTop: "1px solid var(--border)", margin: "8px 0" }} />,
    a: ({ href, children }) => (
        <a href={href} target="_blank" rel="noopener noreferrer" style={{ color: "#6366f1", textDecoration: "underline" }}>
            {children}
        </a>
    ),

    // Tablas (remark-gfm)
    table: ({ children }) => (
        <div style={{ overflowX: "auto", margin: "8px 0", maxWidth: "100%" }}>
            <table style={{ borderCollapse: "collapse", width: "100%", fontSize: "13px" }}>
                {children}
            </table>
        </div>
    ),
    th: ({ children }) => (
        <th
            style={{
                border: "1px solid var(--border)",
                padding: "6px 8px",
                background: "rgba(0,0,0,0.06)",
                fontWeight: "700",
                whiteSpace: "nowrap", // Evita que 'Estado', 'Prioridad' o 'Fecha' se dividan
            }}
        >
            {children}
        </th>
    ),
    td: TableCell,

    blockquote: ({ children }) => (
        <blockquote
            style={{
                borderLeft: "3px solid var(--border)",
                margin: "6px 0",
                paddingLeft: "12px",
                opacity: 0.8,
            }}
        >
            {children}
        </blockquote>
    ),
};

export default function MarkdownContent({ children }) {
    return (
        <ReactMarkdown remarkPlugins={[remarkGfm, remarkChatTokens]} components={markdownComponents}>
            {children || ""}
        </ReactMarkdown>
    );
}






