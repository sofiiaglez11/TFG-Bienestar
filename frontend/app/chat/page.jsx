"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import ChatWindow from "../components/ChatWindow";
import ChatInput from "../components/ChatInput";

const BACKEND_URL = "http://localhost:8000";

export default function ChatPage() {
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const router = useRouter();

  // 1. Cargar historial o lanzar saludo proactivo al iniciar
  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      router.push("/login");
      return;
    }

    const loadChatHistory = async () => {
      setIsLoading(true);
      try {
        // Pedimos los mensajes previos del usuario a la BD
        const res = await fetch(`${BACKEND_URL}/api/chat/history`, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (res.status === 401) {
          // Token caducado o inválido
          localStorage.removeItem("token");
          router.push("/login");
          return;
        }

        if (!res.ok) throw new Error("Error al cargar el historial");

        const data = await res.json();

        // Si el usuario ya tiene conversación, la pintamos
        if (data.history && data.history.length > 0) {
          setMessages(data.history);
        } else {
          // Si la conversación está vacía, solicitamos un saludo proactivo al Agente de Bienestar
          triggerProactiveGreeting(token);
        }
      } catch (err) {
        console.error(err);
        setError("No se pudo cargar el historial de chat.");
      } finally {
        setIsLoading(false);
      }
    };

    loadChatHistory();
  }, [router]);

  // 2. Función para disparar el saludo proactivo inicial
  const triggerProactiveGreeting = async (token) => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/chat/proactive-greeting`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (res.ok) {
        const data = await res.json();
        setMessages([
          {
            role: "assistant",
            content: data.response,
            agent_used: data.agent_used,
          },
        ]);
      }
    } catch (err) {
      console.error("Error al obtener saludo proactivo:", err);
    }
  };

  // 3. Enviar mensaje al chatbot multiagente
  const sendMessage = async (text) => {
    const token = localStorage.getItem("token");
    if (!token) {
      router.push("/login");
      return;
    }

    // Añadimos inmediatamente el mensaje del usuario a la pantalla
    const userMessage = { role: "user", content: text };
    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);
    setError(null);

    try {
      const res = await fetch(`${BACKEND_URL}/api/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ message: text }),
      });

      if (!res.ok) {
        throw new Error(`Error del servidor: ${res.status}`);
      }

      const data = await res.json();

      // Guardamos la respuesta del agente junto con su dominio
      const assistantMessage = {
        role: "assistant",
        content: data.response,
        agent_used: data.agent_used, // ACADEMICO, BIENESTAR o GENERAL
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      setError("Error al conectar con el servidor. Inténtalo de nuevo.");
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  // 4. Reiniciar la conversación
  const handleResetChat = async () => {
    const token = localStorage.getItem("token");
    if (!token) return;

    if (!confirm("¿Seguro que quieres borrar la conversación actual?")) return;

    try {
      await fetch(`${BACKEND_URL}/api/chat/reset`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      setMessages([]);
      // Tras borrar, pedimos un nuevo saludo proactivo
      triggerProactiveGreeting(token);
    } catch (err) {
      console.error("Error al reiniciar chat:", err);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("token");
    router.push("/login");
  };

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100vh",
        background: "var(--bg-page)",
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: "14px 20px",
          borderBottom: "1px solid var(--border)",
          background: "var(--bg-header)",
          display: "flex",
          alignItems: "center",
          gap: "10px",
        }}
      >
        <div
          style={{
            width: "32px",
            height: "32px",
            borderRadius: "50%",
            background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
          }}
        />
        <div>
          <div
            style={{
              fontWeight: 600,
              fontSize: "14px",
              color: "var(--text-primary)",
            }}
          >
            Tutor de Bienestar & Académico
          </div>
          <div style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
            Sistema Multiagente Inteligente
          </div>
        </div>

        {/* Acciones del Header */}
        <div style={{ marginLeft: "auto", display: "flex", gap: "8px" }}>
          {/* <button
            onClick={handleResetChat}
            style={{
              padding: "6px 12px",
              background: "transparent",
              border: "1px solid var(--border)",
              borderRadius: "6px",
              color: "var(--text-secondary)",
              fontSize: "13px",
              cursor: "pointer",
            }}0
          >
            Vaciar chat
          </button> */}

          <button
            onClick={handleLogout}
            style={{
              padding: "6px 12px",
              background: "transparent",
              border: "1px solid var(--border)",
              borderRadius: "6px",
              color: "var(--text-secondary)",
              fontSize: "13px",
              cursor: "pointer",
            }}
          >
            Cerrar sesión
          </button>
        </div>
      </div>

      {/* Message Area */}
      <ChatWindow messages={messages} isLoading={isLoading} />

      {/* Error Banner */}
      {error && (
        <div
          style={{
            margin: "0 16px 8px",
            padding: "10px 14px",
            background: "#fef2f2",
            border: "1px solid #fecaca",
            borderRadius: "8px",
            color: "#dc2626",
            fontSize: "13px",
          }}
        >
          {error}
        </div>
      )}

      {/* Input */}
      <ChatInput onSend={sendMessage} isLoading={isLoading} />
    </div>
  );
}


