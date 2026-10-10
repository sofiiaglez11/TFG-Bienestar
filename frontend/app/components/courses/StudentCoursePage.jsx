import { useState, useEffect } from 'react';
import { BookOpen } from 'lucide-react';
import {
  BACKEND_URL, getToken, authHeaders,
  PageShell, FullPageMessage, BackButton, ErrorBanner, CourseHeader
} from './shared';

export default function StudentCoursePage({ courseId, onNavigate }) {
  const token = getToken();

  const [course, setCourse] = useState(null);
  const [loading, setLoading] = useState(true);
  const [fatalError, setFatalError] = useState(null);
  const [error, setError] = useState(null);

  const fetchCourse = async () => {
    if (!token) { /* router.push("/login") */ return; }
    setLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/courses/${courseId}`, { headers: authHeaders(token) });
      if (res.status === 401) { /* router.push("/login") */ return; }
      if (res.status === 404) { setFatalError("Curso no encontrado"); return; }
      if (res.status === 403) { setFatalError("No tienes acceso a este curso"); return; }
      if (!res.ok) throw new Error("Error al cargar el curso");
      setCourse(await res.json());
    } catch (e) {
      setFatalError("Error al cargar el curso");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { if (courseId) fetchCourse(); }, [courseId]);

  const handleLeave = async () => {
    if (!confirm("¿Seguro que quieres desmatricularte de este curso?")) return;
    try {
      const res = await fetch(`${BACKEND_URL}/api/courses/${courseId}/leave`, { method: "DELETE", headers: authHeaders(token) });
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

  return (
    <PageShell maxWidth="900px">
      <BackButton onClick={() => onNavigate({ view: "list" })}>← Volver a cursos</BackButton>

      <CourseHeader course={course} isTeacher={false}>
        <button
          onClick={handleLeave}
          style={{ padding: "10px 18px", borderRadius: "10px", border: "1px solid #ef4444", background: "none", color: "#ef4444", fontWeight: "600", fontSize: "13px", cursor: "pointer" }}
        >
          Desmatricularse
        </button>
      </CourseHeader>

      <div style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: "16px", padding: "28px", textAlign: "center" }}>
        <div style={{ marginBottom: "16px", display: "flex", justifyContent: "center" }}>
          <BookOpen size={48} color="var(--brand)" />
        </div>
        <h2 style={{ margin: "0 0 8px", fontSize: "20px", fontWeight: "700", color: "var(--text-primary)" }}>
          Estás matriculado en {course?.name}
        </h2>
        <p style={{ margin: "0 0 20px", fontSize: "14px", color: "var(--text-secondary)", lineHeight: "1.6" }}>
          Tu progreso en esta asignatura aparece automáticamente en tu panel de estadísticas.
          Tu profesor podrá ver un resumen de tu rendimiento académico.
        </p>
      </div>

      <ErrorBanner message={error} style={{ marginTop: "16px" }} />
    </PageShell>
  );
}
