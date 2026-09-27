"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import ChatWindow from "../components/ChatWindow";
import ChatInput from "../components/ChatInput";
import SettingsModal from "../components/SettingsModal";
import AnalyticsDashboard from "../components/AnalyticsDashboard";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

export default function ChatPage() {
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [error, setError] = useState(null);

  // Estados para Modal de Configuración General
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [settingsInitialTab, setSettingsInitialTab] = useState("clockify");

  const [clockifyConnected, setClockifyConnected] = useState(false);
  const [activeTab, setActiveTab] = useState("chat");
  const [showProfileMenu, setShowProfileMenu] = useState(false);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [userName, setUserName] = useState("Estudiante");
  const [userEmail, setUserEmail] = useState("Cargando...");
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isCheckingAuth, setIsCheckingAuth] = useState(true);

  const router = useRouter();

  const handleUnauthorized = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("userName");
    localStorage.removeItem("userEmail");
    setIsAuthenticated(false);
    router.push("/login");
  };

  const triggerProactiveGreeting = async (tok, isAppend = false) => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/chat/proactive-greeting`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${tok}`,
        },
        body: JSON.stringify({ is_login: isAppend }),
      });

      if (res.ok) {
        const data = await res.json();
        const newMsg = {
          role: "assistant",
          content: data.response,
          agent_used: data.agent_used,
          timestamp: data.timestamp || new Date().toISOString(),
        };
        if (isAppend) {
          setMessages((prev) => [...prev, newMsg]);
        } else {
          setMessages([newMsg]);
        }
      }
    } catch (err) {
      console.error("Error al obtener saludo proactivo:", err);
    }
  };

  const loadChatHistory = async (tok) => {
    const tokenToUse = tok || localStorage.getItem("token");
    if (!tokenToUse) return;

    setIsLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/chat/history?limit=30&skip=0`, {
        headers: { Authorization: `Bearer ${tokenToUse}` },
      });

      if (res.status === 401) {
        handleUnauthorized();
        return;
      }

      if (!res.ok) throw new Error("Error al cargar el historial");

      const data = await res.json();

      if (data.history && data.history.length > 0) {
        setMessages(data.history);
        setHasMore(data.has_more ?? false);

        const shouldGreetOnLogin = sessionStorage.getItem("triggerLoginGreeting") === "true";
        if (shouldGreetOnLogin) {
          sessionStorage.removeItem("triggerLoginGreeting");
          triggerProactiveGreeting(tokenToUse, true);
        }
      } else {
        sessionStorage.removeItem("triggerLoginGreeting");
        triggerProactiveGreeting(tokenToUse, false);
      }
    } catch (err) {
      console.error(err);
      setError("No se pudo cargar el historial de chat.");
    } finally {
      setIsLoading(false);
    }
  };

  const checkClockifyStatus = async () => {
    const token = localStorage.getItem("token");
    if (!token) return;

    try {
      const res = await fetch(`${BACKEND_URL}/api/user/clockify-status`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.status === 401) {
        handleUnauthorized();
        return;
      }
      if (res.ok) {
        const data = await res.json();
        setClockifyConnected(data.connected);
        localStorage.setItem("clockifyConnected", data.connected.toString());
        if (data.connected) {
          loadChatHistory(token);
        }
      }
    } catch (err) {
      console.error("Error al comprobar estado de Clockify:", err);
      const cached = localStorage.getItem("clockifyConnected");
      if (cached) {
        const isConn = cached === "true";
        setClockifyConnected(isConn);
        if (isConn) loadChatHistory(token);
      }
    }
  };

  const loadMoreMessages = async () => {
    if (isLoadingMore || !hasMore) return;
    const token = localStorage.getItem("token");
    if (!token) return;

    setIsLoadingMore(true);
    try {
      const skip = messages.length;
      const res = await fetch(
        `${BACKEND_URL}/api/chat/history?limit=30&skip=${skip}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );

      if (res.status === 401) {
        handleUnauthorized();
        return;
      }

      if (res.ok) {
        const data = await res.json();
        if (data.history && data.history.length > 0) {
          setMessages((prev) => [...data.history, ...prev]);
        }
        setHasMore(data.has_more ?? false);
      }
    } catch (err) {
      console.error("Error al cargar más mensajes:", err);
    } finally {
      setIsLoadingMore(false);
    }
  };

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      router.push("/login");
      return;
    }

    setIsAuthenticated(true);
    setIsCheckingAuth(false);

    const fetchUserInfo = async () => {
      const cachedName = localStorage.getItem("userName");
      const cachedEmail = localStorage.getItem("userEmail");
      if (cachedName) setUserName(cachedName);
      if (cachedEmail) setUserEmail(cachedEmail);

      try {
        const res = await fetch(`${BACKEND_URL}/api/user/me`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.status === 401) {
          handleUnauthorized();
          return;
        }
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
    checkClockifyStatus();
  }, [router]);

  const sendMessage = async (text) => {
    const token = localStorage.getItem("token");
    if (!token) {
      router.push("/login");
      return;
    }

    const userMessage = {
      role: "user",
      content: text,
      timestamp: new Date().toISOString(),
    };
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

      const assistantMessage = {
        role: "assistant",
        content: data.response,
        agent_used: data.agent_used,
        timestamp: data.timestamp || new Date().toISOString(),
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      setError("Error al conectar con el servidor. Inténtalo de nuevo.");
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("userName");
    localStorage.removeItem("userEmail");
    setIsAuthenticated(false);
    router.push("/login");
  };

  if (isCheckingAuth || !isAuthenticated) {
    return (
      <div style={{ display: "flex", height: "100vh", alignItems: "center", justifyContent: "center", background: "var(--bg-page)", color: "var(--text-secondary)" }}>
        <p>Cargando...</p>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "row", height: "100vh", background: "var(--bg-page)" }}>
      {/* Sidebar */}
      <div
        style={{
          width: isSidebarCollapsed ? "80px" : "260px",
          borderRight: "1px solid var(--border)",
          background: "var(--bg-surface)",
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
          {/* Logo */}
          <div style={{ display: "flex", alignItems: "center", justifyContent: isSidebarCollapsed ? "center" : "space-between", gap: "10px" }}>
            {!isSidebarCollapsed ? (
              <>
                <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                  <div style={{ width: "32px", height: "32px", borderRadius: "50%", background: "linear-gradient(135deg, #6366f1, #8b5cf6)", flexShrink: 0 }} />
                  <div>
                    <div style={{ fontWeight: 600, fontSize: "14px", color: "var(--text-primary)" }}>Tutor de Bienestar</div>
                    <div style={{ fontSize: "12px", color: "var(--text-secondary)" }}>Académico & Personal</div>
                  </div>
                </div>
                <button onClick={() => setIsSidebarCollapsed(true)} style={{ background: "none", border: "none", color: "var(--text-secondary)", cursor: "pointer", fontSize: "18px", padding: "6px" }}>◀</button>
              </>
            ) : (
              <button onClick={() => setIsSidebarCollapsed(false)} style={{ background: "none", border: "none", color: "var(--text-secondary)", cursor: "pointer", fontSize: "18px", padding: "6px", width: "100%" }}>▶</button>
            )}
          </div>

          {/* Menú Superior */}
          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
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
                backgroundColor: activeTab === "chat" ? "var(--pressed-button-bg)" : "transparent",
                color: "var(--text-primary)",
                fontSize: "14px",
                fontWeight: activeTab === "chat" ? "600" : "500",
                cursor: "pointer",
                width: "100%",
              }}
            >
              {!isSidebarCollapsed && <span>Chat</span>}
            </button>

            <button
              onClick={() => clockifyConnected && setActiveTab("stats")}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: isSidebarCollapsed ? "center" : "flex-start",
                gap: isSidebarCollapsed ? "0" : "10px",
                padding: isSidebarCollapsed ? "12px" : "10px 14px",
                borderRadius: "8px",
                border: "none",
                backgroundColor: activeTab === "stats" ? "var(--pressed-button-bg)" : "transparent",
                color: clockifyConnected ? "var(--text-primary)" : "var(--text-secondary)",
                fontSize: "14px",
                fontWeight: activeTab === "stats" ? "600" : "500",
                cursor: clockifyConnected ? "pointer" : "not-allowed",
                width: "100%",
                opacity: clockifyConnected ? 1 : 0.5,
              }}
            >
              <span style={{ fontSize: "16px" }}>{clockifyConnected ? "📊" : "🔒"}</span>
              {!isSidebarCollapsed && <span>Estadísticas</span>}
            </button>
          </div>
        </div>

        {/* Perfil (Inferior) */}
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
          >
            <div style={{ width: "36px", height: "36px", borderRadius: "50%", backgroundColor: "#cbd5e1", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: "600", color: "#475569", fontSize: "14px", flexShrink: 0 }}>👤</div>
            {!isSidebarCollapsed && (
              <div style={{ flex: 1, textAlign: "left", overflow: "hidden" }}>
                <div style={{ fontWeight: 600, fontSize: "13px", color: "var(--text-primary)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{userName}</div>
                <div style={{ fontSize: "11px", color: "var(--text-secondary)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{userEmail}</div>
              </div>
            )}
          </button>

          {/* Menú Desplegable de Perfil */}
          {showProfileMenu && (
            <>
              <div onClick={() => setShowProfileMenu(false)} style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0, zIndex: 998 }} />
              <div
                style={{
                  position: "fixed",
                  bottom: "84px",
                  left: "12px",
                  width: "236px",
                  backgroundColor: "var(--bg-surface)",
                  border: "1px solid var(--border)",
                  borderRadius: "8px",
                  boxShadow: "0 -4px 12px rgba(0,0,0,0.15)",
                  zIndex: 999,
                  overflow: "hidden",
                  display: "flex",
                  flexDirection: "column",
                }}
              >
                <button
                  onClick={() => {
                    setShowProfileMenu(false);
                    setSettingsInitialTab("clockify");
                    setShowSettingsModal(true);
                  }}
                  style={{
                    padding: "10px 14px",
                    border: "none",
                    background: "none",
                    color: "var(--text-primary)",
                    fontSize: "13px",
                    cursor: "pointer",
                    textAlign: "left",
                    width: "100%"
                  }}
                  onMouseOver={(e) => (e.currentTarget.style.backgroundColor = "var(--bg-page)")}
                  onMouseOut={(e) => (e.currentTarget.style.backgroundColor = "transparent")}
                >
                  ⚙️ Configuración general
                </button>

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

      {/* ÁREA PRINCIPAL */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", height: "100vh", position: "relative", overflow: "hidden" }}>
        <div style={{ flex: 1, display: activeTab === "chat" ? "flex" : "none", flexDirection: "column", height: "100%", position: "relative", overflow: "hidden" }}>
          {!clockifyConnected ? (
            <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", padding: "20px" }}>
              <div style={{ maxWidth: "480px", width: "100%", padding: "32px", borderRadius: "20px", background: "var(--bg-surface)", border: "1px solid var(--border)", textAlign: "center", display: "flex", flexDirection: "column", alignItems: "center", gap: "18px" }}>
                <div style={{ width: "56px", height: "56px", borderRadius: "16px", background: "linear-gradient(135deg, #6366f1, #8b5cf6)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "28px" }}>🎓</div>
                <div>
                  <h2 style={{ margin: "0 0 6px 0", fontSize: "20px", color: "var(--text-primary)" }}>¡Bienvenido/a, {userName}!</h2>
                  <p style={{ margin: 0, fontSize: "14px", color: "var(--text-secondary)", lineHeight: "1.5" }}>Conecta tu cuenta de Clockify para comenzar.</p>
                </div>
                <button
                  onClick={() => {
                    setSettingsInitialTab("clockify");
                    setShowSettingsModal(true);
                  }}
                  style={{ width: "100%", padding: "12px 20px", borderRadius: "10px", border: "none", background: "linear-gradient(135deg, #6366f1, #8b5cf6)", color: "#ffffff", fontWeight: "600", fontSize: "14px", cursor: "pointer" }}
                >
                  Vincular Clockify
                </button>
              </div>
            </div>
          ) : (
            <>
              <ChatWindow messages={messages} isLoading={isLoading} hasMore={hasMore} isLoadingMore={isLoadingMore} onLoadMore={loadMoreMessages} />
              {error && <div style={{ margin: "0 16px 8px", padding: "10px 14px", background: "#fef2f2", border: "1px solid #fecaca", borderRadius: "8px", color: "#dc2626", fontSize: "13px" }}>{error}</div>}
              <ChatInput onSend={sendMessage} isLoading={isLoading} />
            </>
          )}
        </div>

        <div style={{ flex: 1, display: activeTab === "stats" ? "flex" : "none", flexDirection: "column", height: "100%", padding: "24px", overflow: "hidden" }}>
          <AnalyticsDashboard isInline={true} isActive={activeTab === "stats"} />
        </div>
      </div>

      {/* Modal Unificado */}
      <SettingsModal
        isOpen={showSettingsModal}
        initialTab={settingsInitialTab}
        onClose={() => {
          setShowSettingsModal(false);
          checkClockifyStatus();
        }}
        onSuccess={() => checkClockifyStatus()}
      />
    </div>
  );
}