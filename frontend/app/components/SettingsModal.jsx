// "use client";

// import { useState, useEffect } from "react";
// import {
//   X,
//   Key,
//   Users,
//   Copy,
//   Check,
//   RefreshCw,
//   Trash2,
//   UserX,
//   Shield,
//   Clock
// } from "lucide-react";

// const RAW_BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
// const BACKEND_URL = RAW_BACKEND_URL.replace(/\/+$/, "");

// export default function SettingsModal({ isOpen, onClose, initialTab = "clockify", onSuccess }) {
//   const [activeTab, setActiveTab] = useState(initialTab); // "clockify" | "privacy"

//   // Estado Clockify
//   const [apiKey, setApiKey] = useState("");
//   const [clockifyStatus, setClockifyStatus] = useState(false);
//   const [clockifyLoading, setClockifyLoading] = useState(false);
//   const [clockifyMsg, setClockifyMsg] = useState(null);

//   // Estado Permisos y Compartir
//   const [myShareCode, setMyShareCode] = useState(null);
//   const [copied, setCopied] = useState(false);
//   const [followCode, setFollowCode] = useState("");
//   const [followError, setFollowError] = useState(null);
//   const [followedUsers, setFollowedUsers] = useState([]);
//   const [followers, setFollowers] = useState([]);
//   const [privacyLoading, setPrivacyLoading] = useState(false);

//   useEffect(() => {
//     if (isOpen) {
//       setActiveTab(initialTab);
//       fetchClockifyStatus();
//       loadPrivacyData();
//     }
//   }, [isOpen, initialTab]);

//   // --- MÉTODOS CLOCKIFY ---
//   const fetchClockifyStatus = async () => {
//     const token = localStorage.getItem("token");
//     if (!token) return;
//     try {
//       const res = await fetch(`${BACKEND_URL}/api/user/clockify-status`, {
//         headers: { Authorization: `Bearer ${token}` }
//       });
//       if (res.ok) {
//         const data = await res.json();
//         setClockifyStatus(data.connected);
//       }
//     } catch (err) {
//       console.error("Error consultando estado de Clockify:", err);
//     }
//   };

//   const handleSaveClockify = async (e) => {
//     e.preventDefault();
//     if (!apiKey.trim()) return;
//     setClockifyLoading(true);
//     setClockifyMsg(null);
//     const token = localStorage.getItem("token");
//     try {
//       const res = await fetch(`${BACKEND_URL}/api/user/clockify-key`, {
//         method: "POST",
//         headers: {
//           "Content-Type": "application/json",
//           Authorization: `Bearer ${token}`
//         },
//         body: JSON.stringify({ api_key: apiKey.trim() })
//       });
//       if (res.ok) {
//         setClockifyMsg({ type: "success", text: "¡Clockify conectado correctamente!" });
//         setApiKey("");
//         setClockifyStatus(true);
//         if (onSuccess) onSuccess();
//       } else {
//         const err = await res.json().catch(() => ({}));
//         setClockifyMsg({ type: "error", text: err.detail || "Error al conectar Clockify." });
//       }
//     } catch (err) {
//       setClockifyMsg({ type: "error", text: "Error de conexión con el servidor." });
//     } finally {
//       setClockifyLoading(false);
//     }
//   };

//   // --- MÉTODOS PRIVACIDAD Y PERMISOS ---
//   const loadPrivacyData = async () => {
//     const token = localStorage.getItem("token");
//     if (!token) return;
//     setPrivacyLoading(true);
//     try {
//       const [codeRes, followedRes, followersRes] = await Promise.all([
//         fetch(`${BACKEND_URL}/api/user/share-code`, { headers: { Authorization: `Bearer ${token}` } }),
//         fetch(`${BACKEND_URL}/api/share/followed`, { headers: { Authorization: `Bearer ${token}` } }),
//         fetch(`${BACKEND_URL}/api/share/followers`, { headers: { Authorization: `Bearer ${token}` } })
//       ]);

//       if (codeRes.ok) {
//         const codeData = await codeRes.json();
//         setMyShareCode(codeData.code);
//       }
//       if (followedRes.ok) {
//         const followedData = await followedRes.json();
//         setFollowedUsers(followedData.followed || []);
//       }
//       if (followersRes.ok) {
//         const followersData = await followersRes.json();
//         setFollowers(followersData.followers || []);
//       }
//     } catch (err) {
//       console.error("Error al cargar privacidad:", err);
//     } finally {
//       setPrivacyLoading(false);
//     }
//   };

//   const handleGenerateCode = async () => {
//     const token = localStorage.getItem("token");
//     if (!token) return;
//     try {
//       const res = await fetch(`${BACKEND_URL}/api/share/generate`, {
//         method: "POST",
//         headers: { Authorization: `Bearer ${token}` }
//       });
//       if (res.ok) {
//         const data = await res.json();
//         setMyShareCode(data.code);
//       }
//     } catch (err) {
//       console.error("Error generando código:", err);
//     }
//   };

