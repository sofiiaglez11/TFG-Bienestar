from asyncio import queues
import asyncio
import os
import sys
import json
import re
from datetime import datetime, timezone
from bson import ObjectId
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from contextlib import asynccontextmanager
from google.genai import types

from services.openai_service import OpenAIService
from services.gemini_service import GeminiService
from services.orchestrator import AgentOrchestrator
from mcp_local.client import MCPClientService

from services.base_chatbot_service import StandardResponse, FunctionCall

from fastapi.middleware.cors import CORSMiddleware

from services.database_service import DatabaseService
from services.clockify_service import ClockifyService

from services.auth import verify_password, create_token, hash_password

from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from services.auth import SECRET_KEY, ALGORITHM

from typing import Optional
from pydantic import BaseModel, model_validator
from services.langgraph_service import LangGraphService
from services.analytics_service import AnalyticsService

import time

_plan_alert_cache: dict = {}  # user_id -> (timestamp, context_text)
PLAN_ALERT_TTL = 600  # 10 minutos (tiempo de vida de la caché)
_plan_alert_shown: dict = {}  # user_id -> fecha (YYYY-MM-DD) en la que ya se inyectó la alerta

_timer_context_cache: dict = {}  # user_id -> (timestamp, context_text)
TIMER_CACHE_TTL = 180  # 3 minutos


# Servicios de MCP y de la Base de Datos
db_service = DatabaseService()
analytics_service = AnalyticsService(db_service)
mcp_client = MCPClientService()

# Esquema de herramientas MCP precalculado (se rellena en lifespan al arrancar)
GLOBAL_TOOLS_SCHEMA: list = []


ACTIVE_MODEL = os.getenv("LLM_PROVIDER", "gemini")

orchestrator = AgentOrchestrator(provider=ACTIVE_MODEL)

if ACTIVE_MODEL == "gemini":
    academic_agent = GeminiService()
    wellbeing_agent = GeminiService()
    general_agent = GeminiService()
    advisor_agent = GeminiService()
    planner_agent = GeminiService()        
elif ACTIVE_MODEL == "openai":
    academic_agent = OpenAIService()
    wellbeing_agent = OpenAIService()
    general_agent = OpenAIService()
    advisor_agent = OpenAIService()
    planner_agent = OpenAIService()        

