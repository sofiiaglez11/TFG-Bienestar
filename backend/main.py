from asyncio import queues
import asyncio
import os
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
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



# Servicios de MCP y de la Base de DAtos
db_service = DatabaseService()
analytics_service = AnalyticsService(db_service)
mcp_client = MCPClientService()


ACTIVE_MODEL = os.getenv("LLM_PROVIDER", "gemini")

orchestrator = AgentOrchestrator(provider=ACTIVE_MODEL)

if ACTIVE_MODEL == "gemini":
    academic_agent = GeminiService()
    wellbeing_agent = GeminiService()
    general_agent = GeminiService()
    advisor_agent = GeminiService()
elif ACTIVE_MODEL == "openai":
    academic_agent = OpenAIService()
    wellbeing_agent = OpenAIService()
    general_agent = OpenAIService()
    advisor_agent = OpenAIService()

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

    "FORMATO OBLIGATORIO DE TABLAS DE TAREAS:\n"
    "Al responder al usuario para mostrar sus tareas, usa SIEMPRE tablas Markdown con EXACTAMENTE estas 5 columnas y en este orden estricto:\n"
    "| Estado | Prioridad | Tarea | Fecha | Etiquetas |\n"
    "Reglas estrictas de formato para cada columna:\n"
    "1. Columna 'Estado': Usa ÚNICAMENTE el emoji correspondiente, NUNCA agregues texto de la palabra del estado:\n"
    "   - ⚡ (para tareas activas o en progreso)\n"
    "   - ⏳ (para tareas pendientes)\n"
    "   - ✅ (para tareas completadas)\n"
    "2. Columna 'Prioridad': Escribe el número entre corchetes rectos, ej: [1], [2], [3]. Si no tiene prioridad, escribe '-'.\n"
"   3. Columna 'Tarea': Escribe solo el nombre de la tarea. Si necesitas añadir una descripción aclaratoria, escríbela en la línea de abajo dentro de la misma celda usando un salto de línea normal. NUNCA uses etiquetas HTML como <br> ni <br/>. Pon la descripción entre paréntesis y en cursiva\n"    
    "4. Columna 'Fecha':\n"
    "   - Formato de fecha: usa SIEMPRE el formato DD/MM/YYYY (ej: 10/03/2026, o DD/MM/YYYY HH:MM si tiene hora).\n"
    "   - Resaltado en rojo (!DD/MM/YYYY!): Pon la fecha entre signos de exclamación !DD/MM/YYYY! ÚNICAMENTE si el campo `overdue` de la tarea es true. Si overdue es false, NUNCA uses exclamaciones aunque la fecha parezca pasada.\n"
    "   - Tareas completadas o no vencidas: Si la tarea ya se ha completado (✅) o si overdue=false, NO la pongas en rojo ni uses signos de exclamación; escríbela de forma normal: DD/MM/YYYY.\n"
    "   - Si no tiene fecha de vencimiento, escribe '-'.\n"
