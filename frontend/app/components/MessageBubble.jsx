import React, { useState, Children } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";


// Función para asignar colores consistentes según el texto
const getTagStyle = (tagText) => {
  const lower = tagText.toLowerCase().trim();

  // Paleta dinámica para cualquier otra etiqueta (Garantiza que el mismo texto = mismo color)
  const palette = [
    { bg: "rgba(14, 165, 233, 0.15)", text: "#0284c7", border: "rgba(14, 165, 233, 0.4)" },  // Celeste
    { bg: "rgba(236, 72, 153, 0.15)", text: "#db2777", border: "rgba(236, 72, 153, 0.4)" },  // Rosa
    { bg: "rgba(20, 184, 166, 0.15)", text: "#0d9488", border: "rgba(20, 184, 166, 0.4)" },  // Turquesa
    { bg: "rgba(249, 115, 22, 0.15)", text: "#ea580c", border: "rgba(249, 115, 22, 0.4)" },  // Naranja Intenso
    { bg: "rgba(99, 102, 241, 0.15)", text: "#4f46e5", border: "rgba(99, 102, 241, 0.4)" },  // Índigo
    { bg: "rgba(107, 114, 128, 0.15)", text: "#4b5563", border: "rgba(107, 114, 128, 0.4)" }  // Gris
  ];

  let hash = 0;
  for (let i = 0; i < lower.length; i++) {
    hash = lower.charCodeAt(i) + ((hash << 5) - hash);
  }

  const index = Math.abs(hash) % palette.length;
  return palette[index];
};