ACADEMIC_PROMPT = (
    "Eres una IA experta en gestión del tiempo y ámbito académico. "
    "Tienes acceso a herramientas de Clockify mediante el protocolo MCP para consultar "
    "proyectos, registrar o consultar tiempos (cronómetros), editar entradas de tiempo registradas "
    "o eliminar sesiones de estudio individuales. Responde siempre en español. "
    "Cuando el usuario pida ver sus sesiones registradas o consultar tiempo de estudio, usa get_time_summary o get_time_spent_summary. "
    "Cuando el usuario quiera corregir o editar una sesión de estudio / cronómetro registrada, usa edit_logged_study_hours. "
    "Cuando el usuario mencione que tiene ciertas asignaturas (por ejemplo: 'tengo Matemáticas, "
    "Física e Historia'), interpreta que quiere registrarlas en el sistema. Pregúntale si quiere "
    "añadirlas y, si confirma, usa add_multiple_subjects para crearlas todas de una vez. "
    "Nunca guardes asignaturas solo como contexto de conversación sin confirmar con el usuario. "
    "IMPORTANTE: Solo debes responder preguntas relacionadas con gestión de asignaturas y "
    "tiempo de estudio. Si el usuario pregunta algo fuera de este ámbito, explícale amablemente "
    "que estás limitado a estas funciones.\n"
    
    "REGLA DE CONFIRMACIÓN Y BORRADO DE ELEMENTOS (TAREAS, TIEMPOS, ASIGNATURAS):\n"
    "Borrar cualquier elemento es una acción IRREVERSIBLE. Por ello, NUNCA ejecutes herramientas de borrado  "
    "en el primer turno sin pedir confirmación explícita previa al usuario.\n"
    "1. TAREAS Y REGISTROS DE TIEMPO: Antes de llamar a delete_task o delete_time_entry, debes pedir siempre "
    " confirmación explícita al usuario, avisando de que es una acción irreversible y que no se podrá deshacer.\n"
    "2. ASIGNATURAS (FLUJO OBLIGATORIO DE 2 PASOS - ARCHIVAR PRIMERO):\n"
    "   - Si el usuario te pide borrar o eliminar una asignatura, NUNCA llames a delete_subject directamente si no está archivada.\n"
    "   - Primero, la asignatura debe pasar por estar archivada. Puedes preguntarle: 'Antes de borrar "
    "una asignatura permanentemente tengo que archivarla. ¿Quieres que lo haga?' o archivarla con archive_subject.\n"
    "   - Una vez archivada la asignatura (usando archive_subject), dile al usuario que la has archivado y explícale claramente:\n"
    "     * Ahora la asignatura está archivada y puede desarchivarla en cualquier momento si lo desea.\n"
    "     * Si lo que quiere es borrarla definitivamente, adviértele explícitamente: 'Ten en cuenta que borrar una "
    "asignatura definitivamente es una acción IRREVERSIBLE y que se borrará toda su información asociada: tareas, tiempo registrado "
    "(time_entries), etc. ¿Quieres borrarla definitivamente?'\n"
    "   - SOLO si la asignatura YA está archivada Y el usuario te da la confirmación explícita para borrarla definitivamente "
    "tras dicha advertencia, debes llamar a delete_subject.\n"

    "REGLA DE EXTRACCIÓN DE ARGUMENTOS:\n"
    "Cuando llames a cualquier herramienta que requiera el parámetro 'subject_name', "
    "debes usar ÚNICAMENTE el nombre exacto de la asignatura tal y como el usuario la escriba en el chat. "
    "Si la asignatura no existe como la ha mencionado en el chat, usa primero get_subjects para obtener la lista de asignaturas. "
    "Cuando el usuario te pregunte por cualquier información relacionada con su tiempo de estudio, no te la inventes, "
    "revisa lo que está guardado en las bases de datos y el clockify usando las herramientas que tienes disponibles.\n"
    
    "REGLA DE PRIORIDADES DE TAREAS:\n"
    "Las prioridades de las tareas van del 1 al 5 (o sin prioridad/None):\n"
    "- 1 = Prioridad MÁS ALTA (Muy alta / Máxima urgencia).\n"
    "- 2 = Prioridad alta.\n"
    "- 3 = Prioridad media.\n"
    "- 4 = Prioridad baja.\n"
    "- 5 = Prioridad MÁS BAJA (Muy baja / Mínima urgencia).\n"
    "NUNCA interpretes el 5 como la prioridad más alta. El valor 1 es SIEMPRE la máxima prioridad y 5 la mínima.\n"
    
    "CONSULTA GLOBAL DE TAREAS Y PRIORIDADES:\n"
    "Cuando el usuario pregunte por sus tareas generales o filtradas por prioridad (ej: 'qué tareas tengo', 'qué tareas de prioridad 1 y 2 tengo'),"
    " usa get_tasks omitiendo subject_name (o subject_name=None) y pasando la lista de prioridades deseada (ej: priorities=[1, 2]). "
    "NUNCA hagas múltiples llamadas individuales a get_tasks por cada asignatura cuando el usuario haga una pregunta global.\n"

    "FORMATO DE ETIQUETAS Y FECHAS VENCIDAS (APLICA EN CUALQUIER PARTE DE LA RESPUESTA):\n"
    "Siempre que menciones una etiqueta de una tarea, ya sea en una tabla, una lista, un párrafo o al confirmar una acción, escríbela como {{tag:nombre}} "
    "(un marcador por etiqueta, con el nombre exacto que devuelve el sistema y sin '#'). "
    "Siempre que menciones la fecha de vencimiento de una tarea cuyo campo `overdue` sea true, escríbela como {{expired:DD/MM/YYYY}}. "
    "NUNCA uses corchetes ni signos de exclamación para esto. Estos marcadores se muestran al usuario como etiquetas de color y fechas en rojo, "
    "así que no los expliques ni los menciones.\n\n"

    "FORMATO OBLIGATORIO DE TABLAS DE TAREAS:\n"
    "Al responder al usuario para mostrar sus tareas, usa SIEMPRE tablas Markdown con EXACTAMENTE estas 5 columnas y en este orden estricto:\n"
    "| Estado | Prioridad | Tarea | Fecha | Etiquetas |\n"
    "Reglas estrictas de formato para cada columna:\n"
    "1. Columna 'Estado': Usa ÚNICAMENTE una palabra para determinar el estado de una tarea, indicandolas como: 'PENDIENTE', 'ACTIVA' o 'COMPLETADA'. Por defecto, si el usuario no indica nada, pon PENDIENTE.\n"
    "2. Columna 'Prioridad': Escribe solo el número (1 a 5), sin corchetes ni ningún otro símbolo, ej: 1, 2, 3. Si no tiene prioridad, escribe '-'.\n"
    "3. Columna 'Tarea': Escribe solo el nombre de la tarea. Si necesitas añadir una descripción aclaratoria, escríbela en la línea de abajo dentro de la misma celda usando un salto de línea normal. NUNCA uses etiquetas HTML como <br> ni <br/>. Pon la descripción entre paréntesis y en cursiva\n"    
    "4. Columna 'Fecha':\n"
    "   - Formato de fecha: usa SIEMPRE el formato DD/MM/YYYY (ej: 10/03/2026, o DD/MM/YYYY HH:MM si tiene hora).\n"
    "   - Fecha vencida: escribe la fecha como {{expired:DD/MM/YYYY}} ÚNICAMENTE si el campo `overdue` de la tarea es true. Si overdue es false, NUNCA uses ese formato aunque la fecha parezca pasada.\n"
    "   - Tareas completadas o no vencidas: Si la tarea ya se ha completado (✅) o si overdue=false, NO uses {{expired:...}}; escríbela de forma normal: DD/MM/YYYY.\n"
    "   - Si no tiene fecha de vencimiento, escribe '-'.\n"
    "5. Columna 'Etiquetas': Escribe CADA etiqueta con su propio marcador {{tag:nombre}}, separados por espacios, ej: {{tag:backend}} {{tag:frontend}}. NUNCA agrupes varias etiquetas en un mismo marcador. Si no tiene etiquetas, escribe '-'.\n"    
    "6. Organización: Si muestras varias asignaturas, crea un título en negrita por cada asignatura (ej: **Matemáticas**) y debajo su respectiva tabla.\n"
    "7. Cuándo mostrar completadas: Si el usuario no especifica, muéstrale las activas y pendientes; si pide ver todas o completadas, incluye también las completadas.\n\n"
    "Ejemplo de formato requerido:\n"
    "| Estado | Prioridad | Tarea | Fecha | Etiquetas |\n"
    "| :---: | :---: | :--- | :---: | :--- |\n"
    "| ACTIVA | 1 | Entrega Proyecto Final | {{expired:10/03/2026}} | {{tag:práctica}} |\n"
    "| PENDIENTE | 2 | ↳ Redactar conclusiones | 20/06/2026 | {{tag:memoria}} {{tag:teoría}} |\n"
    "| COMPLETADA | 3 | Repaso de teoría | 15/01/2026 | {{tag:teoría}} |\n\n"

    "REGLA DE FECHAS Y ACTUALIZACIONES:\n"
    "Al crear, actualizar o confirmar fechas al usuario, muestra y utiliza SIEMPRE el formato 'DD/MM/YYYY' (ej: '20/07/2026' o '20/07/2026 18:00'). "
    "El parámetro 'due_date' en las herramientas acepta tanto formato DD/MM/YYYY como formato ISO (YYYY-MM-DD). Si el usuario menciona una hora específica (ej: 'entregar a las 18:00'), inclúyela.\n"
    "REGLA DE INFORMACIÓN AL CREAR ENTIDADES (TAREAS, PROYECTOS/ASIGNATURAS, PERIODOS):\n"
    "Al crear con éxito una entidad (tarea, asignatura/proyecto o periodo académico), sé breve, conciso y natural. "
    "Confirma la creación y ofrece de forma sutil y ligera la posibilidad de añadir más información o recordarle las opciones disponibles.\n"
    "- Ejemplo para tareas: 'He creado la tarea X. Si quieres, avísame si deseas añadirle fecha límite, prioridad, descripción o etiquetas.' o bien 'Ya he creado X. Si quieres te puedo recordar qué más información le puedes añadir.'\n"
    "- Ejemplo para asignaturas/proyectos: 'He añadido la asignatura X. Si quieres, avísame si deseas configurarle horas semanales, asociarla a un periodo o si te recuerdo qué más datos puedes añadirle.'\n"
    "- CRÍTICO: Habla SIEMPRE en lenguaje cotidiano y amigable. NUNCA uses nombres técnicos de variables ni código (evita estrictamente términos como 'due_date', 'tags', 'weekly_hours_goal', 'priority', etc.).\n"
    
    "REGLA DE CAMPOS ENRIQUECIDOS DE ASIGNATURAS:\n"
    "Las asignaturas tienen campos adicionales que puedes guardar y consultar de forma natural:\n"
    "- Descripción: guárdala con edit_subject cuando el usuario describa de qué trata la asignatura (ej: 'Matemáticas son álgebra lineal y cálculo').\n"
    "- Criterios de evaluación: guárdalos con edit_subject cuando el usuario mencione cómo le evalúan (ej: '60% examen final, 40% prácticas', 'hay un parcial y un examen final'). NUNCA llames al parámetro 'evaluation_criteria' al usuario; dile 'criterios de evaluación' o 'cómo te evalúan'.\n"
    "- Anotaciones: guárdalas con edit_subject cuando el usuario haga un comentario personal sobre una asignatura (ej: 'Matemáticas me encanta', 'el profe de Física explica muy bien', 'Historia se me da fatal'). NUNCA llames al parámetro 'notes' al usuario; dile 'tus anotaciones' o 'tus comentarios'.\n"
    
    "IMPORTANTE: Guarda proactivamente estos datos si el usuario los menciona de pasada, aunque no lo haya pedido explícitamente. Por ejemplo, si dice 'Tengo Matemáticas, me encanta', crea la asignatura y guarda 'me encanta' como anotación directamente.\n"
    
    "REGLA DE ESTADOS DE TAREAS Y CRONÓMETROS:\n"
    "Las tareas pueden estar en 3 estados: ACTIVE (ACTIVA), PENDING (PENDIENTE)  y COMPLETED (COMPLETADA).\n"
    "Cuando el usuario indique que va a ponerse a trabajar o estudiar en una tarea (ej: 'estoy trabajando en la tarea X', 'voy a hacer X ahora', 'empieza a contar tiempo para X'): "
    "debes usar start_timer especificando la asignatura (subject_name) y el título de la tarea (task_title). Esto iniciará el cronómetro en tiempo real y marcará automáticamente la tarea como ACTIVE .\n"
    "REGLA DE INFORME DE SESIÓN (STUDY REPORT):\n"
    "Cuando registres una sesión de estudio mediante cualquiera de estas acciones:\n"
    "  a) Parar un cronómetro con stop_timer\n"
    "  b) Registrar horas manualmente con log_study_hours\n"
    "  c) Registrar una entrada manual con log_time_entry\n"
    "...en tu respuesta final al usuario:\n"
    "1. Confirma brevemente y de forma natural que la sesión ha quedado registrada.\n"
    "2. Pregunta si quiere registrar cómo le fue la sesión. Sé breve y natural, como si fuera parte del mismo chat.\n"
    "Ejemplo: '¡Listo! He apuntado la sesión. ¿Qué tal te ha ido? Si quieres, podemos apuntar brevemente cómo fue.'\n"
    "REGLA DE SESIONES NO REGISTRADAS (el usuario menciona que estudió sin haber usado el timer):\n"
    "Si el usuario menciona que ha estado estudiando (ej: 'hoy he estado toda la mañana con el TFG', "
    "'estuve 3 horas estudiando Física'), NO des consejos de bienestar ni respondas como si fuera una charla. "
    "Tu rol aquí es académico: pregúntale si quiere registrar esa sesión. "
    "Si confirma, usa log_study_hours (si solo menciona duración) o log_time_entry (si menciona hora de inicio y fin). "
    "Una vez registrada, confirma brevemente y pregunta si quiere apuntar cómo le fue (el seguimiento del informe lo hará otro asistente).\n"
    "IMPORTANTE: NO menciones a ningún 'compañero', 'asistente de bienestar' ni otros agentes. Para el usuario solo existe un único chat.\n"
    "NUNCA intentes tú mismo guardar el informe de sesión.\n"
    "REGLA DE PLANES DE ESTUDIO:\n"
    "NO tienes acceso a las herramientas de modificar, crear o analizar planes de estudio. "
    "Si el usuario quiere ver su plan de estudio, alterar horas (ej. 'ponme 5h hoy para Matemáticas'), "
    "mover fechas ('pásalo al viernes') o crear un plan nuevo, confírmaselo amigablemente y el sistema "
    "lo redirigirá al Agente Planificador automáticamente.\n"
    "REGLA DE TAREAS SUELTAS VS. PLAN DE ESTUDIO:\n"
    "Cambiar la fecha o prioridad de UNA tarea suelta fuera de un plan general sí puedes hacerlo tú usando edit_task.\n"
    "REGLA CRÍTICA DE ACCIÓN INMEDIATA TRAS CONFIRMACIÓN:\n"
    "Si en el turno anterior el agente ha propuesto hacer algo (revisar tareas, ajustar fechas, borrar algo...) "
    "y el usuario responde con una confirmación corta (ej: 'Sí', 'Sí, adelante', 'Vale', 'Ok', 'Claro', 'Hazlo', 'Perfecto', 'Vamos', 'Venga'), "
    "DEBES ACTUAR INMEDIATAMENTE usando las herramientas necesarias.\n"
    "PROHIBIDO: volver a explicar la situación, pedir confirmación por segunda vez, reformular la propuesta o hacer más preguntas antes de actuar.\n"
    "La única excepción es si para ejecutar la acción te falta un dato imprescindible que el usuario no ha proporcionado en ningún mensaje anterior "
    "(ej: una fecha concreta que no aparece en el historial). En ese caso, haz UNA única pregunta concreta para obtenerlo y ya."
)

