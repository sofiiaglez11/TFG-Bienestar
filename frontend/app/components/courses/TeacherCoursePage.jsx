import { useState, useEffect, useRef } from 'react';
import { BarChart3, Bot, Users, ChevronRight, Loader2, XCircle, ArrowLeft, Trash2, Copy, Check, Calendar, Menu } from 'lucide-react';
import {
  BACKEND_URL, getToken, authHeaders,
  PageShell, FullPageMessage, BackButton, ErrorBanner, MarkdownText, Badge
} from './shared';

const iconLabel = { display: "inline-flex", alignItems: "center", gap: "6px" };

const BackLabel = () => (
  <span style={iconLabel}>
    <ArrowLeft size={16} /> Volver a cursos
  </span>
);

/* CONCLUSIONES IA DE LA CLASE*/

function GlobalSummaryCard({ summaryText, summaryDate, generating, onGenerate }) {
  return (
    <div style={{
      background: "linear-gradient(to right, rgba(99,102,241,0.05), rgba(139,92,246,0.05))",
      border: "1px solid #6366f130", borderRadius: "16px", padding: "24px", marginBottom: "32px"
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px", flexWrap: "wrap", gap: "12px" }}>
        
        {summaryDate && (
          <span style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
            Generado el {new Date(summaryDate).toLocaleDateString("es-ES")}
          </span>
        )}
      </div>

      {summaryText ? (
        <div style={{ marginBottom: "20px" }}>
          <MarkdownText>{summaryText}</MarkdownText>
        </div>
      ) : (
        <p style={{ margin: "0 0 20px", fontSize: "14px", color: "var(--text-secondary)" }}>
          Aún no se ha generado un resumen de las estadísticas globales de la clase.
        </p>
      )}

      <button
        onClick={onGenerate}
        disabled={generating}
        style={{
          padding: "10px 18px", borderRadius: "10px", border: "none",
          background: "linear-gradient(135deg, #6366f1, #8b5cf6)", color: "#fff", fontWeight: "700", fontSize: "13px",
          cursor: generating ? "not-allowed" : "pointer", opacity: generating ? 0.7 : 1
        }}
      >
        {generating ? "Generando..." : summaryText ? "Regenerar conclusiones IA" : "Generar conclusiones IA"}
      </button>
    </div>
  );
}

/* TABLA DE ALUMNOS */

const thStyle = { padding: "12px 16px", fontWeight: "600", color: "var(--text-secondary)" };
const tdStyle = { padding: "12px 16px", color: "var(--text-primary)" };

function StudentsTable({ stats, onSelect }) {
  return (
    <>
      <h3 style={{ margin: "0 0 4px", fontSize: "18px", fontWeight: "700", color: "var(--text-primary)", display: "flex", alignItems: "center", gap: "8px" }}>
        <Users size={20} color="var(--brand)" />
        Datos por estudiante
      </h3>
      <p style={{ margin: "0 0 16px", fontSize: "13px", color: "var(--text-secondary)" }}>
        Estadísticas de los alumnos matriculados en el curso.
      </p>

      <div style={{ overflowX: "auto", borderRadius: "12px", border: "1px solid var(--border)", background: "var(--bg-surface)" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: "14px" }}>
          <thead>
            <tr style={{ background: "var(--bg-page)", borderBottom: "1px solid var(--border)" }}>
              <th style={thStyle}>Estudiante</th>
              <th style={thStyle}>Tiempo total dedicado</th>
              <th style={thStyle}>Concentración promedia</th>
              <th style={thStyle}>Sueño promedio</th>
              <th style={thStyle}>Nota</th>
            </tr>
          </thead>
          <tbody>
            {stats.map((s, idx) => (
              <tr
                key={s.student_id ?? idx}
                style={{ borderBottom: "1px solid var(--border)" }}
              >
                <td style={{ ...tdStyle, fontWeight: "600" }}>Estudiante</td> 
                <td style={tdStyle}>{s.hours} h</td>
                <td style={tdStyle}>
                  {s.avg_concentration !== null && s.avg_concentration !== undefined ? `${s.avg_concentration} / 5` : "—"}
                </td>
                <td style={tdStyle}>{s.avg_sleep ? `${s.avg_sleep} h` : "—"}</td>
                <td style={{ ...tdStyle, fontWeight: "700" }}>{s.grade ?? "—"}</td>
              </tr>
            ))}
            {stats.length === 0 && (
              <tr>
                <td colSpan="5" style={{ padding: "24px", textAlign: "center", color: "var(--text-secondary)" }}>
                  No hay estudiantes con datos registrados en este curso.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}

/*PÁGINA*/

export default function TeacherCoursePage({ courseId, onNavigate }) {
  const token = getToken();

  const [course, setCourse] = useState(null);
  const [stats, setStats] = useState([]);
  const [students, setStudents] = useState([]);
  const [summaryText, setSummaryText] = useState(null);
  const [summaryDate, setSummaryDate] = useState(null);

  const [loading, setLoading] = useState(true);
  const [fatalError, setFatalError] = useState(null);
  const [error, setError] = useState(null);
  const [generating, setGenerating] = useState(false);
  const [showMenu, setShowMenu] = useState(false);
  const [copied, setCopied] = useState(false);

  const abortRef = useRef(null);
  const menuRef = useRef(null);

  const fetchData = async ({ silent = false } = {}) => {
    if (!token) { return; }
    if (!silent) setLoading(true);
    try {
      const [courseRes, analyticsRes, studentsRes] = await Promise.all([
        fetch(`${BACKEND_URL}/api/courses/${courseId}`, { headers: authHeaders(token) }),
        fetch(`${BACKEND_URL}/api/courses/${courseId}/global-analytics`, { headers: authHeaders(token) }),
        fetch(`${BACKEND_URL}/api/courses/${courseId}/students`, { headers: authHeaders(token) }),
      ]);

      if (courseRes.status === 401) { return; }
      if (courseRes.status === 404) { setFatalError("Curso no encontrado"); return; }
      if (courseRes.status === 403) { setFatalError("No tienes acceso a este curso"); return; }
      if (!courseRes.ok) throw new Error("Error al cargar el curso");
      setCourse(await courseRes.json());

      if (analyticsRes.ok) {
        const data = await analyticsRes.json();
        setStats(data.stats || []);
        setSummaryText(data.global_summary || null);
        setSummaryDate(data.global_summary_generated_at || null);
      } else {
        const err = await analyticsRes.json().catch(() => ({}));
        setError(err.detail || "Error al cargar las estadísticas globales");
      }

      if (studentsRes.ok) {
        setStudents((await studentsRes.json()).students || []);
      }
    } catch (e) {
      setFatalError("Error al cargar el curso");
    } finally {
      if (!silent) setLoading(false);
    }
  };

  useEffect(() => {
    if (courseId) fetchData();
    return () => abortRef.current?.abort();
  }, [courseId]);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setShowMenu(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleGenerateSummary = async () => {
    setGenerating(true);
    setError(null);
    try {
      const res = await fetch(`${BACKEND_URL}/api/courses/${courseId}/global-summary`, {
        method: "POST",
        headers: authHeaders(token)
      });
      if (!res.ok) throw new Error((await res.json()).detail || "Error generando resumen");
      const data = await res.json();
      setSummaryText(data.summary);
      setSummaryDate(data.generated_at);
    } catch (e) {
      setError(e.message);
    } finally {
      setGenerating(false);
    }
  };

  const handleCopyCode = () => {
    if (course?.enrollment_code) {
      navigator.clipboard.writeText(course.enrollment_code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleDelete = async () => {
    setShowMenu(false);
    if (!confirm("¿Eliminar este curso? Esta acción es irreversible.")) return;
    try {
      const res = await fetch(`${BACKEND_URL}/api/courses/${courseId}`, { method: "DELETE", headers: authHeaders(token) });
      if (!res.ok) throw new Error((await res.json()).detail);
      onNavigate({ view: "list" });
    } catch (e) {
      setError(e.message);
    }
  };

  if (loading) return (
    <FullPageMessage>
      Cargando curso...
    </FullPageMessage>
  );

  if (fatalError) return (
    <FullPageMessage
      emoji={<XCircle size={32} color="#ef4444" />}
      error
      onBack={() => onNavigate({ view: "list" })}
      backLabel={<BackLabel />}
    >
      {fatalError}
    </FullPageMessage>
  );

  const studentsCount = students.length || stats.length;

  return (
    <PageShell>
      <BackButton onClick={() => onNavigate({ view: "list" })}><BackLabel /></BackButton>

      {/* HEADER REDISEÑADO */}
      <div style={{
        background: "var(--bg-surface)",
        border: "1px solid var(--border)",
        borderRadius: "16px",
        padding: "24px",
        marginBottom: "24px",
        position: "relative",
        overflow: "visible"
      }}>
        <div style={{
          position: "absolute", top: 0, left: 0, right: 0, height: "3px",
          background: "var(--brand)", borderRadius: "16px 16px 0 0"
        }} />

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "16px", flexWrap: "wrap" }}>
          
          {/* Columna Izquierda: Icono + Nombre + Badges */}
          <div style={{ display: "flex", gap: "16px", alignItems: "flex-start" }}>
            <span style={{
              padding: "12px",
              borderRadius: "12px",
              background: "rgba(99,102,241,0.1)",
              color: "var(--brand)",
              display: "flex",
              alignItems: "center"
            }}>
              <Users size={28} strokeWidth={1.8} />
            </span>

            <div>
              <h1 style={{ margin: "0 0 8px 0", fontSize: "1.5rem", fontWeight: "800", color: "var(--text-primary)" }}>
                {course?.name}
              </h1>

              <div style={{ display: "flex", gap: "8px", alignItems: "center", flexWrap: "wrap" }}>
                {course?.academic_year && (
                  <Badge color="var(--brand)">
                    <Calendar size={12} />
                    {course.academic_year}
                  </Badge>
                )}
                <Badge color="#6366f1">
                  <Users size={12} />
                  {studentsCount} {studentsCount === 1 ? "alumno" : "alumnos"}
                </Badge>
              </div>
            </div>
          </div>

          {/* Columna Derecha: Código de matrícula (Estilo Settings) y Menú Hamburguesa */}
          <div style={{ display: "flex", alignItems: "center", gap: "12px", flexWrap: "wrap" }}>
            {course?.enrollment_code && (
              <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                <code
                  style={{
                    padding: "6px 14px",
                    borderRadius: "8px",
                    backgroundColor: "var(--bg-page)",
                    border: "1px solid var(--border)",
                    fontSize: "16px",
                    fontWeight: "700",
                    letterSpacing: "2px",
                    color: "var(--text-primary)",
                    fontFamily: "monospace"
                  }}
                >
                  {course.enrollment_code}
                </code>
                <button
                  onClick={handleCopyCode}
                  style={{
                    padding: "6px 12px",
                    borderRadius: "6px",
                    border: "1px solid var(--border)",
                    backgroundColor: "var(--bg-surface)",
                    color: "var(--text-primary)",
                    cursor: "pointer",
                    fontSize: "12px",
                    fontWeight: "600",
                    display: "flex",
                    alignItems: "center",
                    gap: "4px"
                  }}
                >
                  {copied ? <Check size={14} color="#16a34a" /> : <Copy size={14} />}
                  {copied ? "Copiado" : "Copiar"}
                </button>
              </div>
            )}

            {/* Menú Hamburguesa */}
            <div style={{ position: "relative" }} ref={menuRef}>
              <button
                onClick={() => setShowMenu(!showMenu)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justify: "center",
                  padding: "8px",
                  borderRadius: "10px",
                  border: "1px solid var(--border)",
                  background: "var(--bg-surface)",
                  color: "var(--text-primary)",
                  cursor: "pointer",
                  transition: "all 0.2s"
                }}
                title="Opciones"
              >
                <Menu size={18} />
              </button>

              {showMenu && (
                <div style={{
                  position: "absolute",
                  top: "100%",
                  right: 0,
                  marginTop: "6px",
                  background: "var(--bg-surface)",
                  border: "1px solid var(--border)",
                  borderRadius: "10px",
                  boxShadow: "0 8px 24px rgba(0,0,0,0.12)",
                  zIndex: 20,
                  minWidth: "150px",
                  overflow: "hidden"
                }}>
                  <button
                    onClick={handleDelete}
                    style={{
                      width: "100%",
                      padding: "10px 14px",
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                      background: "none",
                      border: "none",
                      color: "#ef4444",
                      fontSize: "13px",
                      fontWeight: "600",
                      cursor: "pointer",
                      textAlign: "left",
                      transition: "background 0.2s"
                    }}
                    onMouseOver={e => e.currentTarget.style.background = "rgba(239, 68, 68, 0.08)"}
                    onMouseOut={e => e.currentTarget.style.background = "transparent"}
                  >
                    <Trash2 size={16} />
                    <span>Eliminar curso</span>
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      <ErrorBanner message={error} style={{ marginBottom: "16px" }} />

      {/* Estadísticas generales */}
      <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "20px" }}>
        <div style={{ width: "44px", height: "44px", borderRadius: "12px", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
          <BarChart3 size={22} color="var(--brand)" />
        </div>
        <div>
          <h2 style={{ margin: 0, fontSize: "1.2rem", fontWeight: "700", color: "var(--text-primary)" }}>Resumen de estadísticas del curso generado por agente inteligente  </h2>
          {/* <p style={{ margin: "2px 0 0", fontSize: "13px", color: "var(--text-secondary)" }}>
            Rendimiento global de los {studentsCount} alumnos matriculados
          </p> */}
        </div>
      </div>

      <GlobalSummaryCard
        summaryText={summaryText}
        summaryDate={summaryDate}
        generating={generating}
        onGenerate={handleGenerateSummary}
      />

      <StudentsTable
        stats={stats}
        onSelect={(studentId) => onNavigate({ view: "student", courseId, studentId })}
      />
    </PageShell>
  );
}