// "use client";

// import { useState, useEffect } from "react";
// import { useRouter } from "next/navigation";
// import ChatWindow from "../components/ChatWindow";
// import ChatInput from "../components/ChatInput";

// const BACKEND_URL = "http://localhost:8000";

// // TODO: añadir apartado de configuración, autodetectar modo oscuro/ modo diurno para intercambiar colores

// export default function ChatPage() {
//   const [messages, setMessages] = useState([]);
//   const [isLoading, setIsLoading] = useState(false);
//   const [error, setError] = useState(null);

//   const router = useRouter();

//   // si no se ha iniciado sesión (no hay token), redirige al usuario a la página de inicio de sesión
//   useEffect(() => {
//     const token = localStorage.getItem("token"); // obtener el token del localStorage
//     if (!token) {
//       router.push("/login"); // redirigir a la página de inicio de sesión
//     }
//   }, [router]); // si cambia el router, se ejecuta de nuevo

//   const sendMessage = async (text) => {

//     const token = localStorage.getItem("token"); // obtener el token del localStorage
//     if (!token) {
//       router.push("/login"); // redirigir a la página de inicio de sesión
//       return;
//     }



//     // Agregar el mensaje del usuario al historial de chat
//     const userMessage = { role: "user", content: text };
//     setMessages((prev) => [...prev, userMessage]);
//     setIsLoading(true);
//     setError(null);

//     try {
//       const res = await fetch(`${BACKEND_URL}/api/chat`, {
//         method: "POST",
//         headers: {
//           "Content-Type": "application/json",
//           "Authorization": `Bearer ${token}`
//         },
//         body: JSON.stringify({ message: text }),
//       });

//       if (!res.ok) {
//         throw new Error(`Error del servidor: ${res.status}`);
//       }

//       const data = await res.json();

//       // Add the assistant's response to the chat history
//       const assistantMessage = { role: "assistant", content: data.response };
//       setMessages((prev) => [...prev, assistantMessage]);
//     } catch (err) {
//       setError("eRROR EN EL SERVIDOR");
//       console.error(err);
//     } finally {
//       setIsLoading(false);
//     }
//   };

//   const handleLogout = () => {
//     localStorage.removeItem("token");
//     router.push("/login");
//   };

//   return (
//     <div
//       style={{
//         display: "flex",
//         flexDirection: "column",
//         height: "100vh",
//         background: "var(--bg-page)",
//       }}
//     >
//       {/* Header */}
//       <div
//         style={{
//           padding: "14px 20px",
//           borderBottom: "1px solid var(--border)",
//           background: "var(--bg-header)",
//           display: "flex",
//           alignItems: "center",
//           gap: "10px",
//         }}
//       >
//         <div
//           style={{
//             width: "32px",
//             height: "32px",
//             borderRadius: "50%",
//             background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
//           }}
//         />
//         <div>
//           <div style={{ fontWeight: 600, fontSize: "14px", color: "var(--text-primary)" }}>
//             Asistente de bienestar
//           </div>
//           <div style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
//             Conectado a Clockify
//           </div>
//         </div>

//         {/* Botón de cerrar sesión */}
//         <button
//           onClick={handleLogout}
//           style={{
//             marginLeft: "auto",
//             padding: "6px 12px",
//             background: "transparent",
//             border: "1px solid var(--border)",
//             borderRadius: "6px",
//             color: "var(--text-secondary)",
//             fontSize: "13px",
//             cursor: "pointer",
//             transition: "all 0.2s",
//           }}
//           onMouseOver={(e) => {
//             e.currentTarget.style.color = "var(--text-primary)";
//             e.currentTarget.style.borderColor = "var(--text-primary)";
//           }}
//           onMouseOut={(e) => {
//             e.currentTarget.style.color = "var(--text-secondary)";
//             e.currentTarget.style.borderColor = "var(--border)";
//           }}
//         >
//           Cerrar sesión
//         </button>
//       </div>

//       {/* Message Area */}
//       <ChatWindow messages={messages} isLoading={isLoading} />

//       {/* Error */}
//       {error && (
//         <div
//           style={{
//             margin: "0 16px 8px",
//             padding: "10px 14px",
//             background: "#fef2f2",
//             border: "1px solid #fecaca",
//             borderRadius: "8px",
//             color: "#dc2626",
//             fontSize: "13px",
//           }}
//         >
//           {error}
//         </div>
//       )}

//       {/* Input */}
//       <ChatInput onSend={sendMessage} isLoading={isLoading} />

//       {/* Animation of the loading dots */}
//       <style>{`
//         @keyframes bounce {
//           0%, 60%, 100% { transform: translateY(0); }
//           30% { transform: translateY(-4px); }
//         }
//       `}</style>
//     </div>
//   );
// }