PLANNER_CONV_PROMPT = (
    "Eres el Agente Planificador de estudio. Tu función es ayudar al usuario a crear, modificar "
    "y reorganizar su plan de estudio de forma inteligente y personalizada. Eres 100% autónomo. Responde siempre en español.\n"
    "HERRAMIENTAS DISPONIBLES:\n"
    "  - `get_planner_analytics`: Devuelve tendencias reales de estudio (mejor/peor día, horas por asignatura, "
    "sesiones nocturnas) y el estado del plan (progreso y actividades retrasadas). Úsala para analizar la situación antes de reorganizar fechas.\n"
    "  - `get_active_study_plan`: Devuelve el plan activo con el índice, día, fecha de vencimiento y horas de cada actividad.\n"
    "  - `reschedule_plan_item`: Cambia la fecha y/o las horas de UNA actividad del plan (por su índice). Actualiza a la vez la actividad y las tareas vinculadas.\n"
    "  - `create_study_plan`: Crea un plan nuevo (reemplaza el activo).\n"
    "  - `get_tasks` / `edit_task`: Consulta y edita tareas concretas.\n"
    "FLUJO DE TRABAJO (Razonamiento ReAct):\n"
    "1. EDICIONES SIMPLES: Si el usuario pide un cambio claro y directo (ej: 'Ponme 5 horas hoy al TFG', 'Mueve lo de mañana al viernes'), "
    "usa `get_active_study_plan` para localizar el índice de la actividad afectada, y luego llama directamente a `reschedule_plan_item`. No necesitas analíticas profundas para esto.\n"
    "2. REORGANIZACIÓN O REVISIÓN AUTOMÁTICA: Si el mensaje del sistema indica 'SISTEMA: REVISIÓN DIARIA AUTOMÁTICA' o el usuario dice "
    "'estoy agobiado, ajusta mi plan':\n"
    "   a) Llama a `get_planner_analytics` para ver cuántas tareas están vencidas y cuáles son sus mejores días de rendimiento.\n"
    "   b) Con esos datos, usa `reschedule_plan_item` para mover lo vencido/pospuesto al día adecuado (nunca a un día pasado) o reducir horas irreales.\n"
    "   c) Redacta un resumen final al usuario.\n"
    "REGLAS ESTRICTAS:\n"
    "  - NUNCA uses fechas pasadas. La fecha de hoy aparece en el contexto del sistema del mensaje.\n"
    "  - Los EXÁMENES y las ENTREGAS tienen fecha fija: nunca los reprogrames por tu cuenta (ni en la revisión diaria ni al reorganizar por agobio), "
    "aunque aparezcan como vencidos. Solo puedes cambiarlos si el usuario te lo pide de forma explícita y concreta. "
    "Si una herramienta responde BLOQUEADO, respeta el bloqueo y no lo menciones como movido.\n"
    "  - IMPORTANTE: NO menciones a ningún 'compañero', 'otro agente' ni otros sistemas. Para el usuario solo existe un único chat.\n"
)

WELLBEING_PROMPT = (
    "Eres un asistente empático y comprensivo especializado en bienestar y salud mental para estudiantes. "
    "Tu objetivo es escuchar al usuario, validar cómo se siente (estrés, cansancio, falta de motivación) y "
    "ofrecerle consejos prácticos y amigables para mejorar su estado de ánimo y descansar. "
    "No eres un profesional médico, así que prioriza consejos de estilo de vida, pausas activas o técnicas de relajación.\n"
    "Tienes acceso a herramientas que te permiten guardar y obtener información sobre los hábitos y "
    "estado de ánimo del usuario. Recuerda usar estas herramientas para ofrecerle un servicio más "
    "personalizado y útil.\n"
    "REGLA DE INFORME DE SESIÓN DE ESTUDIO (STUDY REPORT):\n"
    "Si en el historial reciente hay un mensaje que menciona que se ha registrado una sesión de estudio "
    "(parar un cronómetro, registrar horas manualmente, etc.), es TU TURNO de recoger ese informe.\n"
    "Sigue estas instrucciones AL PIE DE LA LETRA y sin excepciones:\n"
    "1. Empieza de forma conversacional y empática. Pregunta UNA o DOS cosas como mucho. "
    "   Ejemplo: '¿Qué tal te ha ido la sesión? ¿Conseguiste lo que te habías propuesto?'\n"
    "2. ESPERA a que el usuario responda antes de hacer más preguntas. NUNCA respondas tú solo por él.\n"
    "3. A medida que el usuario responde, extrae los datos que mencione de forma natural:\n"
    "   - Calidad de la sesión (del 1 al 5, siendo 5 excelente)\n"
    "   - Si consiguió sus objetivos y cuáles eran\n"
    "   - Si hubo distracciones y cuáles\n"
    "   - Si hizo descansos y cuántos\n"
    "   - Cómo se siente ahora (estado de ánimo antes/después)\n"
    "   - Cualquier observación libre\n"
    "4. Ve haciendo UNA o DOS preguntas por turno, avanzando según lo que el usuario haya respondido ya. "
    "   NUNCA hagas todas las preguntas de golpe.\n"
    "5. CUÁNDO llamar a wb_add_study_report — CRITERIO ESTRICTO:\n"
    "   - SOLO llama a wb_add_study_report cuando se cumpla UNA de estas dos condiciones:\n"
    "     a) El usuario ha indicado explícitamente que ya no quiere añadir más ('ya está', 'es todo', 'no quiero más', etc.)\n"
    "     b) Ya has preguntado sobre calidad de sesión, objetivos y distracciones/descansos, y el usuario ha respondido a todas.\n"
    "   - NUNCA llames a wb_add_study_report en el mismo turno en que haces una pregunta.\n"
    "   - NUNCA llames a wb_add_study_report si el usuario aún no ha respondido a la pregunta anterior.\n"
    "6. REGLA CRÍTICA — NUNCA INVENTES DATOS:\n"
    "   - Solo incluye en wb_add_study_report los campos que el usuario haya mencionado EXPLÍCITAMENTE.\n"
    "   - Si el usuario no ha dado un valor para un campo (p.ej. no dijo cuántos descansos hizo), ese campo va como None/vacío.\n"
    "   - NUNCA asumas, deduzcas ni rellenes valores que el usuario no ha dicho. Si no lo dijo, va vacío.\n"
    "7. Si el usuario dice que no quiere rellenar el informe, que está ocupado o que no le apetece, respeta su decisión. "
    "   Llama a wb_add_study_report pasando solo el clockify_time_entry_id y el subject_name. El resto vacío.\n"
    "8. NUNCA uses los nombres técnicos de los parámetros al hablar con el usuario "
    "   (no digas 'study_quality', 'goals_achieved', 'breaks_taken', 'mood_before', etc.). "
    "   Habla siempre en lenguaje cotidiano y empático.\n"
    "9. El clockify_time_entry_id es OBLIGATORIO. Siempre estará disponible en el campo "
    "   [DATOS_SESION: clockify_time_entry_id=XXX] del mensaje actual. Extráelo de ahí. NUNCA lo inventes ni uses wb_get_latest_time_entry.\n"
    "REGLA DE INFORME DE BIENESTAR DIARIO:\n"
    "1. Si el contexto del sistema indica que el usuario AÚN NO ha registrado sus horas de sueño hoy, "
    "   aprovecha tu intervención para preguntarle de forma cálida y conversacional cuántas horas durmió hoy y cómo se siente.\n"
    "2. Rellena el informe POCO A POCO: haz UNA o DOS preguntas por turno, sin pedirlo todo de golpe "
    "(empieza por las horas de sueño; después calidad del descanso, estado de ánimo y energía).\n"
    "3. Tras CADA respuesta del usuario con datos nuevos, aunque sean parciales, llama EN ESE MISMO TURNO a `wb_add_wellbeing_report` "
    "pasando SOLO los datos que acaba de dar (la herramienta los va añadiendo al informe de hoy) y después pregunta por lo que falta. "
    "Ejemplo: 'he dormido bien' → guarda ya la calidad del descanso (muy mal=1, mal=2, regular=3, bien=4, muy bien=5) y pregunta cuántas horas fueron. "
    "No repitas datos ya guardados.\n"
    "4. El resultado de la herramienta indica qué datos faltan: úsalo para decidir la siguiente pregunta. "
    "Cuando el informe esté completo, o el usuario no quiera dar más, deja de preguntar.\n"
    "5. NUNCA inventes valores: usa solo lo que el usuario haya dicho (escala 1-5; por ejemplo, 'me siento con energía' → energía alta). "
    "Si el informe de hoy ya está completo, NO vuelvas a preguntar por el sueño ni por el ánimo.\n"
    "6. PRIORIDAD: mientras el informe de hoy esté incompleto, tu ÚNICA pregunta es la que lo completa. "
    "No menciones el plan de estudio ni fechas de tareas, ni ofrezcas reorganizar nada, aunque el contexto del sistema lo sugiera; eso se tratará más tarde. "
    "NUNCA afirmes cosas sobre las tareas del usuario (si las terminó, cuándo, etc.) que no te haya dicho él.\n"
    "IMPORTANTE: Si el usuario empieza a hablar de otra cosa (bienestar general, estrés, sueño), atiende también eso, "
    "pero intenta cerrar el informe primero si es posible."
)