//   const handleCopyCode = () => {
//     if (!myShareCode) return;
//     navigator.clipboard.writeText(myShareCode);
//     setCopied(true);
//     setTimeout(() => setCopied(false), 2000);
//   };

//   const handleFollowUser = async () => {
//     if (!followCode.trim()) return;
//     const token = localStorage.getItem("token");
//     if (!token) return;
//     setFollowError(null);
//     try {
//       const res = await fetch(`${BACKEND_URL}/api/share/follow`, {
//         method: "POST",
//         headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
//         body: JSON.stringify({ code: followCode.trim().toUpperCase() })
//       });
//       if (!res.ok) {
//         const err = await res.json().catch(() => ({}));
//         setFollowError(err.detail || "Código no válido o ya agregado.");
//         return;
//       }
//       await loadPrivacyData();
//       setFollowCode("");
//     } catch (err) {
//       setFollowError("Error al conectar con el servidor.");
//     }
//   };

//   const handleUnfollowUser = async (targetUserId) => {
//     const token = localStorage.getItem("token");
//     if (!token) return;
//     try {
//       const res = await fetch(`${BACKEND_URL}/api/share/followed/${targetUserId}`, {
//         method: "DELETE",
//         headers: { Authorization: `Bearer ${token}` }
//       });
//       if (res.ok) await loadPrivacyData();
//     } catch (err) {
//       console.error("Error al dejar de seguir:", err);
//     }
//   };

//   const handleRevokeFollower = async (followerUserId) => {
//     const token = localStorage.getItem("token");
//     if (!token) return;
//     try {
//       const res = await fetch(`${BACKEND_URL}/api/share/followers/${followerUserId}`, {
//         method: "DELETE",
//         headers: { Authorization: `Bearer ${token}` }
//       });
//       if (res.ok) await loadPrivacyData();
//     } catch (err) {
//       console.error("Error al revocar acceso:", err);
//     }
//   };

//   if (!isOpen) return null;

//   return (
//     <div
//       style={{
//         position: "fixed",
//         top: 0,
//         left: 0,
//         right: 0,
//         bottom: 0,
//         backgroundColor: "rgba(0,0,0,0.6)",
//         display: "flex",
//         alignItems: "center",
//         justifyContent: "center",
//         zIndex: 1100,
//         padding: "20px"
//       }}
//     >
//       <div
//         style={{
//           backgroundColor: "var(--bg-surface)",
//           border: "1px solid var(--border)",
//           borderRadius: "16px",
//           width: "100%",
//           maxWidth: "760px",
//           maxHeight: "85vh",
//           display: "flex",
//           flexDirection: "column",
//           boxShadow: "0 20px 30px rgba(0,0,0,0.25)",
//           overflow: "hidden",
//           color: "var(--text-primary)"
//         }}
//       >
//         {/* Cabecera Modal */}
//         <div
//           style={{
//             padding: "18px 24px",
//             borderBottom: "1px solid var(--border)",
//             display: "flex",
//             justifyContent: "space-between",
//             alignItems: "center"
//           }}
//         >
//           <h3 style={{ margin: 0, fontSize: "1.15rem", fontWeight: "700" }}>⚙️ Configuración General</h3>
//           <button
//             onClick={onClose}
//             style={{ background: "none", border: "none", color: "var(--text-secondary)", cursor: "pointer", padding: "4px" }}
//           >
//             <X size={20} />
//           </button>
//         </div>

//         {/* Cuerpo con Navegación Lateral */}
//         <div style={{ display: "flex", flex: 1, minHeight: "380px", overflow: "hidden" }}>
//           {/* Menú Izquierdo */}
//           <div
//             style={{
//               width: "200px",
//               borderRight: "1px solid var(--border)",
//               backgroundColor: "var(--bg-page)",
//               padding: "16px 10px",
//               display: "flex",
//               flexDirection: "column",
//               gap: "6px"
//             }}
//           >
//             <button
//               onClick={() => setActiveTab("clockify")}
//               style={{
//                 display: "flex",
//                 alignItems: "center",
//                 gap: "10px",
//                 padding: "10px 12px",
//                 borderRadius: "8px",
//                 border: "none",
//                 backgroundColor: activeTab === "clockify" ? "var(--pressed-button-bg)" : "transparent",
//                 color: "var(--text-primary)",
//                 fontWeight: activeTab === "clockify" ? "600" : "500",
//                 fontSize: "13px",
//                 cursor: "pointer",
//                 textAlign: "left"
//               }}
//             >
//               <Clock size={16} /> Clockify
//             </button>

//             <button
//               onClick={() => setActiveTab("privacy")}
//               style={{
//                 display: "flex",
//                 alignItems: "center",
//                 gap: "10px",
//                 padding: "10px 12px",
//                 borderRadius: "8px",
//                 border: "none",
//                 backgroundColor: activeTab === "privacy" ? "var(--pressed-button-bg)" : "transparent",
//                 color: "var(--text-primary)",
//                 fontWeight: activeTab === "privacy" ? "600" : "500",
//                 fontSize: "13px",
//                 cursor: "pointer",
//                 textAlign: "left"
//               }}
//             >
//               <Shield size={16} /> Permisos y Accesos
//             </button>
//           </div>

