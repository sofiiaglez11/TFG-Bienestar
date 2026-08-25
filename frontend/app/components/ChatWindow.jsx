import { useEffect, useRef, useLayoutEffect } from "react";
import MessageBubble from "./MessageBubble";

export default function ChatWindow({
  messages,
  isLoading,
  hasMore,
  isLoadingMore,
  onLoadMore,
}) {
  const containerRef = useRef(null);
  const bottomRef = useRef(null);
  const prevMessagesLengthRef = useRef(messages.length);
  const prevScrollHeightRef = useRef(0);
  const isPrependingRef = useRef(false);

  // Para detectar el scroll cerca del top (y cargar mensajes más antiguos)
  const handleScroll = () => {
    const container = containerRef.current;
    if (!container) return;

    if (container.scrollTop < 50 && hasMore && !isLoadingMore && onLoadMore) {
      prevScrollHeightRef.current = container.scrollHeight;
      isPrependingRef.current = true;
      onLoadMore();
    }
  };

  useLayoutEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const prevLen = prevMessagesLengthRef.current;
    const currLen = messages.length;

    if (isPrependingRef.current && currLen > prevLen) {
      // Para mantener la posición del scroll tras cargar los mensajes antiguos
      const heightDifference = container.scrollHeight - prevScrollHeightRef.current;
      container.scrollTop = heightDifference;
      isPrependingRef.current = false;
    } else if (prevLen === 0 || (!isPrependingRef.current && currLen > prevLen)) {
      // Auto-scroll al final al cargar por primera vez o al añadir un nuevo mensaje
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }

    prevMessagesLengthRef.current = currLen;
  }, [messages, isLoading]);

  return (
    <div
      ref={containerRef}
      onScroll={handleScroll}
      style={{
        flex: 1,
        overflowY: "auto",
        padding: "24px 16px",
        display: "flex",
        flexDirection: "column",
      }}
    >
      {/* Indicador de carga de mensajes antiguos */}
      {isLoadingMore && (
        <div
          style={{
            textAlign: "center",
            padding: "8px",
            fontSize: "12px",
            color: "var(--text-secondary)",
          }}
        >
          Cargando mensajes anteriores...
        </div>
      )}

      {messages.length === 0 && !isLoading && (
        <div
          style={{
            margin: "auto",
            textAlign: "center",
            color: "var(--text-secondary)",
          }}
        >
          <div style={{ fontSize: "40px", marginBottom: "12px" }}>💬</div>
          <p style={{ fontSize: "15px" }}>
            Escríbeme algo para empezar. Puedo ayudarte a gestionar tu tiempo de estudio con Clockify.
          </p>
        </div>
      )}

      {messages.map((msg, index) => (
        <MessageBubble key={msg._id || index} message={msg} />
      ))}

      {isLoading && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "6px",
            padding: "4px 0",
          }}
        >
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
              flexShrink: 0,
            }}
          >
            IA
          </div>
          <div
            style={{
              padding: "10px 14px",
              borderRadius: "18px 18px 18px 4px",
              background: "var(--bg-input)",
              display: "flex",
              gap: "4px",
              alignItems: "center",
            }}
          >
            {[0, 1, 2].map((i) => (
              <span
                key={i}
                style={{
                  width: "6px",
                  height: "6px",
                  borderRadius: "50%",
                  background: "var(--text-secondary)",
                  animation: "bounce 1.2s infinite",
                  animationDelay: `${i * 0.2}s`,
                  display: "inline-block",
                }}
              />
            ))}
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}