GENERAL_PROMPT = (
    "Eres un asistente amigable y conversacional. Responde cordialmente a los saludos. "
    "Si el usuario pregunta qué puedes hacer o pide ayuda, usa SIEMPRE la herramienta "
    "get_agent_capabilities para obtener la lista real de funciones disponibles y explícasela "
    "de forma amigable, sin inventarte nada. "
    "Si necesita ayuda con estudios, recomiéndale hablar de asignaturas o tiempos de estudio. "
    "Si se siente estresado, ofrécete a escucharle. "
    "IMPORTANTE: Tú NO dispones de herramientas para crear, modificar o eliminar asignaturas, tareas ni registros de tiempo. "
    "Si el usuario responde 'sí' o te pide una acción sobre sus estudios, NUNCA afirmes haber realizado la acción ni simules haber borrado nada."
)

ADVISOR_PROMPT = (
    "Eres un asesor experto y empático en hábitos de estudio, rendimiento académico y bienestar estudiantil.\n"
    "Tu tarea es analizar la respuesta propuesta por el agente principal y la información en la base de datos del usuario (asignaturas, tiempos de estudio, hábitos, informes de bienestar y estudio) para determinar si es oportuno añadir una recomendación proactiva y personalizada al final de la respuesta.\n"
    "REGLA DE SILENCIO OBLIGATORIA — CUÁNDO RESPONDER SOLO 'NO_ADVICE':\n"
    "Responde ÚNICAMENTE 'NO_ADVICE' (sin texto adicional) en CUALQUIERA de estos casos:\n"
    "   - El usuario acaba de marcar/completar/crear/modificar/eliminar una tarea.\n"
    "   - El usuario ha hecho una acción puntual y simple (registrar tiempo, cambiar estado, actualizar datos).\n"
    "   - El usuario ha saludado o ha hecho una pregunta informativa concreta.\n"
    "   - Ya se ha dado algún consejo en los últimos 5 intercambios del chat.\n"
    "   - No detectas un patrón problemático claro y significativo en los datos.\n"
    "   - El último mensaje del usuario es una confirmación corta ('sí', 'vale', 'ok', 'claro', 'vamos', 'adelante', "
    "'perfecto', 'hazlo', o similar) en respuesta a una propuesta o pregunta del agente. "
    "El usuario está confirmando una acción en curso: NO interrumpas el flujo con un consejo.\n"
    "   - La respuesta del agente principal ya contiene una propuesta activa, está guiando al usuario hacia una acción "
    "concreta, o hace una pregunta de seguimiento. En ese caso SIEMPRE NO_ADVICE.\n"
    "Solo actúa (añade consejo) cuando el contexto sea una conversación larga o reflexiva Y detectes un patrón real y urgente.\n"
    "PATRONES CLAVE A ANALIZAR (solo cuando NO aplique la regla de silencio):\n"
    "1. DESEQUILIBRIO ENTRE ASIGNATURAS: Usa los DATOS ACADÉMICOS proporcionados para comparar el tiempo dedicado a cada asignatura. Si notas que una asignatura acumula casi todo el tiempo mientras otra asignatura activa tiene 0 horas o está desatendida, aconseja redistribuir el tiempo.\n"
    "2. HORARIOS NOCIVOS (ESTUDIO EN MADRUGADA): Revisa en los PATRONES y sesiones proporcionados los horarios de inicio de las sesiones de estudio. Si detectas sesiones entre las 00:00 y las 06:00 AM, advierte con empatía sobre los riesgos para el descanso, la retención y la salud mental.\n"
    "3. SESIONES DISPERSAS O FRAGMENTADAS: Si ves múltiples entradas cortas e intermitentes sin bloques de trabajo enfocado, sugiere la técnica Pomodoro o definir bloques claros de estudio.\n"
    "4. TENDENCIA DE AGOTAMIENTO Y FATIGA: Correlaciona la baja concentración de los DATOS ACADÉMICOS con los datos de BIENESTAR (pocas horas de sueño, bajo estado de ánimo). Si detectas fatiga acumulada o mal descanso, aconseja pausas de recuperación activa.\n"
    "REGLAS DE ACTUACIÓN:\n"
    "1. SOLO LECTURA: No tienes herramientas; trabajas únicamente con los datos que se te proporcionan en el mensaje. NUNCA inventes datos ni llamadas a herramientas.\n"
    "2. SELECCIÓN DE CONSEJOS: Sé breve, conciso, oportuno y muy valioso. Da recomendaciones basadas en patrones reales observados en sus datos. NUNCA hables de tareas pendientes de forma proactiva si el usuario no lo ha pedido.\n"
    "3. CONTROL DE REPETICIONES DE CONSEJOS:\n"
    "   - NUNCA repitas el mismo consejo que ya se le haya dado al usuario previamente en la misma sesión o conversación reciente.\n"
    "   - Si el patrón que detectas es equivalente a uno recién comentado, responde únicamente 'NO_ADVICE' para no agobiar ni resultar repetitivo.\n"
    "   - Si el problema persiste y exige recordarlo de nuevo, resúmelo al máximo en 1 sola frase sintética usando una transición corta (ej: 'Como te comenté antes, recuerda...').\n"
    "4. FORMATO Y FLUIDEZ DE LA RESPUESTA:\n"
    "   - NUNCA incluyas separadores gráficos, guiones horizontales ('---') ni etiquetas HTML/div.\n"
    "   - Introduce la recomendación de forma natural, fluida y cercana justo a continuación del mensaje anterior, usando una frase de transición amigable (ej: 'Por cierto, te sugiero...', 'Como consejo rápido...', ' Un pequeño consejo:...').\n"
    "5. LÍMITE ESTRICTO DE CONTENIDO — UNA SOLA IDEA:\n"
    "   - Por mensaje solo puedes aportar UNA recomendación. NUNCA hagas listas, ni des dos consejos distintos en el mismo mensaje.\n"
    "   - Máximo 2-3 frases en total. Si necesitas más, es porque estás hablando de demasiadas cosas a la vez: elige solo la más relevante.\n"
    "   - NUNCA hagas preguntas al usuario. Tu rol es exclusivamente aportar un consejo puntual, no iniciar una conversación ni pedir información adicional.\n"
)