//           {/* Área de Contenido */}
//           <div style={{ flex: 1, padding: "24px", overflowY: "auto" }}>
//             {/* PESTAÑA CLOCKIFY */}
//             {activeTab === "clockify" && (
//               <div style={{ display: "flex", flexDirection: "column", gap: "18px" }}>
//                 <div>
//                   <h4 style={{ margin: "0 0 6px 0", fontSize: "15px" }}>Integración de Clockify</h4>
//                   <p style={{ margin: 0, fontSize: "13px", color: "var(--text-secondary)" }}>
//                     Conecta tu API Key de Clockify para sincronizar automáticamente el tiempo dedicado a tus asignaturas.
//                   </p>
//                 </div>

//                 <div
//                   style={{
//                     padding: "12px 16px",
//                     borderRadius: "8px",
//                     backgroundColor: clockifyStatus ? "rgba(34, 197, 94, 0.1)" : "rgba(234, 179, 8, 0.1)",
//                     border: `1px solid ${clockifyStatus ? "rgba(34, 197, 94, 0.3)" : "rgba(234, 179, 8, 0.3)"}`,
//                     fontSize: "13px",
//                     color: clockifyStatus ? "#15803d" : "#a16207",
//                     display: "flex",
//                     alignItems: "center",
//                     gap: "8px"
//                   }}
//                 >
//                   <span style={{ fontWeight: "700" }}>Estado:</span>
//                   {clockifyStatus ? "Conectado correctamente" : "No conectado"}
//                 </div>

//                 <form onSubmit={handleSaveClockify} style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
//                   <label style={{ fontSize: "12px", fontWeight: "600", color: "var(--text-secondary)" }}>
//                     API Key de Clockify
//                   </label>
//                   <div style={{ display: "flex", gap: "8px" }}>
//                     <input
//                       type="password"
//                       value={apiKey}
//                       onChange={(e) => setApiKey(e.target.value)}
//                       placeholder="Introduce tu API Key..."
//                       style={{
//                         flex: 1,
//                         padding: "8px 12px",
//                         borderRadius: "8px",
//                         border: "1px solid var(--border)",
//                         backgroundColor: "var(--bg-input)",
//                         color: "var(--text-primary)",
//                         fontSize: "13px"
//                       }}
//                     />
//                     <button
//                       type="submit"
//                       disabled={clockifyLoading || !apiKey.trim()}
//                       style={{
//                         padding: "8px 16px",
//                         borderRadius: "8px",
//                         border: "none",
//                         backgroundColor: "var(--brand)",
//                         color: "#fff",
//                         fontWeight: "600",
//                         fontSize: "13px",
//                         cursor: apiKey.trim() ? "pointer" : "not-allowed",
//                         opacity: apiKey.trim() ? 1 : 0.6
//                       }}
//                     >
//                       {clockifyLoading ? "Guardando..." : "Guardar"}
//                     </button>
//                   </div>
//                 </form>

//                 {clockifyMsg && (
//                   <p style={{ margin: 0, fontSize: "12px", color: clockifyMsg.type === "success" ? "#16a34a" : "#dc2626" }}>
//                     {clockifyMsg.text}
//                   </p>
//                 )}
//               </div>
//             )}

//             {/* PESTAÑA PERMISOS Y PRIVACIDAD */}
//             {activeTab === "privacy" && (
//               <div style={{ display: "flex", flexDirection: "column", gap: "22px" }}>
//                 {/* 1. Mi Código */}
//                 <div style={{ borderBottom: "1px solid var(--border)", paddingBottom: "16px" }}>
//                   <h4 style={{ margin: "0 0 6px 0", fontSize: "14px" }}>Tu código de compartir</h4>
//                   <p style={{ margin: "0 0 10px 0", fontSize: "12px", color: "var(--text-secondary)" }}>
//                     Comparte este código con compañeros para que puedan seguir tus estadísticas de estudio.
//                   </p>
//                   <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
//                     <code
//                       style={{
//                         padding: "6px 14px",
//                         borderRadius: "8px",
//                         backgroundColor: "var(--bg-page)",
//                         border: "1px solid var(--border)",
//                         fontSize: "16px",
//                         fontWeight: "700",
//                         letterSpacing: "2px"
//                       }}
//                     >
//                       {myShareCode || "—"}
//                     </code>
//                     <button
//                       onClick={handleCopyCode}
//                       disabled={!myShareCode}
//                       style={{
//                         padding: "6px 12px",
//                         borderRadius: "6px",
//                         border: "1px solid var(--border)",
//                         backgroundColor: "var(--bg-surface)",
//                         cursor: myShareCode ? "pointer" : "not-allowed",
//                         fontSize: "12px",
//                         display: "flex",
//                         alignItems: "center",
//                         gap: "4px"
//                       }}
//                     >
//                       {copied ? <Check size={14} color="#16a34a" /> : <Copy size={14} />}
//                       {copied ? "Copiado" : "Copiar"}
//                     </button>
//                     {!myShareCode && (
//                       <button
//                         onClick={handleGenerateCode}
//                         style={{
//                           padding: "6px 12px",
//                           borderRadius: "6px",
//                           border: "none",
//                           backgroundColor: "var(--brand)",
//                           color: "#fff",
//                           cursor: "pointer",
//                           fontSize: "12px",
//                           fontWeight: "600"
//                         }}
//                       >
//                         Generar código
//                       </button>
//                     )}
//                   </div>
//                 </div>