"   5. Columna 'Etiquetas': Escribe CADA etiqueta en su propio par de corchetes rectos independientes y separados por espacios, ej: [backend] [frontend]. NUNCA agrupes varias etiquetas en el mismo corchete separado por comas como [backend, frontend]. Si no tiene etiquetas, escribe '-'.\n"    "6. Organización: Si muestras varias asignaturas, crea un título en negrita por cada asignatura (ej: **Matemáticas**) y debajo su respectiva tabla.\n"
    "7. Cuándo mostrar completadas: Si el usuario no especifica, muéstrale las activas y pendientes; si pide ver todas o completadas, incluye también las completadas.\n\n"
    "Ejemplo de formato requerido:\n"
    "| Estado | Prioridad | Tarea | Fecha | Etiquetas |\n"
    "| :---: | :---: | :--- | :---: | :--- |\n"
    "| ⚡ | [1] | Entrega Proyecto Final | !10/03/2026! | [Práctica]  |\n"
    "| ⏳ | [2] | ↳ Redactar conclusiones | 20/06/2026 | [Memoria] [Teoría] |\n"
    "| ✅ | [3] | Repaso de teoría | 15/01/2026 | [Teoría] |\n\n"

    "Al final de CADA tabla de tareas añade EXACTAMENTE esta leyenda, una sola vez y sin modificarla: (⚡ En progreso, ⏳ Pendiente, ✅ Completada). NUNCA la pongas dos veces ni uses un texto diferente.\n"
    "Tampoco menciones que las fechas vencidas están entre exclamaciones, ya que eso el usuario no lo ve (las ve de color rojo).\n"


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
    "Las tareas pueden estar en 3 estados: ACTIVE (representada en tabla con ⚡), PENDING (con ⏳) y COMPLETED (con ✅).\n"
    "Cuando el usuario indique que va a ponerse a trabajar o estudiar en una tarea (ej: 'estoy trabajando en la tarea X', 'voy a hacer X ahora', 'empieza a contar tiempo para X'): "
    "debes usar start_timer especificando la asignatura (subject_name) y el título de la tarea (task_title). Esto iniciará el cronómetro en tiempo real y marcará automáticamente la tarea como ACTIVE ⚡.\n"
    "Además, para guardar un registro de tiempo, primero tienes que revisar"
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
    "REGLA DE CREACIÓN Y SEGUIMIENTO DE PLANES DE ESTUDIO:\n"
    "Cuando el usuario te pida ayuda para organizarse o estructurar sus días/semana de estudio (ej: 'ayúdame a organizarme', 'cómo distribuyo mi semana'):\n"
    "1. Proponle un plan claro estructurado por días, asignaturas/bloques temáticos y tareas concretas a realizar (puedes basarte en horas o en tareas con fecha de vencimiento).\n"
    "2. Cuando el usuario acepte o confirme la propuesta (ej: 'me parece bien', 'guárdalo', 'confirmo el plan'), ejecuta la herramienta `create_study_plan` mapeando tu propuesta en la lista 'items' (cada item con day, subject_name, planned_hours, description/tarea y asignándole siempre la fecha de vencimiento adecuada `due_date` en formato YYYY-MM-DD según la planificación).\n"
    "3. Si el usuario pregunta qué plan tiene activo o qué le toca estudiar según su plan, utiliza la herramienta `get_active_study_plan`.\n"
    "4. Si el contexto del sistema incluye alertas por tareas vencidas o no completadas dentro del plan, avisa al usuario con empatía sobre el desvío de su planificación para ayudarle a reajustar sus tareas a tiempo."
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
    "2. Cuando el usuario proporcione sus horas de sueño, usa la herramienta `wb_add_wellbeing_report` para registrar la fecha de hoy, sus horas de sueño (`sleep_hours`) y los demás datos que haya compartido.\n"
    "IMPORTANTE: Si el usuario empieza a hablar de otra cosa (bienestar general, estrés, sueño), atiende también eso, "
    "pero intenta cerrar el informe primero si es posible."
)



