import asyncio
import sys
import re
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional

from services.clockify_service import ClockifyService


class AnalyticsService:
    def __init__(self, db_service):
        self.db_service = db_service

    async def _get_user_clockify_service(self, user_id: str) -> Optional[ClockifyService]:
        user = await self.db_service.get_user_by_id(user_id)
        if user and user.get("clockify"):
            cdata = user["clockify"]
            api_key = cdata.get("api_key") or cdata.get("token")
            if api_key:
                return ClockifyService(
                    api_key=api_key,
                    workspace_id=cdata.get("workspace_id")
                )
        return None

    def _parse_iso_duration_minutes(self, duration_str: str) -> float:
        """Convierte una cadena de duración ISO 8601 (ej. PT1H30M15S) a minutos usando re nativo (sin dependencias externas)."""
        if not duration_str:
            return 0.0
        try:
            pattern = r'PT(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+(?:\.\d+)?)S)?'
            match = re.match(pattern, duration_str)
            if not match:
                return 0.0
            parts = match.groupdict()
            hours = float(parts['hours']) if parts['hours'] else 0.0
            minutes = float(parts['minutes']) if parts['minutes'] else 0.0
            seconds = float(parts['seconds']) if parts['seconds'] else 0.0
            return hours * 60.0 + minutes + seconds / 60.0
        except Exception:
            return 0.0

    async def get_academic_analytics(self, user_id: str, days: int = 7) -> list:
        """Horas, sesiones, concentración y tareas por asignatura."""
        WEEKDAYS = {0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves", 4: "Viernes", 5: "Sábado", 6: "Domingo"}
        subjects = await self.db_service.get_subjects_by_user(user_id)
        
        # Obtener entradas de tiempo desde Clockify
        cs = await self._get_user_clockify_service(user_id)
        clockify_entries = []
        if cs:
            try:
                clockify_entries = await asyncio.to_thread(cs.get_time_entries, days_back=days)
            except Exception as e:
                print(f"[ANALYTICS] Error al consultar Clockify: {e}", file=sys.stderr)

        # Obtener informes de estudio de MongoDB para asociar la nota de concentración/calidad
        study_reports = []
        try:
            study_reports = await self.db_service.get_study_reports_by_user(user_id, limit=100)
        except Exception as e:
            print(f"[ANALYTICS] Error al consultar informes de estudio: {e}", file=sys.stderr)

        result = []
        for subject in subjects:
            s_id = str(subject.get("_id"))
            s_name = subject.get("name", "Sin nombre")
            clockify_proj_id = subject.get("clockify_project_id")

            # Filtrar entradas de Clockify correspondientes a esta asignatura
            subj_entries = [
                e for e in clockify_entries
                if clockify_proj_id and e.get("projectId") == clockify_proj_id
            ]

            # Buscar informes de estudio asociados a la asignatura
            s_name_clean = (s_name or "").lower().strip()
            subj_reports = [
                r for r in study_reports
                if (r.get("subject_name") or "").lower().strip() == s_name_clean
            ]

            sessions = []
            for e in subj_entries:
                start_str = e.get("start") or e.get("timeInterval", {}).get("start")
                end_str = e.get("end") or e.get("timeInterval", {}).get("end")
                if start_str and end_str:
                    try:
                        start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                        end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                        duration = max(0.0, (end_dt - start_dt).total_seconds() / 60.0)

                        # Buscar concentración en informe de estudio correspondiente si existe
                        entry_id = e.get("id")
                        matched_report = next((r for r in subj_reports if r.get("clockify_time_entry_id") == entry_id), None)
                        conc = matched_report.get("study_quality") if matched_report else None

                        sessions.append({
                            "date": start_dt.strftime("%Y-%m-%d"),
                            "weekday": WEEKDAYS.get(start_dt.weekday(), start_dt.strftime("%A")),
                            "duration_minutes": round(duration),
                            "concentration": conc,
                            "start_hour": start_dt.hour
                        })
                    except Exception:
                        pass

            total_hours = sum(s["duration_minutes"] for s in sessions) / 60.0
            avg_duration = sum(s["duration_minutes"] for s in sessions) / len(sessions) if sessions else 0.0

            # Concentración media (de las sesiones o informes)
            quality_list = [s["concentration"] for s in sessions if s.get("concentration") is not None]
            if not quality_list:
                quality_list = [r.get("study_quality") for r in subj_reports if r.get("study_quality") is not None]
            
            avg_concentration = sum(quality_list) / len(quality_list) if quality_list else None

            # Tareas de la asignatura
            tasks = []
            try:
                tasks = await self.db_service.get_tasks_by_subject(s_id)
            except Exception:
                pass

            tasks_completed = sum(1 for t in tasks if t.get("completed") or str(t.get("status")).upper() == "COMPLETED")
            tasks_pending = sum(1 for t in tasks if not (t.get("completed") or str(t.get("status")).upper() == "COMPLETED"))

            result.append({
                "name": s_name,
                "total_hours_week": round(total_hours, 1),
                "sessions": sessions,
                "avg_session_duration_minutes": round(avg_duration),
                "avg_concentration": round(avg_concentration, 1) if avg_concentration is not None else None,
                "tasks_completed": tasks_completed,
                "tasks_pending": tasks_pending,
                "grade": subject.get("grade")
            })
        return result

    async def get_wellbeing_analytics(self, user_id: str, days: int = 7) -> dict:
        """Sueño, estado de ánimo y energía por día de la semana."""
        WEEKDAYS = {0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves", 4: "Viernes", 5: "Sábado", 6: "Domingo"}
        reports = await self.db_service.get_wellbeing_trends(user_id)
        by_weekday = {}
        for r in reports:
            raw_date = r.get("date") or r.get("timestamp")
            if not raw_date:
                continue
            if isinstance(raw_date, datetime):
                dt = raw_date
            else:
                try:
                    dt = datetime.fromisoformat(str(raw_date).replace("Z", "+00:00"))
                except Exception:
                    continue

            day = WEEKDAYS.get(dt.weekday(), dt.strftime("%A"))
            if day not in by_weekday:
                by_weekday[day] = {"sleep": [], "mood": [], "energy": []}

            if r.get("sleep_hours") is not None:
                by_weekday[day]["sleep"].append(float(r["sleep_hours"]))
            if r.get("mood_score") is not None:
                by_weekday[day]["mood"].append(float(r["mood_score"]))
            st = r.get("energy_level") or r.get("stress_score") or r.get("fatigue_score")
            if st is not None:
                by_weekday[day]["energy"].append(float(st))

        summary = {}
        for day, vals in by_weekday.items():
            s_avg = round(sum(vals["sleep"]) / len(vals["sleep"]), 1) if vals["sleep"] else None
            m_avg = round(sum(vals["mood"]) / len(vals["mood"]), 1) if vals["mood"] else None
            e_avg = round(sum(vals["energy"]) / len(vals["energy"]), 1) if vals["energy"] else None
            summary[day] = {"sleep": s_avg, "mood": m_avg, "energy": e_avg}

        sleep_all = [float(r["sleep_hours"]) for r in reports if r.get("sleep_hours") is not None]
        avg_sleep = round(sum(sleep_all) / len(sleep_all), 1) if sleep_all else None

        worst_day = None
        valid_mood_days = {d: summary[d]["mood"] for d in summary if summary[d]["mood"] is not None}
        if valid_mood_days:
            worst_day = min(valid_mood_days, key=valid_mood_days.get)

        return {
            "avg_sleep_hours": avg_sleep,
            "reports_by_weekday": summary,
            "worst_day": worst_day
        }

    async def get_patterns(self, user_id: str, days: int = 7) -> dict:
        """Detecta patrones: sesiones nocturnas, días más productivos, etc."""
        WEEKDAYS = {0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves", 4: "Viernes", 5: "Sábado", 6: "Domingo"}
        cs = await self._get_user_clockify_service(user_id)
        clockify_entries = []
        if cs:
            try:
                clockify_entries = await asyncio.to_thread(cs.get_time_entries, days_back=days)
            except Exception as e:
                print(f"[ANALYTICS] Error al consultar Clockify para patrones: {e}", file=sys.stderr)

        late_sessions = []
        hours_by_weekday = {}

        for e in clockify_entries:
            start_str = e.get("start") or e.get("timeInterval", {}).get("start")
            end_str = e.get("end") or e.get("timeInterval", {}).get("end")
            if start_str and end_str:
                try:
                    start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                    end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                    
                    if start_dt.hour >= 23 or start_dt.hour < 6:
                        late_sessions.append(f"{WEEKDAYS.get(start_dt.weekday())} a las {start_dt.strftime('%H:%M')}")
                    
                    day = WEEKDAYS.get(start_dt.weekday(), start_dt.strftime("%A"))
                    duration_hrs = (end_dt - start_dt).total_seconds() / 3600.0
                    hours_by_weekday[day] = hours_by_weekday.get(day, 0.0) + duration_hrs
                except Exception:
                    pass

        most_prod = max(hours_by_weekday, key=hours_by_weekday.get) if hours_by_weekday else None
        least_prod = min(hours_by_weekday, key=hours_by_weekday.get) if hours_by_weekday else None

        plan_progress = await self.get_study_plan_progress(user_id, days=days)

        return {
            "late_night_sessions": late_sessions,
            "hours_by_weekday": {d: round(h, 1) for d, h in hours_by_weekday.items()},
            "most_productive_weekday": most_prod,
            "least_productive_weekday": least_prod,
            "study_plan_progress": plan_progress
        }

    async def get_study_plan_progress(self, user_id: str, days: int = 7) -> dict:
        """Calcula el progreso del plan de estudio activo frente a las horas reales estudiadas y comprueba tareas atrasadas o no completadas."""
        try:
            plan = await self.db_service.get_active_study_plan(user_id)
            if not plan:
                return {"has_active_plan": False}

            items = plan.get("items", [])
            planned_by_subject = {}
            total_planned_hours = 0.0

            for item in items:
                subj = (item.get("subject_name") or "Otras / General").strip()
                hrs = float(item.get("planned_hours", 0) or 0)
                planned_by_subject[subj] = planned_by_subject.get(subj, 0.0) + hrs
                total_planned_hours += hrs

            academic = await self.get_academic_analytics(user_id, days=days)
            actual_by_subject = {s["name"]: s["total_hours_week"] for s in academic}
            total_actual_hours = sum(actual_by_subject.values())

            # Evaluación de desvíos y tareas asociadas al plan
            overdue_tasks = []
            try:
                from zoneinfo import ZoneInfo
                today_str = datetime.now(ZoneInfo("Europe/Madrid")).strftime("%Y-%m-%d")
            except Exception:
                today_str = datetime.now().strftime("%Y-%m-%d")

            cursor = self.db_service.tasks.find({"user_id": user_id})
            all_user_tasks = await cursor.to_list(500)

            subjects_list = await self.db_service.get_subjects_by_user(user_id, include_archived=True)
            subj_id_to_name = {str(s["_id"]): s.get("name", "Asignatura") for s in subjects_list}

            total_plan_tasks = 0
            completed_plan_tasks = 0
            progress_by_subject = {}

            for subj, p_hrs in planned_by_subject.items():
                a_hrs = actual_by_subject.get(subj, 0.0)
                h_pct = round((a_hrs / p_hrs) * 100, 1) if p_hrs > 0 else 100.0

                # Tareas de esta asignatura
                subj_tasks = [t for t in all_user_tasks if subj_id_to_name.get(str(t.get("subject_id")), "").lower() == subj.lower()]
                subj_total_tasks = len(subj_tasks)
                subj_completed_tasks = len([t for t in subj_tasks if t.get("status") == "COMPLETED"])

                t_pct = round((subj_completed_tasks / subj_total_tasks) * 100, 1) if subj_total_tasks > 0 else 0.0

                total_plan_tasks += subj_total_tasks
                completed_plan_tasks += subj_completed_tasks

                # Progreso principal: por tareas si las hay, por horas si no hay tareas todavía
                main_subj_pct = t_pct if subj_total_tasks > 0 else min(100.0, h_pct)

                progress_by_subject[subj] = {
                    "planned_hours": p_hrs,
                    "actual_hours": a_hrs,
                    "hours_progress_pct": min(100.0, h_pct),
                    "total_tasks": subj_total_tasks,
                    "completed_tasks": subj_completed_tasks,
                    "tasks_progress_pct": t_pct,
                    "progress_pct": main_subj_pct
                }

            hours_overall_pct = round((total_actual_hours / total_planned_hours) * 100, 1) if total_planned_hours > 0 else 0.0
            tasks_overall_pct = round((completed_plan_tasks / total_plan_tasks) * 100, 1) if total_plan_tasks > 0 else 0.0

            # Progreso general priorizando tareas completadas
            if total_plan_tasks > 0:
                overall_pct = tasks_overall_pct
            else:
                overall_pct = min(100.0, hours_overall_pct)

            for t in all_user_tasks:
                due_d = t.get("due_date")
                status = t.get("status")
                completed_at = t.get("completed_at")
                s_name = subj_id_to_name.get(str(t.get("subject_id")), "General")
                
                due_d_clean = due_d[:10] if due_d and len(due_d) >= 10 else due_d

                if due_d_clean and due_d_clean < today_str and status != "COMPLETED":
                    overdue_tasks.append({
                        "title": t.get("title", "Tarea sin título"),
                        "subject_name": s_name,
                        "due_date": due_d_clean,
                        "status": "INCUMPLIDA_PENDIENTE"
                    })
                elif due_d_clean and completed_at and str(completed_at)[:10] > due_d_clean:
                    overdue_tasks.append({
                        "title": t.get("title", "Tarea sin título"),
                        "subject_name": s_name,
                        "due_date": due_d_clean,
                        "completed_at": str(completed_at)[:10],
                        "status": "COMPLETADA_FUERA_DE_PLAZO"
                    })

            return {
                "has_active_plan": True,
                "plan_title": plan.get("title", "Plan de Estudio"),
                "total_planned_hours": round(total_planned_hours, 1),
                "total_actual_hours": round(total_actual_hours, 1),
                "hours_overall_pct": min(100.0, hours_overall_pct),
                "total_plan_tasks": total_plan_tasks,
                "completed_plan_tasks": completed_plan_tasks,
                "tasks_overall_pct": tasks_overall_pct,
                "overall_progress_pct": min(100.0, overall_pct),
                "progress_by_subject": progress_by_subject,
                "overdue_tasks": overdue_tasks,
                "has_overdue_tasks": len(overdue_tasks) > 0
            }
        except Exception as e:
            print(f"[ANALYTICS] Error al calcular el progreso del plan: {e}", file=sys.stderr)
            return {"has_active_plan": False}


    async def get_user_analytics(self, user_id: str, days: int = 7) -> dict:
        """Método principal que agrega todo."""
        academic = await self.get_academic_analytics(user_id, days)
        wellbeing = await self.get_wellbeing_analytics(user_id, days)
        patterns = await self.get_patterns(user_id, days)

        return {
            "academic": {"subjects": academic, "patterns": patterns},
            "wellbeing": wellbeing,
            "formatted_text": self._format_for_llm(academic, wellbeing, patterns)
        }

    def _format_for_llm(self, academic, wellbeing, patterns) -> str:
        """Formatea los datos en texto estructurado para el LLM."""
        lines = ["=== ANÁLISIS ACADÉMICO ==="]
        for s in academic:
            lines.append(f"\nASIGNATURA: {s['name']}:")
            lines.append(f"  - Horas esta semana: {s['total_hours_week']}h")
            lines.append(f"  - Duración media por sesión: {s['avg_session_duration_minutes']} min")
            if s.get("avg_concentration") is not None:
                lines.append(f"  - Concentración media: {s['avg_concentration']}/5")
            lines.append(f"  - Tareas: {s['tasks_completed']} completadas, {s['tasks_pending']} pendientes")
            if s.get("grade") is not None:
                lines.append(f"  - Nota: {s['grade']}/10")

        lines.append("\n=== PATRONES DETECTADOS ===")
        if patterns.get("most_productive_weekday"):
            lines.append(f"  - Día más productivo: {patterns['most_productive_weekday']}")
        if patterns.get("least_productive_weekday"):
            lines.append(f"  - Día menos productivo: {patterns['least_productive_weekday']}")
        if patterns.get("late_night_sessions"):
            lines.append(f"  - Sesiones nocturnas detectadas: {len(patterns['late_night_sessions'])}")

        plan = patterns.get("study_plan_progress", {})
        if plan.get("has_active_plan"):
            lines.append(f"\n=== SEGUIMIENTO DEL PLAN DE ESTUDIO ACTIVO ('{plan.get('plan_title')}') ===")
            lines.append(f"  - Progreso global: {plan.get('overall_progress_pct')}% ({plan.get('total_actual_hours')}h reales / {plan.get('total_planned_hours')}h planificadas)")
            for subj, pdata in plan.get("progress_by_subject", {}).items():
                lines.append(f"  - {subj}: {pdata['actual_hours']}h reales de {pdata['planned_hours']}h planificadas ({pdata['progress_pct']}%)")

        lines.append("\n=== BIENESTAR ===")
        lines.append(f"  - Sueño medio: {wellbeing.get('avg_sleep_hours', 'N/D')}h")
        if wellbeing.get("worst_day"):
            lines.append(f"  - Día con peor estado de ánimo: {wellbeing['worst_day']}")

        return "\n".join(lines)
