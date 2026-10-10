import { useState, useEffect, useRef } from 'react';
import { BarChart3, Bot, Users, ChevronRight } from 'lucide-react';
import {
  BACKEND_URL, getToken, authHeaders,
  PageShell, FullPageMessage, BackButton, ErrorBanner, CourseHeader, MarkdownText
} from './shared';

/* CONCLUSIONES IA DE LA CLASE*/

function GlobalSummaryCard({ summaryText, summaryDate, generating, onGenerate }) {
  return (
    <div style={{
      background: "linear-gradient(to right, rgba(99,102,241,0.05), rgba(139,92,246,0.05))",
      border: "1px solid #6366f130", borderRadius: "16px", padding: "24px", marginBottom: "32px"
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px", flexWrap: "wrap", gap: "12px" }}>
        <h3 style={{ margin: 0, fontSize: "16px", fontWeight: "700", color: "var(--text-primary)", display: "flex", alignItems: "center", gap: "8px" }}>
          <Bot size={20} color="var(--brand)" />
          Conclusiones del Agente IA
        </h3>
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
        Datos por alumno
      </h3>
      <p style={{ margin: "0 0 16px", fontSize: "13px", color: "var(--text-secondary)" }}>
        Estadísticas de los alumnos matriculados en el curso.
      </p>

      <div style={{ overflowX: "auto", borderRadius: "12px", border: "1px solid var(--border)", background: "var(--bg-surface)" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: "14px" }}>
          <thead>
            <tr style={{ background: "var(--bg-page)", borderBottom: "1px solid var(--border)" }}>
              <th style={thStyle}>Alumno</th>
              <th style={thStyle}>Tiempo total</th>
              <th style={thStyle}>Concentración</th>
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
                <td style={{ ...tdStyle, fontWeight: "600" }}>{s.name}</td>
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

  const [streaming, setStreaming] = useState(false);
  const abortRef = useRef(null);

  const fetchData = async ({ silent = false } = {}) => {
    if (!token) { /* router.push("/login") */ return; }
    if (!silent) setLoading(true);
    try {
      const [courseRes, analyticsRes, studentsRes] = await Promise.all([
        fetch(`${BACKEND_URL}/api/courses/${courseId}`, { headers: authHeaders(token) }),
        fetch(`${BACKEND_URL}/api/courses/${courseId}/global-analytics`, { headers: authHeaders(token) }),
        fetch(`${BACKEND_URL}/api/courses/${courseId}/students`, { headers: authHeaders(token) }),
      ]);

      if (courseRes.status === 401) { /* router.push("/login") */ return; }
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


  const handleDelete = async () => {
    if (!confirm("¿Eliminar este curso? Esta acción es irreversible.")) return;
    try {
      const res = await fetch(`${BACKEND_URL}/api/courses/${courseId}`, { method: "DELETE", headers: authHeaders(token) });
      if (!res.ok) throw new Error((await res.json()).detail);
      onNavigate({ view: "list" });
    } catch (e) {
      setError(e.message);
    }
  };

  if (loading) return <FullPageMessage emoji="⏳">Cargando curso...</FullPageMessage>;
  if (fatalError) return (
    <FullPageMessage emoji="❌" error onBack={() => onNavigate({ view: "list" })} backLabel="← Volver a cursos">
      {fatalError}
    </FullPageMessage>
  );

  const studentsCount = students.length || stats.length;

  return (
    <PageShell>
      <BackButton onClick={() => onNavigate({ view: "list" })}>← Volver a cursos</BackButton>

      <CourseHeader
        course={course}
        isTeacher
        studentsCount={studentsCount}
        summariesCount={students.filter(s => s.summary).length}
      >

        <button
          onClick={handleDelete}
          style={{ padding: "10px 18px", borderRadius: "10px", border: "1px solid #ef4444", background: "none", color: "#ef4444", fontWeight: "600", fontSize: "13px", cursor: "pointer" }}
        >
          🗑 Eliminar curso
        </button>
      </CourseHeader>

      <ErrorBanner message={error} style={{ marginBottom: "16px" }} />

      {/* Estadísticas generales */}
      <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "20px" }}>
        <div style={{ width: "44px", height: "44px", borderRadius: "12px", background: "linear-gradient(135deg, #6366f1, #8b5cf6)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
          <BarChart3 size={22} color="#fff" />
        </div>
        <div>
          <h2 style={{ margin: 0, fontSize: "1.2rem", fontWeight: "700", color: "var(--text-primary)" }}>Estadísticas generales</h2>
          <p style={{ margin: "2px 0 0", fontSize: "13px", color: "var(--text-secondary)" }}>
            Rendimiento global de los {studentsCount} alumnos matriculados
          </p>
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