const renderBadges = (text) => {
  if (typeof text !== "string") return text;

  // 1. Interpretar <br> o <br/> como saltos de línea reales de React
  if (text.includes("<br")) {
    const parts = text.split(/<br\s*\/?>/gi);
    return parts.reduce((acc, part, i) => {
      if (i === 0) return [renderBadges(part)];
      return [...acc, <br key={`br-${i}`} />, renderBadges(part)];
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
      const overdueText = match[1].trim();
      parts.push(
        <span
          key={match.index}
          style={{
            color: "#dc2626",
            fontWeight: "700",
            whiteSpace: "nowrap",
          }}
        >
          {overdueText}
        </span>
      );
    } else if (match[2] !== undefined) {
      // Píldoras ([texto]) -> Si la IA manda [backend, prompt], lo dividimos por comas
      const rawText = match[2].trim();
      const subTags = rawText.split(",").map((t) => t.trim()).filter(Boolean);

      subTags.forEach((tagText, subIdx) => {
        const style = getTagStyle(tagText);
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
// function CollapsibleLi({ children }) {
//   const [open, setOpen] = useState(true);

//   const childrenArray = Children.toArray(children);

//   const sublists = [];
//   const content = [];

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

//   if (sublists.length === 0) {
//     return <li style={{ marginBottom: "2px" }}>{children}</li>;
//   }

//   return (
//     <li style={{ listStyle: "none", marginBottom: "4px", marginLeft: "-14px" }}>
//       <div
//         style={{
//           display: "flex",
//           alignItems: "flex-start",
//           gap: "6px",
//           cursor: "pointer",
//           userSelect: "none",
//         }}
//         onClick={(e) => {
//           e.stopPropagation();
//           setOpen(!open);
//         }}
//       >
//         <span
//           style={{
//             fontSize: "10px",
//             display: "inline-flex",
//             alignItems: "center",
//             justifyContent: "center",
//             width: "12px",
//             height: "12px",
//             transform: open ? "rotate(90deg)" : "rotate(0deg)",
//             transition: "transform 0.15s ease",
//             marginTop: "5px",
//             opacity: 0.7,
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

export default function MessageBubble({ message }) {
  const isUser = message.role === "user";

  const formatDateTime = (ts) => {
    if (!ts) return "";
    try {
      const date = new Date(ts);
      if (isNaN(date.getTime())) return "";

      const now = new Date();
      const isToday =
        date.getDate() === now.getDate() &&
        date.getMonth() === now.getMonth() &&
        date.getFullYear() === now.getFullYear();

      const timeStr = date.toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      });

      if (isToday) {
        return timeStr;
      } else {
        const isSameYear = date.getFullYear() === now.getFullYear();
        const dateStr = date.toLocaleDateString("es-ES", {
          day: "numeric",
          month: "short",
          ...(isSameYear ? {} : { year: "numeric" }),
        });
        return `${dateStr}, ${timeStr}`;
      }
    } catch {
      return "";
    }
  };

  const formattedTime = formatDateTime(message.timestamp);

  return (
    <div
      style={{
        display: "flex",
        justifyContent: isUser ? "flex-end" : "flex-start",
        marginBottom: "12px",
      }}
    >
      {!isUser && (
        <div
          style={{
            width: "28px",
            height: "28px",
            borderRadius: "50%",
            background: "var(--avatar-ai-bg)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: "12px",
            color: "white",
            marginRight: "8px",
            flexShrink: 0,
            marginTop: "4px",
          }}
        >
          IA
        </div>
      )}

      <div
        style={{
          maxWidth: "70%",
          padding: "10px 14px",
          borderRadius: isUser ? "18px 18px 4px 18px" : "18px 18px 18px 4px",
          background: isUser ? "var(--bubble-user-bg)" : "var(--bubble-ai-bg)",
          color: isUser ? "var(--bubble-user-text)" : "var(--text-primary)",
          fontSize: "14px",
          lineHeight: "1.6",
          wordBreak: "break-word",
          display: "flex",
          flexDirection: "column",
        }}
      >
        <div>
          {isUser ? (
            // Mensajes del usuario: texto plano con saltos de línea
            <span style={{ whiteSpace: "pre-wrap" }}>{message.content}</span>
          ) : (
            // Mensajes del asistente: renderizado markdown completo con sublistas colapsables
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                // Párrafos sin margen extra en el primero
                p: ({ children }) => (
                  <p style={{ margin: "0 0 8px 0" }}>{children}</p>
                ),
                // Listas
                ul: ({ children }) => (
                  <ul style={{ margin: "4px 0 8px 0", paddingLeft: "20px" }}>{children}</ul>
                ),
                ol: ({ children }) => (
                  <ol style={{ margin: "4px 0 8px 0", paddingLeft: "20px" }}>{children}</ol>
                ),
                //li: CollapsibleLi,
                // Código inline
                code: ({ inline, children }) =>
                  inline ? (
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
                  ) : (
                    <code>{children}</code>
                  ),
                // Bloque de código
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
                h1: ({ children }) => (
                  <h1 style={{ fontSize: "18px", fontWeight: "700", margin: "8px 0 4px" }}>{children}</h1>
                ),
                h2: ({ children }) => (
                  <h2 style={{ fontSize: "16px", fontWeight: "700", margin: "8px 0 4px" }}>{children}</h2>
                ),
                h3: ({ children }) => (
                  <h3 style={{ fontSize: "15px", fontWeight: "600", margin: "6px 0 4px" }}>{children}</h3>
                ),
                // Negrita y cursiva
                strong: ({ children }) => (
                  <strong style={{ fontWeight: "700" }}>{children}</strong>
                ),
                em: ({ children }) => <em>{children}</em>,
                // Separador horizontal
                hr: () => (
                  <hr style={{ border: "none", borderTop: "1px solid var(--border)", margin: "8px 0" }} />
                ),
                // Tablas (remark-gfm)ç

              // Tablas (remark-gfm)
                table: ({ children }) => (
                  <div style={{ overflowX: "auto", margin: "8px 0", maxWidth: "100%" }}>
                    <table
                      style={{
                        borderCollapse: "collapse",
                        width: "100%",
                        fontSize: "13px",
                      }}
                    >
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
                td: ({ children }) => (
                  <td
                    style={{
                      border: "1px solid var(--border)",
                      padding: "6px 8px",
                      verticalAlign: "middle",
                    }}
                  >
                    {React.Children.map(children, (child) =>
                      typeof child === "string" ? renderBadges(child) : child
                    )}
                  </td>
                ),
                
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
              }}
            >
              {message.content}
            </ReactMarkdown>
          )}
        </div>

        {formattedTime && (
          <div
            style={{
              fontSize: "11px",
              opacity: 0.7,
              marginTop: "4px",
              textAlign: "right",
              userSelect: "none",
            }}
          >
            {formattedTime}
          </div>
        )}
      </div>
    </div>
  );
}
