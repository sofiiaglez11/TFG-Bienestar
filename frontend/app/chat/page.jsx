"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import ChatWindow from "../components/ChatWindow";
import ChatInput from "../components/ChatInput";
import ClockifyConfigModal from "../components/ClockifyConfigModal";
import StudentDashboard from "../components/StudentDashboard";

const BACKEND_URL = "http://localhost:8000";

export default function ChatPage() {
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [showClockifyModal, setShowClockifyModal] = useState(false);
  const [showDashboard, setShowDashboard] = useState(false);
  const [clockifyConnected, setClockifyConnected] = useState(false);
  const [activeTab, setActiveTab] = useState("chat");
  const [showProfileMenu, setShowProfileMenu] = useState(false);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [userName, setUserName] = useState("Estudiante");
  const [userEmail, setUserEmail] = useState("Cargando...");

  const router = useRouter();

  // 1. Cargar historial o lanzar saludo proactivo al iniciar
  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      router.push("/login");
      return;
    }

    // Obtener información del usuario
    const fetchUserInfo = async () => {
      const cachedName = localStorage.getItem("userName");
      const cachedEmail = localStorage.getItem("userEmail");
      if (cachedName) setUserName(cachedName);
      if (cachedEmail) setUserEmail(cachedEmail);

      try {
        const res = await fetch(`${BACKEND_URL}/api/user/me`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) {
          const data = await res.json();
          setUserName(data.name || "Estudiante");
          setUserEmail(data.email || "");
          localStorage.setItem("userName", data.name || "Estudiante");
          localStorage.setItem("userEmail", data.email || "");
        }
      } catch (err) {
        console.error("Error al cargar información del usuario:", err);
      }
    };

    fetchUserInfo();

    // Comprobar si el usuario tiene Clockify conectado
    const checkClockifyStatus = async () => {
      try {
        const res = await fetch(`${BACKEND_URL}/api/user/clockify-status`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) {
          const data = await res.json();
          setClockifyConnected(data.connected);
        }
      } catch (err) {
        console.error("Error al comprobar estado de Clockify:", err);
      }
    };

    checkClockifyStatus();

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
    localStorage.removeItem("userName");
    localStorage.removeItem("userEmail");
    router.push("/login");
  };

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "row",
        height: "100vh",
        background: "var(--bg-page)",
      }}
    >
      {/* Sidebar */}
      <div
        style={{
          width: isSidebarCollapsed ? "80px" : "260px",
          borderRight: "1px solid var(--border)",
          background: "var(--bg-header)",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "20px 12px",
          boxSizing: "border-box",
          overflow: "hidden",
          transition: "all 0.3s cubic-bezier(0.4, 0, 0.2, 1)",
          whiteSpace: "nowrap",
        }}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
          {/* Logo / Title & Collapse/Expand Button */}
          <div style={{ display: "flex", alignItems: "center", justifyContent: isSidebarCollapsed ? "center" : "space-between", gap: "10px" }}>
            {!isSidebarCollapsed ? (
              <>
                <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                  <div
                    style={{
                      width: "32px",
                      height: "32px",
                      borderRadius: "50%",
                      background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
                      flexShrink: 0,
                    }}
                  />
                  <div>
                    <div style={{ fontWeight: 600, fontSize: "14px", color: "var(--text-primary)" }}>
                      Tutor de Bienestar
                    </div>
                    <div style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
                      Académico & Personal
                    </div>
                  </div>
                </div>
                <button
                  onClick={() => setIsSidebarCollapsed(true)}
                  style={{
                    background: "none",
                    border: "none",
                    color: "var(--text-secondary)",
                    cursor: "pointer",
                    fontSize: "18px",
                    padding: "6px",
                    borderRadius: "6px",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    transition: "background-color 0.2s",
                  }}
                  title="Contraer barra lateral"
                  onMouseOver={(e) => (e.currentTarget.style.backgroundColor = "var(--bg-page)")}
                  onMouseOut={(e) => (e.currentTarget.style.backgroundColor = "transparent")}
                >
                  ◀
                </button>
              </>
            ) : (
              <button
                onClick={() => setIsSidebarCollapsed(false)}
                style={{
                  background: "none",
                  border: "none",
                  color: "var(--text-secondary)",
                  cursor: "pointer",
                  fontSize: "18px",
                  padding: "6px",
                  borderRadius: "6px",
                  width: "100%",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  transition: "background-color 0.2s",
                }}
                title="Expandir barra lateral"
                onMouseOver={(e) => (e.currentTarget.style.backgroundColor = "var(--bg-page)")}
                onMouseOut={(e) => (e.currentTarget.style.backgroundColor = "transparent")}
              >
                ▶
              </button>
            )}
          </div>

          {/* Navigation Windows/Tabs */}
          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            {/* Botón Chat */}
            <button
              onClick={() => setActiveTab("chat")}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: isSidebarCollapsed ? "center" : "flex-start",
                gap: isSidebarCollapsed ? "0" : "10px",
                padding: isSidebarCollapsed ? "12px" : "10px 14px",
                borderRadius: "8px",
                border: "none",
                // Cambia el fondo según la pestaña activa
                backgroundColor: activeTab === "chat" ? "rgba(99, 102, 241, 0.15)" : "transparent",
                // Color de texto siempre fijo
                color: "var(--text-primary)",
                fontSize: "14px",
                fontWeight: activeTab === "chat" ? "600" : "500",
                cursor: "pointer",
                transition: "all 0.2s ease",
                width: "100%",
              }}
              title={isSidebarCollapsed ? "Chat" : ""}
            >
              <span style={{ fontSize: "16px" }}>💬</span>
              {!isSidebarCollapsed && <span>Chat</span>}
            </button>

            {/* Botón Estadísticas */}
            <button
              onClick={() => setActiveTab("stats")}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: isSidebarCollapsed ? "center" : "flex-start",
                gap: isSidebarCollapsed ? "0" : "10px",
                padding: isSidebarCollapsed ? "12px" : "10px 14px",
                borderRadius: "8px",
                border: "none",
                // Cambia el fondo según la pestaña activa
                backgroundColor: activeTab === "stats" ? "rgba(99, 102, 241, 0.15)" : "transparent",
                // Color de texto siempre fijo
                color: "var(--text-primary)",
                fontSize: "14px",
                fontWeight: activeTab === "stats" ? "600" : "500",
                cursor: "pointer",
                transition: "all 0.2s ease",
                width: "100%",
              }}
              title={isSidebarCollapsed ? "Estadísticas" : ""}
            >
              <span style={{ fontSize: "16px" }}>📊</span>
              {!isSidebarCollapsed && <span>Estadísticas</span>}
            </button>
          </div>
        </div>

        {/* Profile and Settings (Bottom of Sidebar) */}
        <div style={{ position: "relative", display: "flex", flexDirection: "column", alignItems: "center" }}>



          <button
            onClick={() => setShowProfileMenu(!showProfileMenu)}
            style={{
              width: "100%",
              display: "flex",
              alignItems: "center",
              justifyContent: isSidebarCollapsed ? "center" : "flex-start",
              gap: isSidebarCollapsed ? "0" : "10px",
              padding: isSidebarCollapsed ? "8px" : "10px",
              borderRadius: "8px",
              border: "1px solid var(--border)",
              backgroundColor: "var(--bg-page)",
              cursor: "pointer",
            }}
            title={isSidebarCollapsed ? "Ajustes de Perfil" : ""}
          >
            <div
              style={{
                width: "36px",
                height: "36px",
                borderRadius: "50%",
                backgroundColor: "#cbd5e1",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontWeight: "600",
                color: "#475569",
                fontSize: "14px",
                flexShrink: 0,
              }}
            >
              👤
            </div>
            {!isSidebarCollapsed && (
              <div style={{ flex: 1, textAlign: "left", overflow: "hidden" }}>
                <div
                  style={{
                    fontWeight: 600,
                    fontSize: "13px",
                    color: "var(--text-primary)",
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    textOverflow: "ellipsis", // Para que no rompa el diseño si el nombre es largo
                  }}
                >
                  {userName}
                </div>
                <div
                  style={{
                    fontSize: "11px",
                    color: "var(--text-secondary)",
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    textOverflow: "ellipsis", // Para que no rompa el diseño si el email es largo
                  }}
                >
                  {userEmail}
                </div>
              </div>
            )}
          </button>

          {/* Profile Dropdown Menu */}
          {showProfileMenu && (
            <>
              {/* Overlay backdrop to close menu when clicking outside */}
              <div
                onClick={() => setShowProfileMenu(false)}
                style={{
                  position: "fixed",
                  top: 0,
                  left: 0,
                  right: 0,
                  bottom: 0,
                  zIndex: 998,
                }}
              />
              <div
                style={{
                  position: "fixed",
                  bottom: "84px",
                  left: "12px",
                  width: "236px",
                  backgroundColor: "var(--bg-header)",
                  border: "1px solid var(--border)",
                  borderRadius: "8px",
                  boxShadow: "0 -4px 12px rgba(0,0,0,0.15)",
                  zIndex: 999,
                  overflow: "hidden",
                  display: "flex",
                  flexDirection: "column",
                }}
              >
                {clockifyConnected ? (
                  <button
                    onClick={() => {
                      setShowProfileMenu(false);
                      setShowClockifyModal(true);
                    }}
                    style={{
                      padding: "10px 14px",
                      border: "none",
                      background: "none",
                      color: "var(--text-primary)",
                      fontSize: "13px",
                      cursor: "pointer",
                      textAlign: "left",
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                      width: "100%"
                    }}
                    onMouseOver={(e) => (e.currentTarget.style.backgroundColor = "var(--bg-page)")}
                    onMouseOut={(e) => (e.currentTarget.style.backgroundColor = "transparent")}
                  >
                    <span style={{ color: "#22c55e", fontSize: "10px" }}>●</span> Clockify Conectado
                  </button>
                ) : (
                  <button
                    onClick={() => {
                      setShowProfileMenu(false);
                      setShowClockifyModal(true);
                    }}
                    style={{
                      padding: "10px 14px",
                      border: "none",
                      background: "none",
                      color: "var(--text-primary)",
                      fontSize: "13px",
                      cursor: "pointer",
                      textAlign: "left",
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                      width: "100%"
                    }}
                    onMouseOver={(e) => (e.currentTarget.style.backgroundColor = "var(--bg-page)")}
                    onMouseOut={(e) => (e.currentTarget.style.backgroundColor = "transparent")}
                  >
                    <span style={{ color: "#ef4444", fontSize: "10px" }}>●</span> Configurar Clockify
                  </button>
                )}
                <button
                  onClick={() => {
                    setShowProfileMenu(false);
                    handleLogout();
                  }}
                  style={{
                    padding: "10px 14px",
                    border: "none",
                    borderTop: "1px solid var(--border)",
                    background: "none",
                    color: "#ef4444",
                    fontSize: "13px",
                    cursor: "pointer",
                    textAlign: "left",
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                  }}
                  onMouseOver={(e) => (e.currentTarget.style.backgroundColor = "var(--bg-page)")}
                  onMouseOut={(e) => (e.currentTarget.style.backgroundColor = "transparent")}
                >
                  🚪 Cerrar sesión
                </button>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Main Area */}
      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          height: "100vh",
          position: "relative",
          overflow: "hidden",
        }}
      >
        {activeTab === "chat" ? (
          <>
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
          </>
        ) : (
          <div style={{ flex: 1, padding: "24px", overflow: "hidden" }}>
            <StudentDashboard isInline={true} />
          </div>
        )}
      </div>

      {/* Modals */}
      <ClockifyConfigModal
        isOpen={showClockifyModal}
        onClose={() => {
          setShowClockifyModal(false);
          // Refrescar estado de conexión al cerrar el modal
          const token = localStorage.getItem("token");
          if (token) {
            fetch(`${BACKEND_URL}/api/user/clockify-status`, {
              headers: { Authorization: `Bearer ${token}` },
            })
              .then((r) => r.json())
              .then((d) => setClockifyConnected(d.connected))
              .catch(() => { });
          }
        }}
      />
    </div>
  );
}

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
