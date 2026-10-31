"use client";

import { useState, useEffect } from "react";
import { X, Copy, Check, Trash2, UserX, BarChart2, Clock, Settings, Tag as TagIcon, Palette } from "lucide-react";
import ClockifyConfigPanel from "./ClockifyConfigPanel";
import TagBadge from "./TagBadge";
import TagColorPickerModal from "./TagColorPickerModal";
import { setTagColorLocal, refreshTagColors } from "../utils/tagColorStore";
import styles from "./SettingsModal.module.css";

const RAW_BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
const BACKEND_URL = RAW_BACKEND_URL.replace(/\/+$/, "");

export default function SettingsModal({ isOpen, onClose, initialTab = "clockify", onSuccess, onFollowChange }) {
  const [activeTab, setActiveTab] = useState(initialTab); // "clockify" | "privacy" | "tags"

  // Reflejo del estado de Clockify, reportado por ClockifyConfigPanel
  const [clockifyStatus, setClockifyStatus] = useState(null);

  // Estado Permisos y Compartir
  const [myShareCode, setMyShareCode] = useState(null);
  const [copied, setCopied] = useState(false);
  const [followCode, setFollowCode] = useState("");
  const [followError, setFollowError] = useState(null);
  const [followedUsers, setFollowedUsers] = useState([]);
  const [followers, setFollowers] = useState([]);
  const [privacyLoading, setPrivacyLoading] = useState(false);

  // Estado Etiquetas / Tags
  const [tags, setTags] = useState([]);
  const [tagsLoading, setTagsLoading] = useState(false);
  const [selectedTagForColor, setSelectedTagForColor] = useState(null);
  const [mergeMessage, setMergeMessage] = useState("");

  useEffect(() => {
    if (isOpen) {
      setActiveTab(initialTab);
      loadPrivacyData();
      loadTagsData();
    }
  }, [isOpen, initialTab]);

  const loadTagsData = async () => {
    const token = localStorage.getItem("token");
    if (!token) return;
    setTagsLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/tags`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setTags(data.tags || []);
      }
    } catch (err) {
      console.error("Error al cargar etiquetas:", err);
    } finally {
      setTagsLoading(false);
    }
  };

  const handleUpdateTagColor = async (tagName, colorHex) => {
    const token = localStorage.getItem("token");
    if (!token) return;
    try {
      const res = await fetch(`${BACKEND_URL}/api/tags`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({ name: tagName, color: colorHex })
      });
      if (!res.ok) throw new Error(`No se pudo guardar el color (HTTP ${res.status})`);
      setTags((prev) =>
        prev.map((t) => (t.name.toLowerCase() === tagName.trim().toLowerCase() ? { ...t, color: colorHex } : t))
      );
      setTagColorLocal(tagName, colorHex); // actualiza chat y demás vistas al instante
    } catch (err) {
      console.error("Error al actualizar color de la etiqueta:", err);
      throw err; // el modal de color no se cierra si falla
    }
  };

  const handleMergeDuplicateTags = async () => {
    const token = localStorage.getItem("token");
    if (!token) return;
    try {
      const res = await fetch(`${BACKEND_URL}/api/tags/merge-duplicates`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setMergeMessage(
          data.merged?.length
            ? `Se han fusionado ${data.merged.length} etiqueta(s) duplicada(s).`
            : "No hay etiquetas duplicadas."
        );
        await loadTagsData();
        await refreshTagColors();
      }
    } catch (err) {
      console.error("Error al fusionar etiquetas duplicadas:", err);
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
      // Actualización optimista: añadir el usuario desde la respuesta de la API
      const data = await res.json();
      const newUser = {
        user_id: data.user_id,
        name: data.name || "Estudiante",
        email: data.email || ""
      };
      setFollowedUsers((prev) => {
        const alreadyExists = prev.some((u) => (u.user_id || u.id) === newUser.user_id);
        return alreadyExists ? prev : [...prev, newUser];
      });
      setFollowCode("");
      // Notificar a AnalyticsDashboard para que actualice el selector de usuarios
      if (onFollowChange) onFollowChange();
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
        // Actualización optimista: eliminar el usuario de la lista local
        setFollowedUsers((prev) =>
          prev.filter((u) => {
            const id = u.followed_user_id || u.target_user_id || u.user_id || u.id || u._id;
            return id !== targetUserId;
          })
        );
        // Notificar a AnalyticsDashboard para que actualice el selector de usuarios
        if (onFollowChange) onFollowChange();
      } else {
        const errData = await res.json().catch(() => ({}));
        console.error(`Error al dejar de seguir [HTTP ${res.status}]:`, errData);
      }
    } catch (err) {
      console.error("Error de conexión al dejar de seguir:", err);
    }
  };

  const handleRevokeFollower = async (followerUserId, followerUserName) => {
    if (!followerUserId) {
      console.error("ID de usuario no válido para revocar acceso:", followerUserId);
      return;
    }
    const displayName = followerUserName ? `"${followerUserName}"` : "este usuario";
    if (!window.confirm(`¿Estás seguro de que deseas quitarle el acceso a tus estadísticas a ${displayName}?`)) {
      return;
    }
    const token = localStorage.getItem("token");
    if (!token) return;
    try {
      const res = await fetch(`${BACKEND_URL}/api/share/followers/${followerUserId}`, {
        method: "DELETE",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`
        }
      });
      if (res.ok) {
        // Actualización optimista: eliminar el seguidor de la lista local
        setFollowers((prev) => prev.filter((f) => {
          const id = f.follower_id || f.user_id || f.id || f._id;
          return id !== followerUserId;
        }));
      } else {
        const errData = await res.json().catch(() => ({}));
        console.error(`Error al revocar acceso [HTTP ${res.status}]:`, errData);
      }
    } catch (err) {
      console.error("Error de conexión al revocar acceso:", err);
    }
  };

  if (!isOpen) return null;

  return (
    <div className={styles.backdrop}>
      <div className={styles.panel}>
        {/* Cabecera Modal */}
        <div className={styles.panelHeader}>
          <h3 className={styles.panelTitle}>
            <Settings size={18} />
            Configuración
          </h3>
          <button onClick={onClose} className={styles.btnCloseHeader}>
            <X size={20} />
          </button>
        </div>

        {/* Cuerpo con Navegación Lateral */}
        <div className={styles.body}>
          {/* Menú Izquierdo */}
          <div className={styles.sidebar}>
            {[
              { id: "clockify", label: "Clockify", Icon: Clock },
              { id: "privacy",  label: "Estadísticas", Icon:  BarChart2 },
              { id: "tags",     label: "Etiquetas", Icon: TagIcon },
            ].map(({ id, label, Icon }) => (
              <button
                key={id}
                onClick={() => setActiveTab(id)}
                className={`${styles.sidebarBtn} ${activeTab === id ? styles.sidebarBtnActive : ""}`}
              >
                <Icon size={16} /> {label}
              </button>
            ))}
          </div>

          {/* Área de Contenido */}
          <div className={styles.content}>
            {/* PESTAÑA CLOCKIFY */}
            {/* Se mantiene montada (oculta con CSS) mientras el modal está abierto,
                en vez de solo cuando esta pestaña está activa, para que su estado
                se cargue en cuanto se abre el modal y esté disponible también para
                la pestaña de Permisos */}
            <div style={{ display: activeTab === "clockify" ? "flex" : "none", flexDirection: "column", gap: "18px" }}>
              <div>
                <h4 className={styles.sectionTitle}>
                  Integración con Clockify
                </h4>
                <p className={styles.sectionSubtitle}>
                  Conecta tu API Key de Clockify para sincronizar automáticamente el tiempo dedicado a tus asignaturas.
                </p>
              </div>

              <ClockifyConfigPanel
                isActive={isOpen}
                onSuccess={onSuccess}
                onStatusChange={setClockifyStatus}
              />
            </div>  

            {/* PESTAÑA PERMISOS Y PRIVACIDAD */}
            {activeTab === "privacy" && (
              <div style={{ display: "flex", flexDirection: "column", gap: "22px" }}>
                {/* 1. Mi Código */}
                <div className={styles.section}>
                  <h4 className={styles.sectionTitle}>Código para compartir mis estadísticas</h4>
                  <p className={styles.sectionSubtitle}>
                    Comparte este código con compañeros para que puedan seguir tus estadísticas de estudio.
                  </p>
                  {!clockifyStatus ? (
                    <p className={styles.warningText}>
                      Debes vincular una cuenta de Clockify para poder compartir tus estadísticas.
                    </p>
                  ) : (
                    <div className={styles.shareCodeRow}>
                      <code className={styles.shareCode}>
                        {myShareCode || (privacyLoading ? "Cargando..." : "—")}
                      </code>
                      <button
                        onClick={handleCopyCode}
                        disabled={!myShareCode}
                        className={styles.btnOutline}
                      >
                        {copied ? <Check size={14} color="#16a34a" /> : <Copy size={14} />}
                        {copied ? "Copiado" : "Copiar"}
                      </button>
                    </div>
                  )}
                </div>

                {/* 2. Usuarios que sigo */}
                <div className={styles.section}>
                  <h4 className={styles.sectionTitle}>Estadísticas que quiero ver</h4>

                  {/* Añadir un nuevo usuario */}
                  <div style={{ marginBottom: "16px" }}>
                    <label style={{ margin: "0 0 8px 0", fontSize: "12px", color: "var(--text-secondary)", fontWeight: "600" }}>
                      Añadir un nuevo usuario
                    </label>
                    <div className={styles.inputRow}>
                      <input
                        type="text"
                        value={followCode}
                        onChange={(e) => setFollowCode(e.target.value.toUpperCase())}
                        placeholder="Introduce el código..."
                        maxLength={10}
                        className={styles.inputField}
                      />
                      <button
                        onClick={handleFollowUser}
                        disabled={!followCode.trim()}
                        className={styles.btnPrimary}
                      >
                        Seguir
                      </button>
                    </div>
                    {followError && <p className={styles.errorText}>{followError}</p>}
                  </div>

                  {/* Lista de usuarios que sigo */}
                  <div>
                    <h5 style={{ margin: "0 0 8px 0", fontSize: "12px", color: "var(--text-secondary)", fontWeight: "600" }}>
                      Usuarios a los que puedo ver sus estadísticas ({followedUsers.length})
                    </h5>
                    {followedUsers.length === 0 ? (
                      <p style={{ fontSize: "12px", color: "var(--text-secondary)", margin: 0, fontStyle: "italic" }}>
                        No estás siguiendo a ningún usuario todavía.
                      </p>
                    ) : (
                      <div className={styles.userList}>
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
                            <div key={uId || idx} className={styles.userListItem}>
                              <span className={styles.userListItemName}>{userLabel}</span>
                              <button
                                onClick={() => handleUnfollowUser(uId, userLabel)}
                                title="Dejar de seguir"
                                className={styles.btnDanger}
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
                  <h4 className={styles.sectionTitle}>
                    Quién puede ver mis estadísticas ({followers.length})
                  </h4>
                  {followers.length === 0 ? (
                    <p style={{ fontSize: "12px", color: "var(--text-secondary)", margin: 0, fontStyle: "italic" }}>
                      Nadie ve tus estadísticas.
                    </p>
                  ) : (
                    <div className={styles.userList} style={{ maxHeight: "140px" }}>
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
                          <div key={fId || idx} className={styles.userListItem}>
                            <span className={styles.userListItemName}>{followerLabel}</span>
                            <button
                              onClick={() => handleRevokeFollower(fId, followerLabel)}
                              title="Revocar acceso"
                              className={styles.btnDanger}
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

            {/* PESTAÑA ETIQUETAS Y COLORES */}
            {activeTab === "tags" && (
              <div style={{ display: "flex", flexDirection: "column", gap: "18px" }}>
                <div>
                  <h4 className={styles.sectionTitle}>
                    Personalización de Etiquetas
                  </h4>
                  <p style={{ margin: 0, fontSize: "13px", color: "var(--text-secondary)" }}>
                    Haz clic sobre cualquier etiqueta para elegir su color de la paleta. Si no seleccionas ninguno, se asignará un color armónico por defecto.
                  </p>
                  <div style={{ display: "flex", alignItems: "center", gap: "12px", marginTop: "10px" }}>
                    <button onClick={handleMergeDuplicateTags} className={styles.btnMerge}>
                      Fusionar duplicadas
                    </button>
                    {mergeMessage && (
                      <span style={{ fontSize: "12px", color: "var(--text-secondary)" }}>{mergeMessage}</span>
                    )}
                  </div>
                </div>

                {tagsLoading ? (
                  <div style={{ fontSize: "13px", color: "var(--text-secondary)" }}>Cargando etiquetas...</div>
                ) : tags.length === 0 ? (
                  <div className={styles.tagsEmpty}>
                    No se han encontrado etiquetas. Se irán registrando automáticamente conforme añadas tags en tus tareas o en las respuestas de la IA.
                  </div>
                ) : (
                  <div className={styles.tagGrid}>
                    {tags.map((t) => (
                      <TagBadge
                        key={t.name}
                        name={t.name}
                        color={t.color}
                        onClick={() => setSelectedTagForColor(t)}
                      />
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      <TagColorPickerModal
        isOpen={Boolean(selectedTagForColor)}
        tag={selectedTagForColor?.name}
        currentColor={selectedTagForColor?.color}
        onClose={() => setSelectedTagForColor(null)}
        onSelectColor={handleUpdateTagColor}
      />
    </div>
  );
}