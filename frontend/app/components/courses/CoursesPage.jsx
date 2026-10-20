import { useState, useEffect } from 'react';
import { GraduationCap, Users, KeyRound, Calendar, Plus } from 'lucide-react';
import {
  BACKEND_URL, YEAR_OPTIONS, getToken, authHeaders,
  Badge, PageShell, Modal, ErrorBanner, EmptyState
} from './shared';

const gridStyle = { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: "16px" };

/* TARJETA DE CURSO */

function CourseCard({ course, role, onClick }) {
  const isTeacher = role === "teacher";
  return (
    <div
      onClick={onClick}
      style={{
        background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: "16px",
        padding: "20px", cursor: "pointer", transition: "all 0.2s ease", position: "relative", overflow: "hidden",
      }}
      onMouseOver={e => {
        e.currentTarget.style.transform = "translateY(-2px)";
        e.currentTarget.style.boxShadow = "0 8px 30px rgba(99,102,241,0.15)";
        e.currentTarget.style.borderColor = "#6366f1";
      }}
      onMouseOut={e => {
        e.currentTarget.style.transform = "translateY(0)";
        e.currentTarget.style.boxShadow = "none";
        e.currentTarget.style.borderColor = "var(--border)";
      }}
    >
      <div style={{
        position: "absolute", top: 0, left: 0, right: 0, height: "3px",
        background: isTeacher ? "linear-gradient(90deg, #6366f1, #8b5cf6)" : "linear-gradient(90deg, #10b981, #059669)"
      }} />


      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "12px" }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <h3 style={{ margin: "0 0 6px 0", fontSize: "16px", fontWeight: "700", color: "var(--text-primary)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {course.name}
          </h3>
          {course.academic_year && (
            <Badge color={isTeacher ? "#6366f1" : "#10b981"}>
              <Calendar size={10} />
              {course.academic_year}
            </Badge>
          )}
        </div>
        <span style={{ marginLeft: "12px", display: "flex", alignItems: "center", color: isTeacher ? "#6366f1" : "#10b981" }}>
          {isTeacher
            ? <Users size={22} strokeWidth={1.8} />
            : <GraduationCap size={22} strokeWidth={1.8} />
          }
        </span>
      </div>

      {course.description && (
        <p style={{ margin: "0 0 12px 0", fontSize: "13px", color: "var(--text-secondary)", lineHeight: "1.5", overflow: "hidden", display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical" }}>
          {course.description}
        </p>
      )}

      <div style={{ display: "flex", gap: "12px", fontSize: "12px", color: "var(--text-secondary)", marginTop: "8px" }}>
        {isTeacher ? (
          <>
            <span>👥 {course.student_ids?.length || 0} alumnos</span>
            <span style={{ marginLeft: "auto", fontFamily: "monospace", background: "var(--bg-input)", padding: "2px 8px", borderRadius: "6px", fontSize: "12px", letterSpacing: "1px", color: "var(--text-primary)" }}>
              {course.enrollment_code}
            </span>
          </>
        ) : (
          <span style={{ color: "#10b981" }}>✓ Matriculado</span>
        )}
      </div>
    </div>
  );
}

/*CABECERA DE SELECCIÓN */

function SectionHeader({ icon: Icon, title, count, color, action }) {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "12px", flexWrap: "wrap", marginBottom: "16px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
        <Icon size={20} color="var(--brand)" />
        <h2 style={{ margin: 0, fontSize: "1.2rem", fontWeight: "700", color: "var(--text-primary)" }}>{title}</h2>
        <Badge color={color}>{count}</Badge>
      </div>
      {action}
    </div>
  );
}

/* MODAL PARA UNIRSE A UN CURSO */

function JoinCourseModal({ unlinkedSubjects, onClose, onEnrolled }) {
  const token = getToken();
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [confirm, setConfirm] = useState(null);
  const [subjectId, setSubjectId] = useState("");

  const executeEnroll = async (enrollCode, linkedSubjectId) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${BACKEND_URL}/api/courses/enroll`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders(token) },
        body: JSON.stringify({ code: enrollCode, subject_id: linkedSubjectId || null }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail);
      onEnrolled(data.course_name);
      onClose();
    } catch (e) {
      setError(e.message);
      setLoading(false);
    }
  };

  const handleSubmitCode = async (e) => {
    e.preventDefault();
    const trimmed = code.trim();
    if (!trimmed) return;
    setLoading(true);
    setError(null);
    try {
      const checkRes = await fetch(`${BACKEND_URL}/api/courses/check/${trimmed}`, { headers: authHeaders(token) });
      const checkData = await checkRes.json();
      if (!checkRes.ok) throw new Error(checkData.detail);

      // Si hay asignaturas sin vincular, paso extra de sincronización
      if (unlinkedSubjects.length > 0) {
        const exactMatch = unlinkedSubjects.find(s => s.name.toLowerCase() === checkData.name.toLowerCase());
        setConfirm({ code: trimmed, courseName: checkData.name, exactMatch });
        setLoading(false);
        return;
      }
      await executeEnroll(trimmed, null);
    } catch (e) {
      setError(e.message);
      setLoading(false);
    }
  };

  const secondaryBtn = { padding: "10px 18px", borderRadius: "10px", border: "1px solid var(--border)", background: "transparent", color: "var(--text-primary)", fontWeight: "600", fontSize: "13px", cursor: "pointer" };

  // Paso 2: sincronización de asignatura
  if (confirm) {
    return (
      <Modal maxWidth="500px">
        <h3 style={{ margin: "0 0 16px", fontSize: "1.2rem", fontWeight: "700", color: "var(--text-primary)" }}>
          Sincronización de asignatura
        </h3>

        {confirm.exactMatch ? (
          <p style={{ margin: "0 0 24px", fontSize: "14px", color: "var(--text-secondary)", lineHeight: "1.6" }}>
            Tienes una asignatura creada llamada <strong>"{confirm.exactMatch.name}"</strong> que coincide con el curso al que te vas a matricular. ¿Quieres vincularla para no perder tus datos estadísticos?
          </p>
        ) : (
          <>
            <p style={{ margin: "0 0 16px", fontSize: "14px", color: "var(--text-secondary)", lineHeight: "1.6" }}>
              Te vas a matricular en <strong>"{confirm.courseName}"</strong>. Tienes las siguientes asignaturas creadas previamente que no están vinculadas a ningún curso. ¿Quieres sincronizar tus datos con alguna de ellas?
            </p>
            <select
              value={subjectId}
              onChange={e => setSubjectId(e.target.value)}
              style={{ width: "100%", padding: "12px", borderRadius: "10px", border: "1px solid var(--border)", background: "var(--bg-input)", color: "var(--text-primary)", fontSize: "14px", outline: "none", marginBottom: "24px" }}
            >
              <option value="">(No vincular, crear una nueva)</option>
              {unlinkedSubjects.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </>
        )}

        <ErrorBanner message={error} style={{ marginBottom: "16px" }} />

        <div style={{ display: "flex", gap: "12px", justifyContent: "flex-end", flexWrap: "wrap" }}>
          <button onClick={onClose} style={{ ...secondaryBtn, border: "none", background: "var(--bg-input)" }}>Cancelar</button>

          {confirm.exactMatch ? (
            <>
              <button onClick={() => executeEnroll(confirm.code, null)} disabled={loading} style={secondaryBtn}>
                No, crear nueva
              </button>
              <button
                onClick={() => executeEnroll(confirm.code, confirm.exactMatch.id)}
                disabled={loading}
                style={{ padding: "10px 18px", borderRadius: "10px", border: "none", background: "linear-gradient(135deg, #10b981, #059669)", color: "#fff", fontWeight: "700", fontSize: "13px", cursor: "pointer" }}
              >
                {loading ? "Uniendo..." : "Sí, sincronizar datos"}
              </button>
            </>
          ) : (
            <button
              onClick={() => executeEnroll(confirm.code, subjectId)}
              disabled={loading}
              style={{ padding: "10px 18px", borderRadius: "10px", border: "none", background: "linear-gradient(135deg, #6366f1, #8b5cf6)", color: "#fff", fontWeight: "700", fontSize: "13px", cursor: "pointer" }}
            >
              {loading ? "Uniendo..." : "Continuar e inscribirme"}
            </button>
          )}
        </div>
      </Modal>
    );
  }

  // Paso 1: código del curso
  const disabled = loading || !code.trim();
  return (
    <Modal>
      <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "20px" }}>
        <KeyRound size={28} color="var(--brand)" />
        <div>
          <h2 style={{ margin: 0, fontSize: "1.2rem", fontWeight: "700", color: "var(--text-primary)" }}>Unirme a un curso</h2>
          <p style={{ margin: "4px 0 0", fontSize: "13px", color: "var(--text-secondary)" }}>
            Introduce el código que te haya proporcionado tu profesor
          </p>
        </div>
      </div>

      <form onSubmit={handleSubmitCode} style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
        <input
          autoFocus
          value={code}
          onChange={e => setCode(e.target.value.toUpperCase())}
          placeholder="Código (ej: A3BX9K)"
          maxLength={16}
          style={{
            width: "100%", padding: "12px 14px", borderRadius: "10px", border: "1px solid var(--border)",
            background: "var(--bg-input)", color: "var(--text-primary)", fontSize: "14px",
            fontFamily: "monospace", letterSpacing: "2px", outline: "none", boxSizing: "border-box"
          }}
        />
        <ErrorBanner message={error} />
        <div style={{ display: "flex", gap: "12px" }}>
          <button
            type="button" onClick={onClose}
            style={{ flex: 1, padding: "12px", borderRadius: "10px", border: "1px solid var(--border)", background: "none", color: "var(--text-primary)", fontWeight: "600", cursor: "pointer", fontSize: "14px" }}
          >
            Cancelar
          </button>
          <button
            type="submit" disabled={disabled}
            style={{
              flex: 1, padding: "12px", borderRadius: "10px", border: "none",
              background: disabled ? "var(--border)" : "linear-gradient(135deg, #10b981, #059669)",
              color: "#fff", fontWeight: "700", fontSize: "14px", cursor: disabled ? "not-allowed" : "pointer"
            }}
          >
            {loading ? "Comprobando..." : "Unirme"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

/* MODAL: CREAR CURSO*/

const labelStyle = { display: "block", fontSize: "13px", fontWeight: "600", color: "var(--text-secondary)", marginBottom: "6px" };
const fieldStyle = {
  width: "100%", padding: "11px 14px", borderRadius: "10px", border: "1px solid var(--border)",
  background: "var(--bg-input)", color: "var(--text-primary)", fontSize: "14px", outline: "none", boxSizing: "border-box"
};

function CreateCourseModal({ onClose, onCreated }) {
  const token = getToken();
  const [form, setForm] = useState({ name: "", description: "", academic_year: "" });
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.name.trim()) return;
    setCreating(true);
    setError(null);
    try {
      const res = await fetch(`${BACKEND_URL}/api/courses`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders(token) },
        body: JSON.stringify(form),
      });
      if (!res.ok) throw new Error((await res.json()).detail);
      onCreated();
      onClose();
    } catch (e) {
      setError(e.message);
      setCreating(false);
    }
  };

  return (
    <Modal>
      <h2 style={{ margin: "0 0 24px", fontSize: "22px", fontWeight: "800", color: "var(--text-primary)", display: "flex", alignItems: "center", gap: "10px" }}>
        <Plus size={22} />
        Crear nuevo curso
      </h2>
      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
        <div>
          <label style={labelStyle}>Nombre del curso *</label>
          <input
            required value={form.name}
            onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
            placeholder="Ej: Cálculo I, Programación Web..."
            style={fieldStyle}
          />
        </div>
        <div>
          <label style={labelStyle}>Descripción (opcional)</label>
          <textarea
            value={form.description}
            onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
            placeholder="Breve descripción del curso..."
            rows={3}
            style={{ ...fieldStyle, resize: "vertical", fontFamily: "inherit" }}
          />
        </div>
        <div>
          <label style={labelStyle}>Curso académico (opcional)</label>
          <select
            value={form.academic_year}
            onChange={e => setForm(f => ({ ...f, academic_year: e.target.value }))}
            style={fieldStyle}
          >
            <option value="">Sin especificar</option>
            {YEAR_OPTIONS.map(y => <option key={y} value={y}>{y}</option>)}
          </select>
        </div>

        <ErrorBanner message={error} />

        <div style={{ display: "flex", gap: "12px", marginTop: "8px" }}>
          <button
            type="button" onClick={onClose}
            style={{ flex: 1, padding: "12px", borderRadius: "10px", border: "1px solid var(--border)", background: "none", color: "var(--text-primary)", fontWeight: "600", cursor: "pointer", fontSize: "14px" }}
          >
            Cancelar
          </button>
          <button
            type="submit" disabled={creating}
            style={{ flex: 1, padding: "12px", borderRadius: "10px", border: "none", background: "linear-gradient(135deg, #6366f1, #8b5cf6)", color: "#fff", fontWeight: "700", cursor: creating ? "not-allowed" : "pointer", fontSize: "14px" }}
          >
            {creating ? "Creando..." : "Crear curso"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

/* PÁGINA*/

export default function CoursesPage({ onNavigate, userRole = "student" }) {
  const token = getToken();

  const [teachingCourses, setTeachingCourses] = useState([]);
  const [enrolledCourses, setEnrolledCourses] = useState([]);
  const [unlinkedSubjects, setUnlinkedSubjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [filterYear, setFilterYear] = useState("all");
  const [showJoin, setShowJoin] = useState(false);
  const [showCreate, setShowCreate] = useState(false);

  const fetchCourses = async () => {
    if (!token) { /* router.push("/login") */ return; }
    setLoading(true);
    try {
      const [teachRes, enrollRes, subjectsRes] = await Promise.all([
        fetch(`${BACKEND_URL}/api/courses/teaching`, { headers: authHeaders(token) }),
        fetch(`${BACKEND_URL}/api/courses/enrolled`, { headers: authHeaders(token) }),
        fetch(`${BACKEND_URL}/api/subjects/unlinked`, { headers: authHeaders(token) }),
      ]);
      if (teachRes.status === 401 || enrollRes.status === 401) { /* router.push("/login") */ return; }
      setTeachingCourses((await teachRes.json()).courses || []);
      setEnrolledCourses((await enrollRes.json()).courses || []);
      setUnlinkedSubjects((await subjectsRes.json()).subjects || []);
    } catch (e) {
      setError("Error al cargar los cursos");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchCourses(); }, []);

  const handleEnrolled = (courseName) => {
    setNotice(`Te has matriculado en "${courseName}"`);
    setTimeout(() => setNotice(null), 5000);
    fetchCourses();
  };

  const availableYears = Array.from(new Set(
    [...teachingCourses, ...enrolledCourses].map(c => c.academic_year).filter(Boolean)
  )).sort().reverse();

  const byYear = (list) => filterYear === "all" ? list : list.filter(c => c.academic_year === filterYear);
  const filteredEnrolled = byYear(enrolledCourses);
  const filteredTeaching = byYear(teachingCourses);

  return (
    <PageShell>
      {/* Header */}
      <div style={{ marginBottom: "32px" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "16px", flexWrap: "wrap" }}>
          <div>
            <h1 style={{ margin: 0, fontSize: "1.4rem", fontWeight: "700", display: "flex", alignItems: "center", gap: "10px", color: "var(--text-primary)" }}>
              {userRole === "teacher" ? "Mis Cursos" : "Mis Cursos"}
            </h1>
            <p style={{ margin: "4px 0 0 0", fontSize: "14px", color: "var(--text-secondary)" }}>
              {userRole === "teacher"
                ? "Gestiona los cursos que impartes"
                : "Gestiona los cursos en los que estás matriculado"}
            </p>
          </div>

          {!loading && availableYears.length > 0 && (
            <select
              value={filterYear}
              onChange={(e) => setFilterYear(e.target.value)}
              style={{ padding: "8px 12px", borderRadius: "8px", border: "1px solid var(--border)", backgroundColor: "var(--bg-surface)", color: "var(--text-primary)", fontSize: "14px", outline: "none", cursor: "pointer" }}
            >
              <option value="all">Todos los años académicos</option>
              {availableYears.map(y => <option key={y} value={y}>{y}</option>)}
            </select>
          )}
        </div>
      </div>

      {notice && <div style={{ marginBottom: "16px", fontSize: "13px", color: "#10b981" }}>{notice}</div>}

      {loading ? (
        <div style={{ textAlign: "center", padding: "60px", color: "var(--text-secondary)" }}>
          <div style={{ fontSize: "32px", marginBottom: "12px" }}>⏳</div>
          Cargando cursos...
        </div>
      ) : (
        <>
          {/* 1. Matriculado + botón unirse — solo para estudiantes */}
          {userRole !== "teacher" && (
          <section style={{ marginBottom: "40px" }}>
            <SectionHeader
              icon={GraduationCap}
              title="Cursos en los que estoy matriculado"
              count={filteredEnrolled.length}
              color="#10b981"
              action={
                <button
                  onClick={() => setShowJoin(true)}
                  style={{ padding: "10px 18px", borderRadius: "10px", border: "none", background: "linear-gradient(135deg, #10b981, #059669)", color: "#fff", fontWeight: "700", fontSize: "14px", cursor: "pointer", boxShadow: "0 4px 12px rgba(16,185,129,0.3)" }}
                >
                  Unirme a un curso
                </button>
              }
            />
            {filteredEnrolled.length === 0 ? (
              <EmptyState>
                {filterYear !== "all"
                  ? "No hay cursos en este año académico."
                  : "Aún no estás matriculado en ningún curso. Pulsa 'Unirme a un curso' e introduce el código de tu profesor."}
              </EmptyState>
            ) : (
              <div style={gridStyle}>
                {filteredEnrolled.map(c => (
                  <CourseCard key={c._id} course={c} role="student" onClick={() => onNavigate({ view: "course", courseId: c._id, role: "student" })} />
                ))}
              </div>
            )}
          </section>
          )}

          {/* 2. Imparto + botón crear — solo para profesores */}
          {userRole !== "student" && (
          <section>
            <SectionHeader
              icon={Users}
              title="Cursos que imparto"
              count={filteredTeaching.length}
              color="#6366f1"
              action={
                <button
                  onClick={() => setShowCreate(true)}
                  style={{ padding: "10px 18px", borderRadius: "10px", border: "none", background: "linear-gradient(135deg, #6366f1, #8b5cf6)", color: "#fff", fontWeight: "700", fontSize: "14px", cursor: "pointer", boxShadow: "0 4px 12px rgba(99,102,241,0.3)" }}
                >
                  + Crear curso
                </button>
              }
            />
            {filteredTeaching.length === 0 ? (
              <EmptyState>
                {filterYear !== "all"
                  ? "No hay cursos en este año académico."
                  : "Aún no has creado ningún curso. Pulsa '+ Crear curso' para empezar."}
              </EmptyState>
            ) : (
              <div style={gridStyle}>
                {filteredTeaching.map(c => (
                  <CourseCard key={c._id} course={c} role="teacher" onClick={() => onNavigate({ view: "course", courseId: c._id, role: "teacher" })} />
                ))}
              </div>
            )}
          </section>
          )}
        </>
      )}

      <ErrorBanner message={error} style={{ margin: "16px 0" }} />

      {showJoin && (
        <JoinCourseModal unlinkedSubjects={unlinkedSubjects} onClose={() => setShowJoin(false)} onEnrolled={handleEnrolled} />
      )}
      {showCreate && (
        <CreateCourseModal onClose={() => setShowCreate(false)} onCreated={fetchCourses} />
      )}
    </PageShell>
  );
}