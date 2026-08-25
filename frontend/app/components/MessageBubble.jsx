import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

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
            // Mensajes del asistente: renderizado markdown completo
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
                li: ({ children }) => (
                  <li style={{ marginBottom: "2px" }}>{children}</li>
                ),
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
                // Negrita y cursiva (heredan del padre, solo aseguramos el peso)
                strong: ({ children }) => (
                  <strong style={{ fontWeight: "700" }}>{children}</strong>
                ),
                em: ({ children }) => <em>{children}</em>,
                // Separador horizontal
                hr: () => (
                  <hr style={{ border: "none", borderTop: "1px solid var(--border)", margin: "8px 0" }} />
                ),
                // Tablas (remark-gfm)
                table: ({ children }) => (
                  <table
                    style={{
                      borderCollapse: "collapse",
                      width: "100%",
                      margin: "6px 0",
                      fontSize: "13px",
                    }}
                  >
                    {children}
                  </table>
                ),
                th: ({ children }) => (
                  <th
                    style={{
                      border: "1px solid var(--border)",
                      padding: "4px 8px",
                      background: "rgba(0,0,0,0.1)",
                      textAlign: "left",
                    }}
                  >
                    {children}
                  </th>
                ),
                td: ({ children }) => (
                  <td style={{ border: "1px solid var(--border)", padding: "4px 8px" }}>
                    {children}
                  </td>
                ),
                // Blockquote
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