//                 {/* 2. Seguir a alguien */}
//                 <div style={{ borderBottom: "1px solid var(--border)", paddingBottom: "16px" }}>
//                   <h4 style={{ margin: "0 0 6px 0", fontSize: "14px" }}>Añadir compañero</h4>
//                   <div style={{ display: "flex", gap: "8px" }}>
//                     <input
//                       type="text"
//                       value={followCode}
//                       onChange={(e) => setFollowCode(e.target.value.toUpperCase())}
//                       placeholder="Código del usuario"
//                       maxLength={10}
//                       style={{
//                         padding: "6px 12px",
//                         borderRadius: "6px",
//                         border: "1px solid var(--border)",
//                         backgroundColor: "var(--bg-input)",
//                         color: "var(--text-primary)",
//                         fontSize: "13px",
//                         width: "180px"
//                       }}
//                     />
//                     <button
//                       onClick={handleFollowUser}
//                       style={{
//                         padding: "6px 14px",
//                         borderRadius: "6px",
//                         border: "none",
//                         backgroundColor: "var(--brand)",
//                         color: "#fff",
//                         cursor: "pointer",
//                         fontSize: "12px",
//                         fontWeight: "600"
//                       }}
//                     >
//                       Seguir
//                     </button>
//                   </div>
//                   {followError && <p style={{ margin: "6px 0 0", fontSize: "12px", color: "#dc2626" }}>{followError}</p>}
//                 </div>

//                 {/* 3. Listas de Permisos */}
//                 <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
//                   {/* Personas a las que sigues */}
//                   <div>
//                     <h5 style={{ margin: "0 0 8px 0", fontSize: "13px", color: "var(--text-primary)" }}>
//                       Estadísticas que ves ({followedUsers.length})
//                     </h5>
//                     {followedUsers.length === 0 ? (
//                       <p style={{ fontSize: "12px", color: "var(--text-secondary)", margin: 0 }}>No sigues a nadie.</p>
//                     ) : (
//                       <div style={{ display: "flex", flexDirection: "column", gap: "6px", maxHeight: "120px", overflowY: "auto" }}>
//                         {followedUsers.map((u, idx) => {
//                           const uId = u.user_id || u.id || u.followed_user_id;
//                           const uName = u.name || u.user_name || u.email || `Usuario ${idx + 1}`;
//                           return (
//                             <div key={uId} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "6px 10px", borderRadius: "6px", backgroundColor: "var(--bg-page)", border: "1px solid var(--border)" }}>
//                               <span style={{ fontSize: "12px" }}>{uName}</span>
//                               <button onClick={() => handleUnfollowUser(uId)} title="Dejar de seguir" style={{ background: "none", border: "none", color: "#dc2626", cursor: "pointer" }}>
//                                 <Trash2 size={13} />
//                               </button>
//                             </div>
//                           );
//                         })}
//                       </div>
//                     )}
//                   </div>

//                   {/* Personas que te siguen */}
//                   <div>
//                     <h5 style={{ margin: "0 0 8px 0", fontSize: "13px", color: "var(--text-primary)" }}>
//                       Tienen acceso a tus datos ({followers.length})
//                     </h5>
//                     {followers.length === 0 ? (
//                       <p style={{ fontSize: "12px", color: "var(--text-secondary)", margin: 0 }}>Nadie ve tus datos.</p>
//                     ) : (
//                       <div style={{ display: "flex", flexDirection: "column", gap: "6px", maxHeight: "120px", overflowY: "auto" }}>
//                         {followers.map((f, idx) => {
//                           const fId = f.user_id || f.id || f.follower_id;
//                           const fName = f.name || f.user_name || f.email || `Usuario ${idx + 1}`;
//                           return (
//                             <div key={fId} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "6px 10px", borderRadius: "6px", backgroundColor: "var(--bg-page)", border: "1px solid var(--border)" }}>
//                               <span style={{ fontSize: "12px" }}>{fName}</span>
//                               <button onClick={() => handleRevokeFollower(fId)} title="Revocar acceso" style={{ background: "none", border: "none", color: "#dc2626", cursor: "pointer" }}>
//                                 <UserX size={13} />
//                               </button>
//                             </div>
//                           );
//                         })}
//                       </div>
//                     )}
//                   </div>
//                 </div>

//               </div>
//             )}
//           </div>
//         </div>
//       </div>
//     </div>
//   );
// }

"use client";