# GENERAL_PROMPT = (
#     "Eres un asistente amigable y conversacional. Responde cordialmente a los saludos y "
#     "preguntas generales. Si el usuario necesita ayuda con sus estudios, recomiéndale hablar de sus asignaturas "
#     "o tiempos de estudio; y si se siente estresado o cansado, ofrécete a escucharle y ayudarle con su bienestar."
# )

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
    "PATRONES CLAVE A ANALIZAR CON TUS HERRAMIENTAS DE CONSULTA:\n"
    "1. DESEQUILIBRIO ENTRE ASIGNATURAS: Usa 'list_subjects' y 'get_time_summary' para comparar el tiempo dedicado a cada asignatura. Si notas que una asignatura acumula casi todo el tiempo mientras otra asignatura activa tiene 0 horas o está desatendida, aconseja redistribuir el tiempo.\n"
    "2. SEGUIMIENTO PROACTIVO DE TAREAS PENDIENTES / NO TRATADAS EN EL DÍA: Si en la conversación actual del día NO se ha hablado de tareas y el estudiante tiene tareas pendientes (PENDING) o activas (ACTIVE) o próximas a vencer, pregúntale amigablemente cómo las lleva, si ha podido avanzar en alguna o si necesita ayuda para ponerse a trabajar en ellas.\n"
    "3. HORARIOS NOCIVOS (ESTUDIO EN MADRUGADA): Usa 'get_time_entries' para revisar los horarios de inicio de las sesiones de estudio. Si detectas sesiones entre las 00:00 y las 06:00 AM, advierte con empatía sobre los riesgos para el descanso, la retención y la salud mental.\n"
    "4. SESIONES DISPERSAS O FRAGMENTADAS: Si ves múltiples entradas cortas e intermitentes sin bloques de trabajo enfocado, sugiere la técnica Pomodoro o definir bloques claros de estudio.\n"
    "5. TENDENCIA DE AGOTAMIENTO Y FATIGA: Correlaciona 'wb_get_study_reports' (fatiga, baja concentración) con 'wb_get_wellbeing_trends' / 'wb_get_wellbeing_report' (pocas horas de sueño, bajo estado de ánimo). Si detectas fatiga acumulada o mal descanso, aconseja pausas de recuperación activa.\n"
    "REGLAS DE ACTUACIÓN:\n"
    "1. SOLO LECTURA: Tienes acceso a herramientas de consulta para revisar datos del usuario. NUNCA intentes modificar, crear ni eliminar datos.\n"
    "2. SELECCIÓN DE CONSEJOS: Sé breve, conciso, oportuno y muy valioso. Da recomendaciones basadas en patrones reales observados en sus datos.\n"
    "3. CONTROL DE REPETICIONES DE CONSEJOS:\n"
    "   - NUNCA repitas el mismo consejo que ya se le haya dado al usuario previamente en la misma sesión o conversación reciente.\n"
    "   - Si el patrón que detectas es equivalente a uno recién comentado, responde únicamente 'NO_ADVICE' para no agobiar ni resultar repetitivo.\n"
    "   - Si el problema persiste y exige recordarlo de nuevo, resúmelo al máximo en 1 sola frase sintética usando una transición corta (ej: 'Como te comenté antes, recuerda...').\n"
    "4. FORMATO Y FLUIDEZ DE LA RESPUESTA:\n"
    "   - NUNCA incluyas separadores gráficos, guiones horizontales ('---') ni etiquetas HTML/div.\n"
    "   - Introduce la recomendación de forma natural, fluida y cercana justo a continuación del mensaje anterior, usando una frase de transición amigable (ej: 'Por cierto, te sugiero...', 'Como consejo rápido...', ' Un pequeño consejo:...').\n"
)


COMMON_RULES = (
    "\nREGLA OBLIGATORIA DE FORMATO — PROHIBICIÓN DE USAR IDs TÉCNICOS EN TUS RESPUESTAS:\n"
    "NUNCA muestres ni le leas al usuario IDs técnicos internos de la base de datos o de Clockify "
    "(como cadenas alfanuméricas de identificadores '65a...', '68b...', IDs de sesiones, IDs de tareas, IDs de proyectos, IDs de informes, etc.). "
    "Aunque las herramientas o el contexto del sistema incluyan identificadores como ID o clockify_time_entry_id, "
    "debes ignorar esos IDs al redactar tu mensaje final. Refiérete SIEMPRE a los elementos por su nombre, título, asignatura, "
    "fecha u hora de forma 100% natural, cercana e inteligible para una persona.\n"


    "MUY IMPORTANTE: Recuerda hablar tal y como se explica en esta configuración, aunque el usuario no lo pida explícitamente. "
    "Además, tienes que tener en cuenta siempre esta configuración, aunque en mensajes previos del chat siguiera un flujo de conversación distinto, ya que el usuario puede cambiar de tema y de rol de asistente en cualquier momento. "

)

