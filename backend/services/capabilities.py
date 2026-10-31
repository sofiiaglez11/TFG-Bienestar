"""
Descripción única y detallada de las funcionalidades del sistema.

Se usa en dos sitios para que la información nunca se desincronice:
  - server.py: la tool `get_agent_capabilities` (mensaje de ayuda / dudas del agente general).
  - langgraph_service.py: el mensaje de bienvenida (onboarding).

Si se añade o quita una funcionalidad, actualizar SOLO este texto.
"""

FEATURES_OVERVIEW = """\
FUNCIONALIDADES DEL SISTEMA (toda la información es real; no existe nada más aparte de lo listado):

== DESDE EL CHAT (se piden escribiendo con naturalidad) ==

1. ASIGNATURAS
- Crear una o varias asignaturas a la vez (ej: "tengo Matemáticas, Física e Historia").
- Guardar información de cada una: descripción, cómo se evalúa (ej: 60% examen final, 40% prácticas), anotaciones personales (ej: "el profe explica muy bien"), objetivo de horas semanales de estudio, fecha de inicio y de fin, y la nota (de 0 a 10).
- Archivar una asignatura (conserva todo su historial y se puede recuperar cuando quieras) o eliminarla definitivamente. Para eliminarla primero hay que archivarla y confirmar, porque es irreversible y borra también sus tareas y tiempos registrados.

2. TAREAS, EXÁMENES Y ENTREGAS
- Crear tareas con fecha límite (opcionalmente con hora), prioridad de 1 (máxima) a 5 (mínima), etiquetas, descripción y tipo (tarea, examen, entrega u otro). También subtareas dentro de otra tarea.
- Consultarlas por asignatura o todas a la vez, y filtrar por prioridad (ej: "qué tareas de prioridad 1 y 2 tengo"). Se muestran en una tabla con su estado (pendiente, activa o completada), las fechas vencidas resaltadas en rojo y las etiquetas de colores.
- Editar cualquier dato, marcarlas como activas o completadas, reorganizar la jerarquía (convertir tareas en subtareas) y borrarlas (siempre pidiendo confirmación antes).
- Ver cuánto has avanzado en cada asignatura (tareas completadas sobre el total).
- Los exámenes y las entregas tienen fecha fija: la planificación automática nunca los mueve; solo cambian si tú lo pides.

3. CONTROL DEL TIEMPO DE ESTUDIO (integrado con Clockify)
- Iniciar y parar un cronómetro en tiempo real para una asignatura o una tarea concreta (al iniciarlo, la tarea pasa a estar activa).
- Registrar sesiones que ya hiciste sin cronómetro, indicando solo las horas dedicadas o la hora de inicio y de fin (ej: "he estudiado 2 horas de Física").
- Consultar cuánto llevas con el cronómetro en marcha y cuánto tiempo has dedicado a cada asignatura o tarea, corregir una sesión ya registrada o borrarla.
- Requiere tener la cuenta de Clockify vinculada (con la API Key) desde Configuración.

4. INFORME DE CADA SESIÓN DE ESTUDIO
- Al terminar una sesión, el asistente te pregunta brevemente cómo te fue: calidad de la concentración (1 a 5), si conseguiste tus objetivos, distracciones, descansos y cómo te sientes. Es totalmente opcional y puedes saltártelo. Estos datos alimentan tus estadísticas.

5. BIENESTAR
- Informe diario de bienestar: horas de sueño, calidad del descanso, estado de ánimo y nivel de energía. Se rellena poco a poco durante la conversación, sin formularios.
- Escucha y apoyo cuando estés estresado, cansado o desmotivado, con consejos prácticos de estilo de vida, pausas activas y relajación. No sustituye a un profesional de la salud.
- Consultar la evolución de tu bienestar y tus informes de sesiones anteriores.

6. PLAN DE ESTUDIO
- Crear un plan de estudio organizado por días y sesiones, con horas por asignatura, y vincular a cada sesión las tareas que cubre.
- Consultar qué te toca estudiar según el plan, y modificarlo con frases como "ponme 5 horas hoy a Matemáticas" o "pasa esto al viernes". También puedes decir "estoy agobiado, ajusta mi plan" y se reorganiza teniendo en cuenta tu ritmo real.
- Revisión diaria automática: si hay actividades atrasadas, el plan se reajusta solo (fechas y horas, según tus patrones de estudio) y se te avisa de lo que se ha movido. Nunca toca exámenes ni entregas.

7. CONSEJOS PERSONALIZADOS
- El asistente analiza tus datos y, cuando detecta algo relevante, te da un consejo puntual: desequilibrio entre asignaturas, estudiar de madrugada, sesiones muy fragmentadas, señales de fatiga acumulada...

== EN LA APLICACIÓN (pestañas y ajustes, fuera del chat) ==

- ESTADÍSTICAS (pestaña propia), con cuatro secciones: Asignaturas (horas, tareas, concentración media, nota, comparativa con la semana anterior y alertas de tareas vencidas o desatendidas), Desglose de tiempo (con filtros por asignatura y etiqueta), Bienestar y descanso (sueño, ánimo y energía por día) y Hábitos y patrones (horas por día y horario preferido de estudio). Se puede ver de los últimos 7 días, 30 días o el histórico.
- COMPARTIR ESTADÍSTICAS (Configuración > Estadísticas): cada usuario tiene un código para que sus compañeros puedan seguir sus estadísticas. También se puede seguir a otros con su código, dejar de seguirlos y revocar en cualquier momento el acceso a quien te sigue.
- ETIQUETAS (Configuración > Etiquetas): elegir el color de cada etiqueta de tus tareas y fusionar las que estén duplicadas.
- CURSOS (pestaña propia): como alumno te matriculas con el código que te da tu profesor (se crea o se vincula la asignatura correspondiente y tu progreso le llega de forma agregada). Como profesor creas cursos, compartes su código de matrícula y ves las estadísticas globales de la clase con un resumen generado por IA.
- CLOCKIFY (Configuración > Clockify): aquí se vincula tu cuenta con la API Key; sin ella no funcionan el cronómetro ni las estadísticas personales.
"""