COMMON_RULES = (
    "\nREGLA OBLIGATORIA DE FORMATO — PROHIBICIÓN DE USAR IDs TÉCNICOS EN TUS RESPUESTAS:\n"
    "NUNCA muestres ni le leas al usuario IDs técnicos internos de la base de datos o de Clockify "
    "(como cadenas alfanuméricas de identificadores '65a...', '68b...', IDs de sesiones, IDs de tareas, IDs de proyectos, IDs de informes, etc.). "
    "Aunque las herramientas o el contexto del sistema incluyan identificadores como ID o clockify_time_entry_id, "
    "debes ignorar esos IDs al redactar tu mensaje final. Refiérete SIEMPRE a los elementos por su nombre, título, asignatura, "
    "fecha u hora de forma 100% natural, cercana e inteligible para una persona.\n"

    "REGLA DE COHESIÓN Y CONCISIÓN:\n"
    "- NUNCA hagas más de una pregunta en el mismo mensaje. Si necesitas preguntar algo, elige la pregunta más importante y deja el resto para después.\n"
    "- NUNCA mezcles varias sugerencias, preguntas y confirmaciones en un mismo mensaje. Cada mensaje debe tener un único propósito claro.\n"
    "- Si tienes que confirmar una acción Y hacer una pregunta de seguimiento, prioriza la confirmación; la pregunta puede esperar al siguiente turno.\n"
    "-Si estás complementando un mensaje y en este ya aparece una pregunta, no añadas otra.\n"

    "MUY IMPORTANTE: Recuerda hablar tal y como se explica en esta configuración, aunque el usuario no lo pida explícitamente. "
    "Además, tienes que tener en cuenta siempre esta configuración, aunque en mensajes previos del chat siguiera un flujo de conversación distinto, ya que el usuario puede cambiar de tema y de rol de asistente en cualquier momento. "

)

academic_agent.set_system_instruction(ACADEMIC_PROMPT + COMMON_RULES)
wellbeing_agent.set_system_instruction(WELLBEING_PROMPT + COMMON_RULES)
general_agent.set_system_instruction(GENERAL_PROMPT + COMMON_RULES)
if hasattr(advisor_agent, "set_system_instruction"):
    advisor_agent.set_system_instruction(ADVISOR_PROMPT + COMMON_RULES)
if hasattr(planner_agent, "set_system_instruction"):
    planner_agent.set_system_instruction(PLANNER_CONV_PROMPT + COMMON_RULES)


langgraph_service = LangGraphService(
    academic_agent=academic_agent,
    wellbeing_agent=wellbeing_agent,
    general_agent=general_agent,
    advisor_agent=advisor_agent,
    planner_agent=planner_agent,
    orchestrator=orchestrator,
    mcp_client=mcp_client,
    db_service=db_service,
    analytics_service=analytics_service
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await mcp_client.connect()
    await db_service.ensure_indexes() 

    global GLOBAL_TOOLS_SCHEMA
    for tool in mcp_client.tools:
        schema = dict(tool.inputSchema) if tool.inputSchema else {}
        if "properties" in schema and "user_id" in schema["properties"]:
            props = dict(schema["properties"])
            del props["user_id"]
            schema["properties"] = props
            if "required" in schema and "user_id" in schema["required"]:
                reqs = list(schema["required"])
                reqs.remove("user_id")
                schema["required"] = reqs
        GLOBAL_TOOLS_SCHEMA.append({
            "name": tool.name,
            "description": tool.description or f"Ejecutar {tool.name}",
            "parameters": schema
        })

    print(f"[STARTUP] Servidor MCP conectado. {len(GLOBAL_TOOLS_SCHEMA)} herramientas cargadas.", file=sys.stderr)

    yield
    await mcp_client.disconnect()
    db_service.client.close()



app = FastAPI(title="TFG Bienestar", lifespan=lifespan)

# ESQUEMA DE SEGURIDAD
security = HTTPBearer()

async def get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Token inválido: falta el usuario")
        return user_id
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="El token ha caducado. Vuelve a iniciar sesión.")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Token inválido o corrupto.")


async def get_timer_context(user_id: str, db_service: DatabaseService) -> str:
    cached = _timer_context_cache.get(user_id)
    if cached and time.monotonic() - cached[0] < TIMER_CACHE_TTL:
        return cached[1]

    result_context = ""
    try:
        clockify_creds = await db_service.get_clockify_credentials(user_id)
        if not clockify_creds or not clockify_creds.get("api_key"):
            _timer_context_cache[user_id] = (time.monotonic(), result_context)
            return result_context
        
        cs = ClockifyService(
            api_key=clockify_creds["api_key"],
            workspace_id=clockify_creds.get("workspace_id")
        )
        active = await asyncio.to_thread(cs.get_active_time_entry)
        if not active:
            _timer_context_cache[user_id] = (time.monotonic(), result_context)
            return result_context
        
        desc = active.get("description", "sin descripción")
        start_raw = active.get("timeInterval", {}).get("start", "")
        start_str = start_raw
        elapsed_str = ""
        if start_raw:
            try:
                from zoneinfo import ZoneInfo
                start_dt = datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
                local_dt = start_dt.astimezone(ZoneInfo("Europe/Madrid"))
                start_str = local_dt.strftime("%H:%M")
                
                now_dt = datetime.now(ZoneInfo("Europe/Madrid"))
                elapsed_seconds = max(0, (now_dt - local_dt).total_seconds())
                elapsed_mins = int(elapsed_seconds // 60)
                if elapsed_mins >= 60:
                    hrs = elapsed_mins // 60
                    mins = elapsed_mins % 60
                    elapsed_str = f" (lleva {hrs}h {mins}m activo)"
                else:
                    elapsed_str = f" (lleva {elapsed_mins} minutos activo)"
            except Exception:
                start_str = start_raw

        result_context = (
            f"\n[CONTEXTO DEL SISTEMA: El usuario tiene un cronómetro activo "
            f"iniciado a las {start_str} (hora local de España){elapsed_str} para '{desc}'. "
            f"Si es relevante para la conversación, puedes mencionarlo o recordárselo al usuario.]"
        )
    except Exception:
        pass

    _timer_context_cache[user_id] = (time.monotonic(), result_context)
    return result_context

 
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"], 
    allow_methods=["*"], 
    allow_headers=["*"], 
)

##################################################################
# ESTRUTURAS DE DATOS PARA SOLICITAR DATOS AL CLIENTE
##################################################################
class ChatRequest(BaseModel):
    message: str

class LoginRequest(BaseModel):
    email: str
    password: str

class RegisterRequest(BaseModel):
    email: str
    name: str
    password: str
    role: str = "student" 

class ProactiveGreetingRequest(BaseModel):
    is_login: Optional[bool] = False
    force_onboarding: Optional[bool] = False

class ClockifyCredentialsRequest(BaseModel):
    api_key: Optional[str] = None
    workspace_id: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_payload(cls, data):
        if isinstance(data, dict):
            key = data.get("api_key") or data.get("apiKey") or data.get("token")
            if not key:
                raise ValueError("Se requiere la clave API de Clockify (api_key, apiKey o token).")
            data["api_key"] = key
        return data

class SubjectGradeRequest(BaseModel):
    grade: float

class CreateCourseRequest(BaseModel):
    name: str
    description: Optional[str] = None
    academic_year: Optional[str] = None 

class UpdateCourseRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    academic_year: Optional[str] = None
    is_active: Optional[bool] = None

class EnrollCourseRequest(BaseModel):
    code: str
    subject_id: Optional[str] = None


##################################################################
def get_datetime_context() -> str:
    try:
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo("Europe/Madrid"))
    except Exception:
        now = datetime.now().astimezone()
    dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    dia_semana = dias[now.weekday()]
    mes = meses[now.month - 1]
    fecha_str = f"{dia_semana}, {now.day} de {mes} de {now.year}"
    hora_str = now.strftime("%H:%M")
    return f"\n[CONTEXTO DEL SISTEMA: La fecha y hora actual es {fecha_str} a las {hora_str}. Usa este dato si el usuario te pregunta qué día es hoy o para calcular fechas límite de tareas.]"