academic_agent.set_system_instruction(ACADEMIC_PROMPT + COMMON_RULES)
wellbeing_agent.set_system_instruction(WELLBEING_PROMPT + COMMON_RULES)
general_agent.set_system_instruction(GENERAL_PROMPT + COMMON_RULES)
if hasattr(advisor_agent, "set_system_instruction"):
    advisor_agent.set_system_instruction(ADVISOR_PROMPT + COMMON_RULES)


langgraph_service = LangGraphService(
    academic_agent=academic_agent,
    wellbeing_agent=wellbeing_agent,
    general_agent=general_agent,
    advisor_agent=advisor_agent,
    orchestrator=orchestrator,
    mcp_client=mcp_client,
    db_service=db_service,
    analytics_service=analytics_service
)


# FastAPI lifespan: Manages startup and shutdown of the app
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Al arrancar la API, encendemos el "USB" del servidor MCP una sola vez
    await mcp_client.connect()
    await db_service.ensure_indexes()  # Aseguramos que los índices estén creados al iniciar la app

    yield
    # Al apagar la API, desconectamos el proceso de fondo de forma segura
    await mcp_client.disconnect()
    db_service.client.close()



app = FastAPI(title="TFG Bienestar", lifespan=lifespan)

# ESQUEMA DE SEGURIDAD
security = HTTPBearer()

async def get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """
    Coge el token de la cabecera, 
    verifica que sea válido y devuelve el ID del usuario.
    """
    token = credentials.credentials
    try:
        # Intentamos descifrar el token con nuestra clave secreta
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
    """Comprueba si hay un cronómetro activo en Clockify y devuelve contexto para el agente."""
    try:
        clockify_creds = await db_service.get_clockify_credentials(user_id)
        if not clockify_creds or not clockify_creds.get("api_key"):
            return ""
        
        cs = ClockifyService(
            api_key=clockify_creds["api_key"],
            workspace_id=clockify_creds.get("workspace_id")
        )
        active = await asyncio.to_thread(cs.get_active_time_entry)
        if not active:
            return ""
        
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
                
                # Calcular tiempo transcurrido
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

        return (
            f"\n[CONTEXTO DEL SISTEMA: El usuario tiene un cronómetro activo "
            f"iniciado a las {start_str} (hora local de España){elapsed_str} para '{desc}'. "
            f"Si es relevante para la conversación, puedes mencionarlo o recordárselo al usuario.]"
        )
    except Exception:
        return ""

 
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"], # Permitir solicitudes desde el frontend
    allow_methods=["*"], # Permitir todos los métodos HTTP
    allow_headers=["*"], # Permitir todos los encabezados
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
            # Normaliza api_key buscando variantes comunes
            key = data.get("api_key") or data.get("apiKey") or data.get("token")
            if not key:
                raise ValueError("Se requiere la clave API de Clockify (api_key, apiKey o token).")
            data["api_key"] = key
        return data

class SubjectGradeRequest(BaseModel):
    grade: float


