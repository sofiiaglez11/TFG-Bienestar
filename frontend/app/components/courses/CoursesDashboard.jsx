import { useState } from 'react';
import CoursesPage from './CoursesPage';
import TeacherCoursePage from './TeacherCoursePage';
import StudentCoursePage from './StudentCoursePage';


export default function CoursesDashboard({ onClose, userRole = "student" }) {
  const [viewState, setViewState] = useState({ view: "list" });

  const handleNavigate = (newState) => {
    if (newState.view === "close") onClose();
    else setViewState(newState);
  };

  switch (viewState.view) {
    case "list": //LISTA DE CURSOS
      return <CoursesPage onNavigate={handleNavigate} userRole={userRole} />;

    case "course": //DETALLE DEL CURSO
      return viewState.role === "teacher"
        ? <TeacherCoursePage key={viewState.courseId} courseId={viewState.courseId} onNavigate={handleNavigate} />
        : <StudentCoursePage key={viewState.courseId} courseId={viewState.courseId} onNavigate={handleNavigate} />;

    default:
      return null;
  }
}