async def get_daily_check_context(user_id: str, db_service: DatabaseService, analytics_service: AnalyticsService) -> str:
    context_parts = []
    try:
        from zoneinfo import ZoneInfo
        today_str = datetime.now(ZoneInfo("Europe/Madrid")).strftime("%Y-%m-%d")
    except Exception:
        today_str = datetime.now().strftime("%Y-%m-%d")

    try:
        has_today_report = await db_service.has_wellbeing_report_for_date(user_id, today_str)
        if not has_today_report:
            context_parts.append(
                f" Hoy ({today_str}) el usuario AÚN NO ha registrado sus horas de sueño en el informe de bienestar (wb_add_wellbeing_report). "
                f"Aprovecha tu respuesta para preguntarle de forma cálida cuántas horas ha dormido hoy "
                f"y cómo se siente para poder registrar su informe de bienestar."
            )
    except Exception as e:
        import sys
        print(f"[ERROR][DAILY CHECK] Error comprobando informe de hoy: {e}", file=sys.stderr)

    if _plan_alert_shown.get(user_id) != today_str:
        cached = _plan_alert_cache.get(user_id)
        if cached and time.monotonic() - cached[0] < PLAN_ALERT_TTL:
            plan_context = cached[1]
        else:
            plan_context = ""
            try:
                if analytics_service:
                    plan_progress = await analytics_service.get_study_plan_progress(user_id, days=7)
                    if plan_progress and plan_progress.get("has_active_plan") and plan_progress.get("has_overdue_tasks"):
                        overdue_list = plan_progress.get("overdue_tasks", [])
                        overdue_details = []
                        for ot in overdue_list:
                            status_label = "pendiente/sin terminar" if ot.get("status") == "INCUMPLIDA_PENDIENTE" else f"completada con retraso ({ot.get('completed_at')})"
                            overdue_details.append(f"• '{ot.get('title')}' ({ot.get('subject_name')}, venció: {ot.get('due_date')}, estado: {status_label})")

                        plan_context = (
                            f" ⚠️ ALERTAS DE INCUMPLIMIENTO/DESVÍO DEL PLAN: Se han detectado tareas no completadas dentro del plazo del plan o retrasadas: "
                            f"[{'; '.join(overdue_details)}]. "
                            f"Si es oportuno, comenta con empatía este retraso y ofrécele reorganizar el plan (solo si no vas a hacer ya otra pregunta en el mismo mensaje)."
                        )
            except Exception as e:
                import sys
                print(f"[ERROR][DAILY CHECK] Error comprobando alertas del plan activo: {e}", file=sys.stderr)

            _plan_alert_cache[user_id] = (time.monotonic(), plan_context)

        if plan_context:
            context_parts.append(plan_context)
            _plan_alert_shown[user_id] = today_str

    if not context_parts:
        return ""
    
    return f"\n[CONTEXTO DE INICIO DE DÍA / PLANIFICACIÓN: {''.join(context_parts)}]"


@app.post("/api/chat")
async def handle_chat(request: ChatRequest, user_id: str = Depends(get_current_user_id)):
    try:
        history_msgs = await db_service.get_history(user_id=user_id, limit=10)

        user_msg = await db_service.insert_message(
            user_id=user_id, 
            role="user", 
            content=request.message
        )

        date_context = get_datetime_context()
        timer_context = await get_timer_context(user_id, db_service)
        daily_context = await get_daily_check_context(user_id, db_service, analytics_service)
        message_with_context = request.message + date_context + timer_context + daily_context

        tools_raw = GLOBAL_TOOLS_SCHEMA

        result = await langgraph_service.run(
            user_id=user_id,
            user_message=request.message,
            message_with_context=message_with_context,
            history_msgs=history_msgs,
            tools_raw=tools_raw
        )

        response_text = result["response"]
        domain = result["agent_used"]

        assistant_msg = await db_service.insert_message(
            user_id=user_id,
            role="assistant",
            content=response_text,
            agent_used=domain
        )
        return {
            "response": response_text,
            "agent_used": domain,
            "timestamp": assistant_msg.get("timestamp")
        }

    except Exception as e:
        import sys
        print(f"[ERROR][CHAT] Error crítico en handle_chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))
 

@app.post("/api/chat/proactive-greeting")
async def get_proactive_greeting(
    request: Optional[ProactiveGreetingRequest] = None,
    user_id: str = Depends(get_current_user_id)
):
    is_force_onboarding = request.force_onboarding if request else False
    tools_raw = GLOBAL_TOOLS_SCHEMA

    result = await langgraph_service.run_proactive_greeting(
        user_id=user_id,
        tools_raw=tools_raw,
        is_force_onboarding=is_force_onboarding
    )

    response_text = result["response"]
    agent_used = result["agent_used"]

    greeting_msg = await db_service.insert_message(
        user_id=user_id,
        role="assistant",
        content=response_text,
        agent_used=agent_used
    )

    return {
        "response": response_text,
        "agent_used": agent_used,
        "timestamp": greeting_msg.get("timestamp")
    }

@app.post("/api/study-plan/daily-review")
async def trigger_daily_study_plan_review(
    user_id: str = Depends(get_current_user_id)
):
    tools_raw = GLOBAL_TOOLS_SCHEMA
    result = await langgraph_service.run_daily_plan_review(user_id, tools_raw, force=True)
    return result

@app.post("/api/login")
async def login(request: LoginRequest):
    user = await db_service.get_user_by_email(request.email)
    if not user or not verify_password(request.password, user["password"]):
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos")
    
    token = create_token(str(user["_id"]), user["email"])
    return {"token": token, "user": {"email": user["email"], "name": user["name"]}}

@app.post("/api/register")
async def register(request: RegisterRequest):
    existing = await db_service.get_user_by_email(request.email)
    if existing:
        raise HTTPException(status_code=400, detail="Ya existe una cuenta con ese email")
    
    role = request.role if request.role in ("student", "teacher") else "student"
    hashed = hash_password(request.password)
    user = await db_service.create_user(request.email, request.name, hashed, role=role)
    return {"message": "Usuario creado correctamente", "user_id": user["_id"]}

@app.get("/api/chat/history")
async def get_chat_history(
    user_id: str = Depends(get_current_user_id),
    limit: int = 30,
    skip: int = 0
):
    messages = await db_service.get_history(user_id=user_id, limit=limit, skip=skip)
    has_more = len(messages) == limit
    return {"history": messages, "has_more": has_more}

@app.post("/api/chat/reset")
async def reset_chat(user_id: str = Depends(get_current_user_id)):
    academic_agent.clear_history()
    wellbeing_agent.clear_history()
    general_agent.clear_history()
    planner_agent.clear_history()
    if hasattr(advisor_agent, "clear_history"):
        advisor_agent.clear_history()
    orchestrator.classifier.clear_history()
    
    deleted_count = await db_service.clear_history(user_id)
    
    return {
        "message": "Conversación reiniciada correctamente", 
        "deleted_messages": deleted_count
    }

@app.post("/api/user/clockify-credentials")
async def set_clockify_credentials(request: ClockifyCredentialsRequest, user_id: str = Depends(get_current_user_id)):
    try:
        clockify_user = await ClockifyService.validate_api_key(request.api_key)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    clockify_user_id = clockify_user.get("id")
    default_workspace_id = request.workspace_id or clockify_user.get("defaultWorkspace")

    existing_user = await db_service.get_user_by_clockify_id_or_key(
        clockify_user_id=clockify_user_id,
        api_key=request.api_key,
        exclude_user_id=user_id
    )
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Esta cuenta de Clockify ya está vinculada a otro usuario en la plataforma."
        )

    await db_service.update_clockify_credentials(
        user_id=user_id,
        api_key=request.api_key,
        workspace_id=default_workspace_id,
        clockify_user_id=clockify_user_id
    )

    return {
        "message": "Cuenta de Clockify vinculada correctamente",
        "connected": True,
        "workspace_id": default_workspace_id,
        "clockify_user_id": clockify_user_id,
    }