##################################################################
def get_datetime_context() -> str:
    """Devuelve la fecha y hora actual formateada en español como contexto para el agente."""
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
    """
    Comprueba si hoy el usuario ha registrado su informe de bienestar (horas de sueño)
    y el estado de su plan de estudio activo para aportar contexto al agente.
    """
    context_parts = []
    try:
        from zoneinfo import ZoneInfo
        today_str = datetime.now(ZoneInfo("Europe/Madrid")).strftime("%Y-%m-%d")
    except Exception:
        today_str = datetime.now().strftime("%Y-%m-%d")

    # 1. Comprobar si ya existe informe de bienestar para hoy
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
        print(f"[DAILY CHECK] Error comprobando informe de hoy: {e}", file=sys.stderr)

    # 2. Comprobar únicamente si hay desvíos / tareas retrasadas en el plan activo
    try:
        if analytics_service:
            plan_progress = await analytics_service.get_study_plan_progress(user_id, days=7)
            if plan_progress and plan_progress.get("has_active_plan") and plan_progress.get("has_overdue_tasks"):
                overdue_list = plan_progress.get("overdue_tasks", [])
                overdue_details = []
                for ot in overdue_list:
                    status_label = "pendiente/sin terminar" if ot.get("status") == "INCUMPLIDA_PENDIENTE" else f"completada con retraso ({ot.get('completed_at')})"
                    overdue_details.append(f"• '{ot.get('title')}' ({ot.get('subject_name')}, venció: {ot.get('due_date')}, estado: {status_label})")
                
                context_parts.append(
                    f" ⚠️ ALERTAS DE INCUMPLIMIENTO/DESVÍO DEL PLAN: Se han detectado tareas no completadas dentro del plazo del plan o retrasadas: "
                    f"[{'; '.join(overdue_details)}]. "
                    f"Avisa al usuario con empatía sobre este retraso e incítale a reorganizarse, ya que no se está siguiendo el plan según lo previsto."
                )
    except Exception as e:
        import sys
        print(f"[DAILY CHECK] Error comprobando alertas del plan activo: {e}", file=sys.stderr)

    if not context_parts:
        return ""
    
    return f"\n[CONTEXTO DE INICIO DE DÍA / PLANIFICACIÓN: {''.join(context_parts)}]"


@app.post("/api/chat")
async def handle_chat(request: ChatRequest, user_id: str = Depends(get_current_user_id)):
    try:


        # Recuperamos los últimos 20 mensajes de historial del usuario para tener contexto de la conversación
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


        # Obtenemos la lista de herramientas disponibles en el MCP
        # y ocultamos el campo "user_id" para que la IA no se lo invente.
        tools_raw = []
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
                    
            tools_raw.append({
                "name": tool.name,
                "description": tool.description or f"Ejecutar {tool.name}",
                "parameters": schema
            })

    
        # Ejecución a través del flujo de LangGraph
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
        print(f"Error crítico en handle_chat: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
 

@app.post("/api/chat/proactive-greeting")
async def get_proactive_greeting(
    request: Optional[ProactiveGreetingRequest] = None,
    user_id: str = Depends(get_current_user_id)
):
    """
    Endpoint que genera el saludo proactivo adecuado a través del grafo de LangGraph:
    - Si es un usuario nuevo (o sin historial ni asignaturas): ejecuta onboarding_node (GENERAL)
    - Si es un usuario recurrente (inicio de sesión): ejecuta login_greeting_node (BIENESTAR)
    """
    is_force_onboarding = request.force_onboarding if request else False

    result = await langgraph_service.run_proactive_greeting(
        user_id=user_id,
        is_force_onboarding=is_force_onboarding
    )

    response_text = result["response"]
    agent_used = result["agent_used"]

    # Guardar el saludo en el historial de MongoDB
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
    
    hashed = hash_password(request.password)
    user = await db_service.create_user(request.email, request.name, hashed)
    return {"message": "Usuario creado correctamente", "user_id": user["_id"]}


@app.get("/api/chat/history")
async def get_chat_history(
    user_id: str = Depends(get_current_user_id),
    limit: int = 30,
    skip: int = 0
):
    """
    Devuelve los mensajes del historial del usuario desde MongoDB con paginación.
    """
    messages = await db_service.get_history(user_id=user_id, limit=limit, skip=skip)
    has_more = len(messages) == limit
    return {"history": messages, "has_more": has_more}


@app.post("/api/chat/reset")
async def reset_chat(user_id: str = Depends(get_current_user_id)):
    """
     Reinicia la memoria del bot en RAM y vacía la colección 
    'history' de este usuario en MongoDB.
    """
    academic_agent.clear_history()
    wellbeing_agent.clear_history()
    general_agent.clear_history()
    
    # Borramos también la persistencia en Mongo para este usuario
    deleted_count = await db_service.clear_history(user_id)
    
    return {
        "message": "Conversación reiniciada correctamente", 
        "deleted_messages": deleted_count
    }



@app.post("/api/user/clockify-credentials")
async def set_clockify_credentials(request: ClockifyCredentialsRequest, user_id: str = Depends(get_current_user_id)):
    """
    Valida la API Key de Clockify contra su API y, si es correcta, la guarda.
    """
    # 1. Validar la clave ANTES de guardar nada
    try:
        clockify_user = await ClockifyService.validate_api_key(request.api_key)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 2. La clave es válida → obtener workspace por defecto
    clockify_user_id = clockify_user.get("id")
    default_workspace_id = request.workspace_id or clockify_user.get("defaultWorkspace")

    # 3. Verificar que esta cuenta de Clockify no esté ya vinculada a otro usuario en la plataforma
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

    # 4. Guardar en base de datos
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
    """
    Devuelve el estado actual de la conexión del usuario con Clockify.
    """
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
        "name": user.get("name")
    }