import { useState, useEffect } from "react";
import {
  X,
  Copy,
  Check,
  Trash2,
  UserX,
  Shield,
  Clock
} from "lucide-react";

const RAW_BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
const BACKEND_URL = RAW_BACKEND_URL.replace(/\/+$/, "");

export default function SettingsModal({ isOpen, onClose, initialTab = "clockify", onSuccess }) {
  const [activeTab, setActiveTab] = useState(initialTab); // "clockify" | "privacy"

  // Estado Clockify
  const [apiKey, setApiKey] = useState("");
  const [clockifyStatus, setClockifyStatus] = useState(false);
  const [clockifyLoading, setClockifyLoading] = useState(false);
  const [clockifyMsg, setClockifyMsg] = useState(null);

  // Estado Permisos y Compartir
  const [myShareCode, setMyShareCode] = useState(null);
  const [copied, setCopied] = useState(false);
  const [followCode, setFollowCode] = useState("");
  const [followError, setFollowError] = useState(null);
  const [followedUsers, setFollowedUsers] = useState([]);
  const [followers, setFollowers] = useState([]);
  const [privacyLoading, setPrivacyLoading] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setActiveTab(initialTab);
      fetchClockifyStatus();
      loadPrivacyData();
    }
  }, [isOpen, initialTab]);

  // --- MÉTODOS CLOCKIFY ---
  const fetchClockifyStatus = async () => {
    const token = localStorage.getItem("token");
    if (!token) return;
    try {
      const res = await fetch(`${BACKEND_URL}/api/user/clockify-status`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setClockifyStatus(data.connected);
      }
    } catch (err) {
      console.error("Error consultando estado de Clockify:", err);
    }
  };

  const handleSaveClockify = async (e) => {
    e.preventDefault();
    if (!apiKey.trim()) return;
    setClockifyLoading(true);
    setClockifyMsg(null);
    const token = localStorage.getItem("token");
    try {
      const res = await fetch(`${BACKEND_URL}/api/user/clockify-key`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({ api_key: apiKey.trim() })
      });
      if (res.ok) {
        setClockifyMsg({ type: "success", text: "¡Clockify conectado correctamente!" });
        setApiKey("");
        setClockifyStatus(true);
        if (onSuccess) onSuccess();
      } else {
        const err = await res.json().catch(() => ({}));
        setClockifyMsg({ type: "error", text: err.detail || "Error al conectar Clockify." });
      }
    } catch (err) {
      setClockifyMsg({ type: "error", text: "Error de conexión con el servidor." });
    } finally {
      setClockifyLoading(false);
    }
  };

  // --- MÉTODOS PRIVACIDAD Y PERMISOS ---
  const loadPrivacyData = async () => {
    const token = localStorage.getItem("token");
    if (!token) return;
    setPrivacyLoading(true);
    try {
      const [codeRes, followedRes, followersRes] = await Promise.all([
        fetch(`${BACKEND_URL}/api/user/share-code`, { headers: { Authorization: `Bearer ${token}` } }),
        fetch(`${BACKEND_URL}/api/share/followed`, { headers: { Authorization: `Bearer ${token}` } }),
        fetch(`${BACKEND_URL}/api/share/followers`, { headers: { Authorization: `Bearer ${token}` } })
      ]);

      if (codeRes.ok) {
        const codeData = await codeRes.json();
        setMyShareCode(codeData.code);
      }
      if (followedRes.ok) {
        const followedData = await followedRes.json();
        setFollowedUsers(followedData.followed || []);
      }
      if (followersRes.ok) {
        const followersData = await followersRes.json();
        setFollowers(followersData.followers || []);
      }
    } catch (err) {
      console.error("Error al cargar privacidad:", err);
    } finally {
      setPrivacyLoading(false);
    }
  };

  const handleGenerateCode = async () => {
    const token = localStorage.getItem("token");
    if (!token) return;
    try {
      const res = await fetch(`${BACKEND_URL}/api/share/generate`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setMyShareCode(data.code);
      }
    } catch (err) {
      console.error("Error generando código:", err);
    }
  };

  const handleCopyCode = () => {
    if (!myShareCode) return;
    navigator.clipboard.writeText(myShareCode);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleFollowUser = async () => {
    if (!followCode.trim()) return;
    const token = localStorage.getItem("token");
    if (!token) return;
    setFollowError(null);
    try {
      const res = await fetch(`${BACKEND_URL}/api/share/follow`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ code: followCode.trim().toUpperCase() })
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        setFollowError(err.detail || "Código no válido o ya agregado.");
        return;
      }
      await loadPrivacyData();
      setFollowCode("");
    } catch (err) {
      setFollowError("Error al conectar con el servidor.");
    }
  };

  const handleUnfollowUser = async (targetUserId, targetUserName) => {
    if (!targetUserId) {
      console.error("ID de usuario no válido para dejar de seguir:", targetUserId);
      return;
    }
    const displayName = targetUserName ? `"${targetUserName}"` : "este usuario";
    if (!window.confirm(`¿Estás seguro de que deseas dejar de seguir a ${displayName}?`)) {
      return;
    }
    const token = localStorage.getItem("token");
    if (!token) return;

    try {
      const res = await fetch(`${BACKEND_URL}/api/share/followed/${targetUserId}`, {
        method: "DELETE",
        headers: { 
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}` 
        }
      });

      if (res.ok) {
        // Actualización optimista del estado
        setFollowedUsers((prev) =>
          prev.filter((u) => {
            const id = u.followed_user_id || u.target_user_id || u.user_id || u.id || u._id;
            return id !== targetUserId;
          })
        );
        await loadPrivacyData();
      } else {
        const errData = await res.json().catch(() => ({}));
        console.error(`Error al dejar de seguir [HTTP ${res.status}]:`, errData);
      }
    } catch (err) {
      console.error("Error de conexión al dejar de seguir:", err);
    }
  };

  const handleRevokeFollower = async (followerUserId, followerUserName) => {
    if (!followerUserId) return;
    const displayName = followerUserName ? `"${followerUserName}"` : "este usuario";
    if (!window.confirm(`¿Estás seguro de que deseas quitarle el acceso a tus estadísticas a ${displayName}?`)) {
      return;
    }
    const token = localStorage.getItem("token");
    if (!token) return;
    try {
      const res = await fetch(`${BACKEND_URL}/api/share/followers/${followerUserId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        setFollowers((prev) => prev.filter((f) => {
          const id = f.follower_id || f.user_id || f.id || f._id;
          return id !== followerUserId;
        }));
        await loadPrivacyData();
      }
    } catch (err) {
      console.error("Error al revocar acceso:", err);
    }
  };

  if (!isOpen) return null;

  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: "rgba(0,0,0,0.6)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 1100,
        padding: "20px"
      }}
    >
      <div
        style={{
          backgroundColor: "var(--bg-surface)",
          border: "1px solid var(--border)",
          borderRadius: "16px",
          width: "100%",
          maxWidth: "760px",
          maxHeight: "85vh",
          display: "flex",
          flexDirection: "column",
          boxShadow: "0 20px 30px rgba(0,0,0,0.25)",
          overflow: "hidden",
          color: "var(--text-primary)"
        }}
      >
        {/* Cabecera Modal */}
        <div
          style={{
            padding: "18px 24px",
            borderBottom: "1px solid var(--border)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center"
          }}
        >
          <h3 style={{ margin: 0, fontSize: "1.15rem", fontWeight: "700" }}>⚙️ Configuración General</h3>
          <button
            onClick={onClose}
            style={{ background: "none", border: "none", color: "var(--text-secondary)", cursor: "pointer", padding: "4px" }}
          >
            <X size={20} />
          </button>
        </div>

        {/* Cuerpo con Navegación Lateral */}
        <div style={{ display: "flex", flex: 1, minHeight: "380px", overflow: "hidden" }}>
          {/* Menú Izquierdo */}
          <div
            style={{
              width: "200px",
              borderRight: "1px solid var(--border)",
              backgroundColor: "var(--bg-page)",
              padding: "16px 10px",
              display: "flex",
              flexDirection: "column",
              gap: "6px"
            }}
          >
            <button
              onClick={() => setActiveTab("clockify")}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "10px",
                padding: "10px 12px",
                borderRadius: "8px",
                border: "none",
                backgroundColor: activeTab === "clockify" ? "var(--pressed-button-bg)" : "transparent",
                color: "var(--text-primary)",
                fontWeight: activeTab === "clockify" ? "600" : "500",
                fontSize: "13px",
                cursor: "pointer",
                textAlign: "left"
              }}
            >
              <Clock size={16} /> Clockify
            </button>

            <button
              onClick={() => setActiveTab("privacy")}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "10px",
                padding: "10px 12px",
                borderRadius: "8px",
                border: "none",
                backgroundColor: activeTab === "privacy" ? "var(--pressed-button-bg)" : "transparent",
                color: "var(--text-primary)",
                fontWeight: activeTab === "privacy" ? "600" : "500",
                fontSize: "13px",
                cursor: "pointer",
                textAlign: "left"
              }}
            >
              <Shield size={16} /> Permisos y Accesos
            </button>
          </div>

          {/* Área de Contenido */}
          <div style={{ flex: 1, padding: "24px", overflowY: "auto" }}>
            {/* PESTAÑA CLOCKIFY */}
            {activeTab === "clockify" && (
              <div style={{ display: "flex", flexDirection: "column", gap: "18px" }}>
                <div>
                  <h4 style={{ margin: "0 0 6px 0", fontSize: "15px" }}>Integración de Clockify</h4>
                  <p style={{ margin: 0, fontSize: "13px", color: "var(--text-secondary)" }}>
                    Conecta tu API Key de Clockify para sincronizar automáticamente el tiempo dedicado a tus asignaturas.
                  </p>
                </div>

                <div
                  style={{
                    padding: "12px 16px",
                    borderRadius: "8px",
                    backgroundColor: clockifyStatus ? "rgba(34, 197, 94, 0.1)" : "rgba(234, 179, 8, 0.1)",
                    border: `1px solid ${clockifyStatus ? "rgba(34, 197, 94, 0.3)" : "rgba(234, 179, 8, 0.3)"}`,
                    fontSize: "13px",
                    color: clockifyStatus ? "#15803d" : "#a16207",
                    display: "flex",
                    alignItems: "center",
                    gap: "8px"
                  }}
                >
                  <span style={{ fontWeight: "700" }}>Estado:</span>
                  {clockifyStatus ? "Conectado correctamente" : "No conectado"}
                </div>

                <form onSubmit={handleSaveClockify} style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                  <label style={{ fontSize: "12px", fontWeight: "600", color: "var(--text-secondary)" }}>
                    API Key de Clockify
                  </label>
                  <div style={{ display: "flex", gap: "8px" }}>
                    <input
                      type="password"
                      value={apiKey}
                      onChange={(e) => setApiKey(e.target.value)}
                      placeholder="Introduce tu API Key..."
                      style={{
                        flex: 1,
                        padding: "8px 12px",
                        borderRadius: "8px",
                        border: "1px solid var(--border)",
                        backgroundColor: "var(--bg-input)",
                        color: "var(--text-primary)",
                        fontSize: "13px"
                      }}
                    />
                    <button
                      type="submit"
                      disabled={clockifyLoading || !apiKey.trim()}
                      style={{
                        padding: "8px 16px",
                        borderRadius: "8px",
                        border: "none",
                        backgroundColor: "var(--brand)",
                        color: "#fff",
                        fontWeight: "600",
                        fontSize: "13px",
                        cursor: apiKey.trim() ? "pointer" : "not-allowed",
                        opacity: apiKey.trim() ? 1 : 0.6
                      }}
                    >
                      {clockifyLoading ? "Guardando..." : "Guardar"}
                    </button>
                  </div>
                </form>

                {clockifyMsg && (
                  <p style={{ margin: 0, fontSize: "12px", color: clockifyMsg.type === "success" ? "#16a34a" : "#dc2626" }}>
                    {clockifyMsg.text}
                  </p>
                )}
              </div>
            )}

            {/* PESTAÑA PERMISOS Y PRIVACIDAD */}
            {activeTab === "privacy" && (
              <div style={{ display: "flex", flexDirection: "column", gap: "22px" }}>
                {/* 1. Mi Código */}
                <div style={{ borderBottom: "1px solid var(--border)", paddingBottom: "18px" }}>
                  <h4 style={{ margin: "0 0 6px 0", fontSize: "14px", fontWeight: "600" }}>Tu código de compartir</h4>
                  <p style={{ margin: "0 0 10px 0", fontSize: "12px", color: "var(--text-secondary)" }}>
                    Comparte este código con compañeros para que puedan seguir tus estadísticas de estudio.
                  </p>
                  <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                    <code
                      style={{
                        padding: "6px 14px",
                        borderRadius: "8px",
                        backgroundColor: "var(--bg-page)",
                        border: "1px solid var(--border)",
                        fontSize: "16px",
                        fontWeight: "700",
                        letterSpacing: "2px"
                      }}
                    >
                      {myShareCode || "—"}
                    </code>
                    <button
                      onClick={handleCopyCode}
                      disabled={!myShareCode}
                      style={{
                        padding: "6px 12px",
                        borderRadius: "6px",
                        border: "1px solid var(--border)",
                        backgroundColor: "var(--bg-surface)",
                        cursor: myShareCode ? "pointer" : "not-allowed",
                        fontSize: "12px",
                        display: "flex",
                        alignItems: "center",
                        gap: "4px"
                      }}
                    >
                      {copied ? <Check size={14} color="#16a34a" /> : <Copy size={14} />}
                      {copied ? "Copiado" : "Copiar"}
                    </button>
                    {!myShareCode && (
                      <button
                        onClick={handleGenerateCode}
                        style={{
                          padding: "6px 12px",
                          borderRadius: "6px",
                          border: "none",
                          backgroundColor: "var(--brand)",
                          color: "#fff",
                          cursor: "pointer",
                          fontSize: "12px",
                          fontWeight: "600"
                        }}
                      >
                        Generar código
                      </button>
                    )}
                  </div>
                </div>

                {/* 2. Usuarios que sigo */}
                <div style={{ borderBottom: "1px solid var(--border)", paddingBottom: "18px" }}>
                  <h4 style={{ margin: "0 0 12px 0", fontSize: "14px", fontWeight: "600" }}>Usuarios que sigo</h4>
                  
                  {/* Arriba: Añadir un nuevo usuario */}
                  <div style={{ marginBottom: "16px" }}>
                    <label style={{ display: "block", fontSize: "12px", color: "var(--text-secondary)", marginBottom: "6px", fontWeight: "500" }}>
                      Añadir un nuevo usuario
                    </label>
                    <div style={{ display: "flex", gap: "8px" }}>
                      <input
                        type="text"
                        value={followCode}
                        onChange={(e) => setFollowCode(e.target.value.toUpperCase())}
                        placeholder="Introduce el código..."
                        maxLength={10}
                        style={{
                          padding: "7px 12px",
                          borderRadius: "6px",
                          border: "1px solid var(--border)",
                          backgroundColor: "var(--bg-input)",
                          color: "var(--text-primary)",
                          fontSize: "13px",
                          width: "200px"
                        }}
                      />
                      <button
                        onClick={handleFollowUser}
                        disabled={!followCode.trim()}
                        style={{
                          padding: "7px 16px",
                          borderRadius: "6px",
                          border: "none",
                          backgroundColor: "var(--brand)",
                          color: "#fff",
                          cursor: followCode.trim() ? "pointer" : "not-allowed",
                          fontSize: "12px",
                          fontWeight: "600",
                          opacity: followCode.trim() ? 1 : 0.6
                        }}
                      >
                        Seguir
                      </button>
                    </div>
                    {followError && <p style={{ margin: "6px 0 0", fontSize: "12px", color: "#dc2626" }}>{followError}</p>}
                  </div>

                  {/* Abajo: Lista de usuarios que sigo */}
                  <div>
                    <h5 style={{ margin: "0 0 8px 0", fontSize: "12px", color: "var(--text-secondary)", fontWeight: "600" }}>
                      Lista de usuarios seguidos ({followedUsers.length})
                    </h5>
                    {followedUsers.length === 0 ? (
                      <p style={{ fontSize: "12px", color: "var(--text-secondary)", margin: 0, fontStyle: "italic" }}>
                        No estás siguiendo a ningún usuario todavía.
                      </p>
                    ) : (
                      <div style={{ display: "flex", flexDirection: "column", gap: "6px", maxHeight: "160px", overflowY: "auto" }}>
                        {followedUsers.map((u, idx) => {
                          const uId = u.followed_user_id || u.target_user_id || u.user_id || u.id || u._id;
                          const name = u.name || u.user_name || u.nombre;
                          const email = u.email || u.user_email;

                          let userLabel = `Usuario ${idx + 1}`;
                          if (name && email && name !== email) {
                            userLabel = `${name} (${email})`;
                          } else if (email) {
                            userLabel = email;
                          } else if (name) {
                            userLabel = name;
                          }

                          return (
                            <div
                              key={uId || idx}
                              style={{
                                display: "flex",
                                justifyContent: "space-between",
                                alignItems: "center",
                                padding: "8px 12px",
                                borderRadius: "6px",
                                backgroundColor: "var(--bg-page)",
                                border: "1px solid var(--border)"
                              }}
                            >
                              <span style={{ fontSize: "13px", color: "var(--text-primary)" }}>
                                {userLabel}
                              </span>
                              <button
                                onClick={() => handleUnfollowUser(uId, userLabel)}
                                title="Dejar de seguir"
                                style={{
                                  background: "none",
                                  border: "none",
                                  color: "#dc2626",
                                  cursor: "pointer",
                                  padding: "4px",
                                  display: "flex",
                                  alignItems: "center"
                                }}
                              >
                                <Trash2 size={15} />
                              </button>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                </div>

                {/* 3. Quién puede ver mis estadísticas */}
                <div>
                  <h4 style={{ margin: "0 0 8px 0", fontSize: "14px", fontWeight: "600" }}>
                    Quién puede ver mis estadísticas ({followers.length})
                  </h4>
                  {followers.length === 0 ? (
                    <p style={{ fontSize: "12px", color: "var(--text-secondary)", margin: 0, fontStyle: "italic" }}>
                      Nadie ve tus estadísticas.
                    </p>
                  ) : (
                    <div style={{ display: "flex", flexDirection: "column", gap: "6px", maxHeight: "140px", overflowY: "auto" }}>
                      {followers.map((f, idx) => {
                        const fId = f.follower_id || f.user_id || f.id || f._id;
                        const name = f.name || f.user_name || f.nombre;
                        const email = f.email || f.user_email;

                        let followerLabel = `Usuario ${idx + 1}`;
                        if (name && email && name !== email) {
                          followerLabel = `${name} (${email})`;
                        } else if (email) {
                          followerLabel = email;
                        } else if (name) {
                          followerLabel = name;
                        }

                        return (
                          <div
                            key={fId || idx}
                            style={{
                              display: "flex",
                              justifyContent: "space-between",
                              alignItems: "center",
                              padding: "8px 12px",
                              borderRadius: "6px",
                              backgroundColor: "var(--bg-page)",
                              border: "1px solid var(--border)"
                            }}
                          >
                            <span style={{ fontSize: "13px", color: "var(--text-primary)" }}>
                              {followerLabel}
                            </span>
                            <button
                              onClick={() => handleRevokeFollower(fId, followerLabel)}
                              title="Revocar acceso"
                              style={{
                                background: "none",
                                border: "none",
                                color: "#dc2626",
                                cursor: "pointer",
                                padding: "4px",
                                display: "flex",
                                alignItems: "center"
                              }}
                            >
                              <UserX size={15} />
                            </button>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>

              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}