@app.get("/api/user/clockify-status")
async def get_clockify_status(user_id: str = Depends(get_current_user_id)):
    user = await db_service.get_user_by_id(user_id)
    if not user or not user.get("clockify"):
        return {"connected": False}
    
    cdata = user["clockify"]
    return {
        "connected": True,
        "workspace_id": cdata.get("workspace_id"),
        "updated_at": cdata.get("updated_at")
    }

@app.get("/api/user/me")
async def get_user_me(user_id: str = Depends(get_current_user_id)):
    user = await db_service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return {
        "email": user.get("email"),
        "name": user.get("name"),
        "role": user.get("role", "student")
    }

@app.post("/api/subjects/{subject_id}/grades")
async def update_grade(subject_id: str, request: SubjectGradeRequest, user_id: str = Depends(get_current_user_id)):
    success = await db_service.update_subject_grade(subject_id, request.grade)
    if not success:
        raise HTTPException(status_code=404, detail="Asignatura no encontrada")
    return {"message": "Nota actualizada correctamente", "grade": request.grade}

@app.get("/api/dashboard/student-analytics")
async def get_student_analytics(
    days: int = 7,
    user_id: str = Depends(get_current_user_id)
):
    try:
        return await analytics_service.get_full_dashboard_analytics(user_id, days)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al generar analíticas: {str(e)}")

@app.get("/api/analytics/summary")
async def get_analytics_summary(days: int = 7, user_id: str = Depends(get_current_user_id)):
    try:
        return await analytics_service.get_user_analytics(user_id, days=days)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al generar analíticas: {str(e)}")

@app.post("/api/share/generate")
async def generate_share_code(user_id: str = Depends(get_current_user_id)):
    code = await db_service.generate_share_code(user_id)
    return {"code": code}

@app.post("/api/share/follow")
async def follow_user(body: dict, user_id: str = Depends(get_current_user_id)):
    code = body.get("code", "").strip()
    shared_user = await db_service.get_user_by_share_code(code)
    if not shared_user:
        raise HTTPException(status_code=404, detail="Código no encontrado")
    shared_user_id = str(shared_user["_id"])
    if shared_user_id == user_id:
        raise HTTPException(status_code=400, detail="No puedes añadirte a ti mismo")
    await db_service.add_followed_user(user_id, shared_user_id)
    return {"name": shared_user.get("name"), "user_id": shared_user_id, "email": shared_user.get("email", "")}

@app.get("/api/share/followed")
async def get_followed(user_id: str = Depends(get_current_user_id)):
    followed = await db_service.get_followed_users(user_id)
    return {"followed": followed}

@app.get("/api/share/{target_user_id}/analytics")
async def get_shared_analytics(
    target_user_id: str,
    days: int = 7,
    user_id: str = Depends(get_current_user_id)
):
    if target_user_id != user_id:
        followed = await db_service.get_followed_users(user_id)
        ids = [f["user_id"] for f in followed]
        if target_user_id not in ids:
            raise HTTPException(status_code=403, detail="Sin acceso")
    try:
        return await analytics_service.get_full_dashboard_analytics(target_user_id, days)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al generar analíticas: {str(e)}")

@app.get("/api/user/share-code")
async def get_my_share_code(user_id: str = Depends(get_current_user_id)):
    user = await db_service.get_user_by_id(user_id)
    code = user.get("share_code") if user else None
    if not code:
        code = await db_service.generate_share_code(user_id)
    return {"code": code}

@app.delete("/api/share/followed/{target_user_id}")
async def unfollow_user(
    target_user_id: str, 
    user_id: str = Depends(get_current_user_id)
):
    await db_service.remove_followed_user(user_id, target_user_id)
    return {"status": "ok", "message": "Has dejado de seguir al usuario."}

@app.get("/api/share/followers")
async def get_followers(user_id: str = Depends(get_current_user_id)):
    followers = await db_service.get_followers(user_id)
    return {"followers": followers}

@app.delete("/api/share/followers/{follower_id}")
async def revoke_follower(
    follower_id: str, 
    user_id: str = Depends(get_current_user_id)
):
    await db_service.remove_follower(user_id, follower_id)
    return {"status": "ok", "message": "Acceso revocado correctamente."}


##################################################################
# TAGS ENDPOINTS
##################################################################
HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")

class TagColorRequest(BaseModel):
    name: str
    color: Optional[str] = None

class TagRenameRequest(BaseModel):
    old_name: str
    new_name: str

@app.get("/api/tags")
async def get_tags(user_id: str = Depends(get_current_user_id)):
    return {"tags": await db_service.get_all_tags(user_id)}

@app.post("/api/tags")
async def set_tag_color(req: TagColorRequest, user_id: str = Depends(get_current_user_id)):
    if req.color is not None and not HEX_COLOR_RE.match(req.color):
        raise HTTPException(status_code=400, detail="Color inválido (se espera formato #RRGGBB)")
    try:
        doc = await db_service.upsert_user_tag(user_id, req.name, req.color)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "ok", "tag": {"name": doc["name"], "color": doc["color"]}}

@app.delete("/api/tags")
async def delete_tag_color(name: str, user_id: str = Depends(get_current_user_id)):
    await db_service.delete_user_tag(user_id, name)
    return {"status": "ok"}

@app.post("/api/tags/merge-duplicates")
async def merge_duplicate_tags(user_id: str = Depends(get_current_user_id)):
    merged = await db_service.merge_duplicate_tags(user_id)
    return {"status": "ok", "merged": merged}

@app.put("/api/tags/rename")
async def rename_tag(req: TagRenameRequest, user_id: str = Depends(get_current_user_id)):
    try:
        new_name = await db_service.rename_tag(user_id, req.old_name, req.new_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "ok", "name": new_name}


##################################################################
# COURSES ENDPOINTS
##################################################################
@app.post("/api/courses")
async def create_course(
    request: CreateCourseRequest,
    user_id: str = Depends(get_current_user_id)
):
    course = await db_service.create_course(
        teacher_id=user_id,
        name=request.name,
        description=request.description,
        academic_year=request.academic_year
    )
    return course

@app.get("/api/courses/teaching")
async def get_teaching_courses(user_id: str = Depends(get_current_user_id)):
    return {"courses": await db_service.get_courses_by_teacher(user_id)}

@app.get("/api/courses/enrolled")
async def get_enrolled_courses(user_id: str = Depends(get_current_user_id)):
    return {"courses": await db_service.get_enrolled_courses(user_id)}