@app.post("/api/subjects/{subject_id}/grades")
async def update_grade(subject_id: str, request: SubjectGradeRequest, user_id: str = Depends(get_current_user_id)):
    """
    Actualiza la nota de una asignatura concreta.
    """
    success = await db_service.update_subject_grade(subject_id, request.grade)
    if not success:
        raise HTTPException(status_code=404, detail="Asignatura no encontrada")
    return {"message": "Nota actualizada correctamente", "grade": request.grade}


@app.get("/api/dashboard/student-analytics")
async def get_student_analytics(user_id: str = Depends(get_current_user_id)):
    """
    Devuelve las analíticas agregadas para el dashboard del alumno:
    Cruza las horas dedicadas (desde Clockify) con las notas de cada asignatura.
    """
    try:
        subjects = await db_service.get_subjects_by_user(user_id)
        
        # Obtener periodo activo si lo hay
        active_period = await db_service.get_active_period(user_id)
        start_date = None
        end_date = None
        if active_period:
            start_date = active_period.get("start_date")
            end_date = active_period.get("end_date")

        # Obtener credenciales de Clockify del usuario
        clockify_creds = await db_service.get_clockify_credentials(user_id)
        
        # Obtener entradas de tiempo de Clockify
        clockify_entries = []
        if clockify_creds and clockify_creds.get("api_key"):
            try:
                import asyncio
                cs = ClockifyService(
                    api_key=clockify_creds["api_key"] or clockify_creds.get("token"),
                    workspace_id=clockify_creds.get("workspace_id")
                )
                if start_date or end_date:
                    clockify_entries = await asyncio.to_thread(
                        cs.get_time_entries, start_date=start_date, end_date=end_date
                    )
                else:
                    clockify_entries = await asyncio.to_thread(
                        cs.get_time_entries, days_back=365
                    )
            except Exception as e:
                # Loggear el error pero no fallar la petición completa
                print(f"Error fetching Clockify entries: {e}")
                clockify_entries = []

        # Agrupar segundos de Clockify por projectId
        project_seconds = {}
        for entry in clockify_entries:
            pid = entry.get("projectId")
            if not pid:
                continue
            start_iso = entry.get("start")
            end_iso = entry.get("end")
            if start_iso and end_iso:
                try:
                    dt1 = datetime.fromisoformat(start_iso.replace('Z', '+00:00'))
                    dt2 = datetime.fromisoformat(end_iso.replace('Z', '+00:00'))
                    seconds = (dt2 - dt1).total_seconds()
                    project_seconds[pid] = project_seconds.get(pid, 0.0) + seconds
                except Exception:
                    pass

        # Obtener analíticas de bienestar, patrones, métricas extendidas y desglose de tiempo
        wellbeing = {}
        patterns = {}
        study_plan = {}
        ext_metrics = {}
        time_breakdown = {}
        try:
            wellbeing = await analytics_service.get_wellbeing_analytics(user_id, days=7)
            patterns = await analytics_service.get_patterns(user_id, days=7)
            study_plan = patterns.get("study_plan_progress", {})
            ext_metrics = await analytics_service.get_extended_subject_metrics(user_id)
            time_breakdown = await analytics_service.get_time_breakdown(user_id, days=30)
        except Exception as e:
            print(f"[DASHBOARD] Error al calcular analíticas complementarias: {e}")

        # Obtener informes de estudio para medir concentración media por asignatura
        study_reports = []
        try:
            study_reports = await db_service.get_study_reports_by_user(user_id, limit=100)
        except Exception as e:
            pass

        analytics = []
        for subject in subjects:
            s_id = str(subject["_id"])
            s_name = subject.get("name", "Asignatura")
            clockify_project_id = subject.get("clockify_project_id")
            
            # Obtener segundos del proyecto desde Clockify
            seconds = 0.0
            if clockify_project_id and clockify_project_id in project_seconds:
                seconds = project_seconds[clockify_project_id]
                
            total_hours = round(seconds / 3600.0, 2)

            # Concentración media basada en informes de estudio
            s_name_clean = (s_name or "").lower().strip()
            subj_reports = [
                r for r in study_reports
                if (r.get("subject_name") or "").lower().strip() == s_name_clean and r.get("study_quality") is not None
            ]
            avg_conc = round(sum(r["study_quality"] for r in subj_reports) / len(subj_reports), 1) if subj_reports else None

            # Métricas extendidas por asignatura
            subj_ext = ext_metrics.get(s_id, {})
            last_week_tasks = subj_ext.get("last_week_tasks", {"total": 0, "completed": 0, "pending": 0})
            total_tasks_created = subj_ext.get("total_tasks_created", 0)
            total_tasks_completed = subj_ext.get("total_tasks_completed", 0)
            weekly_comp = subj_ext.get("weekly_comparison", {"current_week_hours": total_hours, "previous_week_hours": 0.0, "change_pct": 0.0})
            overdue_count = subj_ext.get("overdue_tasks_count", 0)
            overdue_list = subj_ext.get("overdue_tasks", [])
            neglected_count = subj_ext.get("neglected_tasks_count", 0)
            neglected_list = subj_ext.get("neglected_tasks", [])

            analytics.append({
                "id": s_id,
                "name": s_name,
                "hours": total_hours,
                "weekly_hours_goal": subject.get("weekly_hours_goal"),
                "grade": subject.get("grade"),
                "avg_concentration": avg_conc,
                "tasks_completed": total_tasks_completed,
                "tasks_pending": max(0, total_tasks_created - total_tasks_completed),
                "total_tasks_created": total_tasks_created,
                "last_week_tasks": last_week_tasks,
                "weekly_comparison": weekly_comp,
                "overdue_tasks_count": overdue_count,
                "overdue_tasks": overdue_list,
                "neglected_tasks_count": neglected_count,
                "neglected_tasks": neglected_list
            })
            
        return {
            "analytics": analytics,
            "wellbeing": wellbeing,
            "patterns": patterns,
            "study_plan": study_plan,
            "time_breakdown": time_breakdown
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al generar analíticas: {str(e)}")


@app.get("/api/analytics/summary")
async def get_analytics_summary(days: int = 7, user_id: str = Depends(get_current_user_id)):
    """
    Devuelve las métricas y resúmenes estadísticos agregados del usuario para los últimos `days` días.
    """
    try:
        return await analytics_service.get_user_analytics(user_id, days=days)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al generar analíticas: {str(e)}")