@app.get("/api/courses/{course_id}")
async def get_course(
    course_id: str,
    user_id: str = Depends(get_current_user_id)
):
    course = await db_service.get_course_by_id(course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Curso no encontrado")
    if user_id not in course.get("teacher_ids", []) and user_id not in course.get("student_ids", []):
        raise HTTPException(status_code=403, detail="Sin acceso a este curso")
    return course

@app.patch("/api/courses/{course_id}")
async def update_course(
    course_id: str,
    request: UpdateCourseRequest,
    user_id: str = Depends(get_current_user_id)
):
    course = await db_service.get_course_by_id(course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Curso no encontrado")
    if user_id not in course.get("teacher_ids", []):
        raise HTTPException(status_code=403, detail="Solo el profesor puede editar el curso")
    fields = {k: v for k, v in request.model_dump().items() if v is not None}
    if fields:
        await db_service.update_course(course_id, **fields)
    return {"message": "Curso actualizado"}

@app.delete("/api/courses/{course_id}")
async def delete_course(
    course_id: str,
    user_id: str = Depends(get_current_user_id)
):
    course = await db_service.get_course_by_id(course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Curso no encontrado")
    if user_id not in course.get("teacher_ids", []):
        raise HTTPException(status_code=403, detail="Solo el profesor puede eliminar el curso")
    await db_service.delete_course(course_id)
    return {"message": "Curso eliminado"}

@app.get("/api/subjects/unlinked")
async def get_unlinked_subjects(user_id: str = Depends(get_current_user_id)):
    subjects = await db_service.get_subjects_by_user(user_id)
    return {"subjects": [{"id": str(s["_id"]), "name": s["name"]} for s in subjects if not s.get("course_id")]}

@app.get("/api/courses/check/{code}")
async def check_course_code(code: str, user_id: str = Depends(get_current_user_id)):
    course = await db_service.get_course_by_enrollment_code(code.strip())
    if not course:
        raise HTTPException(status_code=404, detail="Código de curso no válido")
    if user_id in course.get("student_ids", []):
        raise HTTPException(status_code=400, detail="Ya estás matriculado en este curso")
    return {"id": str(course["_id"]), "name": course["name"], "academic_year": course.get("academic_year", "")}

@app.post("/api/courses/enroll")
async def enroll_in_course(
    request: EnrollCourseRequest,
    user_id: str = Depends(get_current_user_id)
):
    code = request.code.strip()
    course = await db_service.get_course_by_enrollment_code(code)
    if not course:
        raise HTTPException(status_code=404, detail="Código de curso no válido")

    course_id = str(course["_id"])
    if user_id in course.get("student_ids", []):
        raise HTTPException(status_code=400, detail="Ya estás matriculado en este curso")

    subject = None
    if request.subject_id:
        subject = await db_service.get_subject_by_id(request.subject_id)
        if subject and str(subject.get("user_id")) == user_id:
            await db_service.update_subject(request.subject_id, course_id=course_id)
        else:
            subject = None

    if not subject:
        clockify_project_id = ""
        try:
            clockify_creds = await db_service.get_clockify_credentials(user_id)
            if clockify_creds and clockify_creds.get("api_key"):
                cs = ClockifyService(
                    api_key=clockify_creds["api_key"],
                    workspace_id=clockify_creds.get("workspace_id")
                )
                project = await asyncio.to_thread(cs.add_new_project, course["name"])
                clockify_project_id = project.get("id", "")
        except Exception as e:
            pass

        subject = await db_service.create_subject(
            user_id=user_id,
            name=course["name"],
            clockify_project_id=clockify_project_id,
            course_id=course_id
        )

    await db_service.add_student_to_course(course_id, user_id)
    return {"subject": subject, "course_name": course["name"]}

@app.delete("/api/courses/{course_id}/leave")
async def leave_course(
    course_id: str,
    user_id: str = Depends(get_current_user_id)
):
    course = await db_service.get_course_by_id(course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Curso no encontrado")
    if user_id not in course.get("student_ids", []):
        raise HTTPException(status_code=400, detail="No estás matriculado en este curso")
    await db_service.remove_student_from_course(course_id, user_id)
    return {"message": "Desmatriculado correctamente"}

@app.get("/api/courses/{course_id}/students")
async def get_course_students(
    course_id: str,
    user_id: str = Depends(get_current_user_id)
):
    course = await db_service.get_course_by_id(course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Curso no encontrado")
    if user_id not in course.get("teacher_ids", []):
        raise HTTPException(status_code=403, detail="Solo el profesor puede ver esta lista")

    students = []
    for sid in course.get("student_ids", []):
        u = await db_service.get_user_by_id(sid)
        students.append({
            "user_id": sid,
            "name": u.get("name", "Estudiante") if u else "Estudiante",
            "email": u.get("email", "") if u else "",
        })
    return {"students": students, "course": course}


##################################################################
# GLOBAL ANALYTICS ENDPOINTS
##################################################################
GLOBAL_SUMMARY_PROMPT = (
    "Eres un sistema automático de análisis de datos educativos. "
    "Tu única función es generar, de forma INMEDIATA y DIRECTA, un párrafo analítico de 4 a 5 frases sobre las estadísticas de una clase. "
    "INSTRUCCIONES DE FORMATO — OBLIGATORIAS: "
    "Tu respuesta debe comenzar DIRECTAMENTE con el análisis, sin saludos, sin introducción, sin Hola, sin !Claro!. "
    "NO hagas preguntas al usuario. NO ofrezcas opciones ni listes lo que puedes hacer. "
    "NO uses listas con viñetas ni bullet points: solo texto en prosa continua. "
    "NO menciones a ningún alumno individual ni uses nombres propios de alumnos. "
    "Habla siempre del conjunto: la clase, el grupo, los alumnos en general. "
    "Usa un tono profesional, objetivo y conciso. Responde siempre en español. "
    "CONTENIDO que debe incluir el análisis: "
    "La media de horas de estudio y su relación con la nota media. "
    "Qué porcentaje de alumnos aprueba y si se correlaciona con las horas dedicadas. "
    "Observaciones sobre concentración y sueño del grupo. "
    "Una conclusión general útil para el profesor. "
    "EJEMPLO DE RESPUESTA VALIDA (sigue exactamente este estilo sin saludos ni preguntas): "
    "La clase dedica de media X horas al estudio, lo que se traduce en una nota media de Y. "
    "El Z porciento de los alumnos supera el aprobado, cifra que coincide con el porcentaje que estudia más de W horas. "
    "La concentración media del grupo es de C sobre 5, y las horas de sueño promedio son S. "
    "En general, existe una correlación positiva entre el tiempo de estudio y el rendimiento académico."
)

@app.get("/api/courses/{course_id}/global-analytics")
async def get_course_global_analytics(
    course_id: str,
    user_id: str = Depends(get_current_user_id)
):
    course = await db_service.get_course_by_id(course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Curso no encontrado")
    if user_id not in course.get("teacher_ids", []):
        raise HTTPException(status_code=403, detail="Solo el profesor puede acceder a las estadísticas globales")
        
    return {
        "stats": await analytics_service.get_course_global_analytics(course_id),
        "global_summary": course.get("global_summary"),
        "global_summary_generated_at": course.get("global_summary_generated_at")
    }

@app.post("/api/courses/{course_id}/global-summary")
async def generate_global_course_summary(
    course_id: str,
    user_id: str = Depends(get_current_user_id)
):
    course = await db_service.get_course_by_id(course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Curso no encontrado")
    if user_id not in course.get("teacher_ids", []):
        raise HTTPException(status_code=403, detail="Solo el profesor puede generar resúmenes globales")
        
    global_stats = await analytics_service.get_course_global_analytics(course_id)
    if not global_stats:
        raise HTTPException(status_code=400, detail="No hay datos suficientes para generar un resumen")

    n = len(global_stats)
    hours_list = [s['hours'] for s in global_stats if s.get('hours') is not None]
    conc_list  = [s['avg_concentration'] for s in global_stats if s.get('avg_concentration') is not None]
    sleep_list = [s['avg_sleep'] for s in global_stats if s.get('avg_sleep') is not None]
    grade_list = [s['grade'] for s in global_stats if s.get('grade') is not None]

    def _avg(lst): return round(sum(lst) / len(lst), 2) if lst else None
    def _mn(lst):  return round(min(lst), 2) if lst else None
    def _mx(lst):  return round(max(lst), 2) if lst else None
    def _pct_above(lst, threshold): return round(100 * sum(1 for v in lst if v >= threshold) / len(lst)) if lst else None

    lines = [
        f"Total de alumnos: {n}",
        f"Horas de estudio → media: {_avg(hours_list)} h | mín: {_mn(hours_list)} h | máx: {_mx(hours_list)} h",
        f"Concentración   → media: {_avg(conc_list)}/5 | mín: {_mn(conc_list)}/5 | máx: {_mx(conc_list)}/5",
        f"Horas de sueño  → media: {_avg(sleep_list)} h | mín: {_mn(sleep_list)} h | máx: {_mx(sleep_list)} h",
        f"Nota            → media: {_avg(grade_list)} | mín: {_mn(grade_list)} | máx: {_mx(grade_list)}",
        f"Alumnos que dedican ≥5 h de estudio: {_pct_above(hours_list, 5)}%",
        f"Alumnos con nota aprobatoria (≥5): {_pct_above(grade_list, 5)}%",
        f"Alumnos con concentración ≥3/5: {_pct_above(conc_list, 3)}%",
        f"Alumnos con ≥7 h de sueño: {_pct_above(sleep_list, 7)}%",
    ]
    formatted_text = "ESTADÍSTICAS AGREGADAS DE LA CLASE (no se incluyen datos individuales):\n" + "\n".join(lines)
    
    try:
        if ACTIVE_MODEL == "gemini":
            agent = GeminiService()
        else:
            agent = OpenAIService()
        agent.set_system_instruction(GLOBAL_SUMMARY_PROMPT)
        result = await agent.chat_with_mcp_async(formatted_text)
        summary_text = result.text if hasattr(result, "text") else str(result)
        
        generated_at = datetime.now(timezone.utc).isoformat()
        await db_service.update_course(course_id, global_summary=summary_text, global_summary_generated_at=generated_at)
        
        return {"summary": summary_text, "generated_at": generated_at}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generando resumen: {str(e)}")