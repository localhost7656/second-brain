# Segundo Cerebro — Especificación

[Русский](SPECIFICATION.ru.md) · [English](SPECIFICATION.en.md) · [Español](SPECIFICATION.es.md) · [Українська](SPECIFICATION.uk.md)

Versión del programa: **2.7.1**

Segundo Cerebro es un programa para Obsidian que organiza notas y pensamientos sueltos por proyectos y redacta documentos sobre ellos con ayuda de un modelo de lenguaje. El usuario deja archivos de texto en la carpeta de entrada de la bóveda. El programa determina a qué proyecto pertenece cada pensamiento, lo descompone en unidades de sentido, encuentra duplicados, contradicciones y material obsoleto, reúne para cada proyecto una "base de síntesis" y, a partir de ella, redacta documentos: el "Archivo resumen" («Сводный файл») obligatorio y otros, los que necesite precisamente ese material.

Este documento describe cómo está construido el programa y cómo funciona por dentro: qué decide el modelo, qué decide el código, qué decide la persona y por qué. Está pensado para quien quiera entender el programa, comprobar su comportamiento o ampliarlo. Cómo usar el programa paso a paso lo explica la guía `ИНСТРУКЦИЯ.md` en la carpeta del programa.

Convenciones:

- Los nombres de carpetas, archivos, campos YAML, comandos y valores aparecen en `monoespaciado`, exactamente como en el programa.
- Los umbrales se indican con sus valores por defecto. Todos se pueden cambiar en los ajustes (sección 17), y la mayoría también por separado para un contenedor.
- "Modelo", sin más, significa el modelo de lenguaje (LLM). El modelo de embeddings siempre se nombra completo.
- "Sección 6.4" es una referencia a una sección de este documento.
- Todos los proyectos y entradas de ejemplo son ficticios.
- La interfaz del programa, sus prompts y los nombres de las carpetas y archivos que crea están en ruso. En esta traducción, los textos de la interfaz se traducen y el original ruso se indica entre comillas angulares «…» cuando ayuda a encontrar un botón o un mensaje; los nombres de carpetas, archivos y campos se dejan tal cual, con su traducción la primera vez que aparecen.

## 1. Propósito y principios

### 1.1 Propósito

Una base de conocimiento personal para alguien con muchos proyectos e ideas entrelazados. Se puede anotar cualquier cosa en cualquier momento: un pensamiento breve, la exportación de una conversación con una IA, un diario de varios años. Nada se pierde y no hace falta tener la estructura en la cabeza: el programa se encarga de repartir el material por proyectos, relacionarlo y reunirlo en un texto coherente.

El programa es abierto y no está atado a un único modelo. El usuario elige el modelo de lenguaje: uno en la nube por API, uno propio en este ordenador o, de forma manual, a través de un chat web (sección 13). El objetivo es doble: asumir el complejo trabajo lógico con los proyectos y reducir la barrera de entrada para quienes no conocen Obsidian. Al mismo tiempo, el programa no se convierte en una "caja negra": el usuario entiende los principios básicos de su funcionamiento y siempre puede ver qué se hizo y por qué.

### 1.2 Principios

1. **Un único punto de entrada.** La información entra en el sistema solo a través de la carpeta `_staging` (sección 4). No hay atajo para ninguna fuente, así que toda entrada se procesa igual y deja el mismo rastro.
2. **Nada se borra.** Lo obsoleto, lo rechazado y lo duplicado se marca y sigue disponible (sección 11.1). Los archivos originales se guardan sin cambios.
3. **El modelo evalúa, el código decide, la persona confirma.** El modelo devuelve evaluaciones: confianza, valor, nivel de ruido. La decisión la toma el código comparando la evaluación con un umbral. Todo lo que queda por debajo del umbral y todo lo discutible se convierte en una pregunta para el usuario (sección 7). Allí donde un error costaría perder sentido, el modelo no decide nada por su cuenta.
4. **El texto de los pensamientos solo lo escribe la persona.** El modelo no reescribe entradas ni inventa pensamientos por el autor. Una entrada procesada no se edita: cambiar un pensamiento significa añadir una entrada nueva (sección 4.3). La versión condensada por el modelo se guarda aparte del texto original.
5. **La materia prima y el producto son cosas distintas.** De las entradas se extraen aspectos, unidades atómicas de sentido (sección 5). Con los aspectos seleccionados se arma la base de síntesis, y a partir de ella el modelo redacta documentos (sección 8): un texto coherente e independiente, no un resumen de los aspectos uno por uno. Igual que las fuentes de un trabajo de curso y el propio trabajo son cosas distintas.
6. **Todo se guarda en archivos normales.** Las entradas, las fichas de proyecto y los documentos son Markdown con encabezado YAML en la bóveda de Obsidian; los datos de trabajo son JSON en la carpeta oculta `.system`. No hace falta un servidor de bases de datos: la bóveda se copia y se sincroniza como una carpeta cualquiera.
7. **Solo se ejecuta por orden del usuario.** Las fases las inicia el usuario: sin programación horaria ni procesamiento en segundo plano. Interrumpir es seguro: tras cada paso se guarda el estado, y una nueva ejecución continúa desde el mismo punto (sección 11.3).
8. **La calidad importa más que ahorrar tokens.** Los prompts no se recortan para acortarlos. Si el material no cabe en la ventana del modelo, el código lo divide en partes. Los gastos se limitan en dinero: un presupuesto mensual y una estimación antes de una ejecución grande (sección 14).
9. **Privacidad por defecto.** Por defecto, los embeddings se calculan en este ordenador (sección 12). Las claves de API se guardan junto al programa, no en la bóveda, y no se sincronizan.
10. **Toda suposición se verifica.** Allí donde el sistema supone y la persona decide, el par "suposición — decisión" se anota en el registro de reflexión (sección 15.3). Con esta estadística se ajustan los umbrales (sección 10.5).

### 1.3 Componentes

- **El programa**: el paquete de Python `brain` en la carpeta del programa. Realiza todas las operaciones sobre la bóveda, llama a los modelos, hace preguntas y aplica las respuestas. Se ejecuta con comandos `python -m brain <comando>` (sección 20). Normalmente el usuario no lo necesita directamente: lo llama el plugin.
- **El plugin de Obsidian "Segundo Cerebro"** («Второй мозг», carpeta `.obsidian/plugins/vtoroy-mozg/`): el panel, la ventana de ajustes, los comandos y ventanas como "Nuevo pensamiento" («Новая мысль»). El plugin por sí mismo no modifica datos: lee la instantánea de estado `.system/ui.json` y ejecuta comandos del programa (sección 18).
- **La bóveda de Obsidian**: todos los datos del usuario y los datos de trabajo del programa (sección 3).
- **Modelos.** El modelo de lenguaje hace falta allí donde hay que comprender el texto (sección 13). El modelo de embeddings hace falta para buscar material parecido (sección 12). Por defecto es un modelo propio en este ordenador: KaLM-Embedding-Gemma3 12B sobre llama.cpp.
- **Prompts**: los textos de las tareas para el modelo, un archivo por paso, en la carpeta `prompts/` del programa (sección 9).
- **Ajustes**: el archivo `settings.yaml` junto al programa (sección 17).

Flujo general:

```
_staging/  — archivos nuevos
  │
  ▼  Fase 1 — procesamiento (python -m brain run)
  respuestas a preguntas → ediciones manuales → recepción de archivos (copia en _исходники)
  → [carga masiva: borrador de estructura → lo aprueba el usuario]
  → cada entrada: clasificación → umbrales → preguntas aclaratorias → condensación
                  → vectores → extracción de aspectos al pool del contenedor
  → cada contenedor modificado: análisis del pool → valor → armado de la base de síntesis
                  → comparación con la versión anterior de la base
  │
  ▼  Fase 2 — documentos (python -m brain synth "Contenedor")
  base de síntesis → síntesis de documentos → comparación con versiones anteriores → versión en .system/versions

Preguntas desde cualquier paso → open-questions.md y el panel del plugin →
la respuesta se aplica en el acto (desde el panel) o al inicio de la siguiente Fase 1 (desde el archivo)
```

## 2. Términos

Glosario de los conceptos del documento. Si una formulación del texto difiere de la definición de aquí, prevalece la definición.

| Término | Significado |
| --- | --- |
| **Bóveda** | La carpeta de Obsidian (vault) con la que trabaja el programa. Todos los datos están en ella (sección 3). |
| **Contenedor** (nodo) | Un nodo del grafo de proyectos de cualquier nivel: proyecto, subproyecto, brote de idea o pregunta. Físicamente, una carpeta con la ficha del contenedor, las entradas, los documentos y las vistas (sección 3.4). |
| **Ficha del contenedor** | El archivo `Nombre/Nombre.md`: las propiedades del contenedor en el encabezado YAML y el texto del usuario. |
| **Entrada** | Unidad de información que el programa procesa: un pensamiento, un fragmento de diario, un diálogo con una IA, un recurso, una edición manual de un documento, etc. Un archivo `.md` con encabezado YAML en `_записи/`, `_shared/`, `_unsorted/` o `_на_проверку/`. En el código y en los campos YAML: `entity`. |
| **Original** | Un archivo de entrada tal como se dejó en `_staging`. Se guarda sin cambios en `_исходники/` (originales); las entradas enlazan a él. |
| **Segmento** | Parte de un archivo de entrada que se convirtió en una entrada aparte durante una carga masiva (sección 6.4). Sus límites son números de párrafo; el código copia el texto del segmento literalmente y el modelo no lo reescribe. |
| **Encabezado de servicio** | Primeras líneas opcionales de un archivo de entrada: una fecha `dd.mm.aaaa` y una pista `hint: …` (sección 4.2). |
| **Pista** (`hint`) | Indicación del usuario sobre dónde clasificar la entrada. No dicta el resultado, sino que desplaza la confianza a favor de la opción indicada (sección 4.4). |
| **Fuente** (`source`) | De dónde vino la entrada: material de archivo, una nota, un chat con IA, etc. Se determina por la subcarpeta de `_staging`. Sirve para orientarse y desplaza el umbral de condensación; no influye en los pesos ni en la ordenación (sección 4.2). |
| **Aspecto** | Unidad atómica de sentido que el modelo extrae de una entrada: un hecho, una idea, un plan, etc. (sección 5). No se guarda en la entrada, sino en el pool de aspectos del contenedor, con un enlace a la entrada de origen. Es la unidad básica de cálculo: sobre los aspectos se construyen el valor, los duplicados, las contradicciones y la ordenación. |
| **Tipo simple de aspecto** | Uno de los ocho tipos fijos: `fact`, `observation`, `hypothesis`, `idea`, `conclusion`, `question`, `plan`, `judgment` (sección 5.1). |
| **Aspecto compuesto** | Un conjunto de varios aspectos simples de un mismo contenedor (no necesariamente de una misma entrada) que forma un todo: una experiencia, una decisión fundamentada, una bifurcación. Se arma según la fórmula de composición de su tipo (sección 5.2). |
| **Pool de aspectos** | Todos los aspectos simples y compuestos del contenedor con sus estados, valoraciones y vínculos de duplicados y contradicciones. Archivo `.system/data/pools/<id>.json` (sección 16.3). |
| **Valor de contenido** | Valoración de 0 a 100 de un aspecto en el contexto de todo el contenedor (prompt "Valor", «Ценность»). Primer eje de ordenación: con él los elementos se descartan y se dividen en principales y secundarios (sección 6.10). |
| **Tabla de prioridad** | El orden de los grupos de aspectos por tipo en la base de síntesis. Segundo eje de ordenación, independiente del primero (sección 5.4). |
| **Análisis del pool** | Una única llamada al modelo sobre todo el pool del contenedor: encuentra aspectos compuestos, duplicados, material obsoleto, contradicciones y propuestas de estructura (sección 6.10). |
| **Base de síntesis** | El resultado de la Fase 1 para un contenedor: aspectos seleccionados por valor, agrupados por tipo y ordenados, con marcas de contradicciones y bifurcaciones. La materia prima de los documentos (sección 6.10). |
| **Documento** (producto) | Un texto que la Fase 2 redacta a partir de la base de síntesis: el "Archivo resumen" obligatorio y documentos adicionales, cuyo conjunto decide el modelo (sección 8). |
| **Archivo resumen** («Сводный файл») | Documento obligatorio del contenedor: una descripción general del proyecto. |
| **Vista** | Los archivos `_аспекты.md` (aspectos) y `_база синтеза.md` (base de síntesis) en la carpeta del contenedor: el pool y la base de síntesis en forma legible. Son de solo lectura: el programa los reescribe por su cuenta. |
| **Fase 1** | Procesamiento: recepción de archivos nuevos, reparto de las entradas por contenedores, extracción de aspectos, armado de las bases de síntesis (sección 6). Comando `run`. |
| **Fase 2** | Redacción de documentos para el contenedor elegido a partir de su base de síntesis (sección 8). Comando `synth`. |
| **Bootstrap** | Modo de carga masiva: la estructura de contenedores aún no existe o está incompleta. Primero, un borrador de estructura a partir de todo el material; después, el reparto con división de los textos largos en segmentos (secciones 6.2–6.3). |
| **Steady-state** | Modo normal: una entrada nueva se reparte según la estructura existente, sin dividirla. |
| **Borrador de estructura** | Árbol de contenedores propuesto por el modelo, que el usuario corrige y aprueba en un solo archivo `_структура (черновик).md` (sección 6.3). |
| **Cuarentena** | La carpeta `_на_проверку/` (para revisar): entradas que el programa no pudo repartir con seguridad. Esperan la respuesta a una pregunta. |
| **Condensación** | Compresión del texto largo o ruidoso de una entrada a una forma densa antes de extraer aspectos. El texto original no cambia (sección 6.7). |
| **Pregunta** (`needs_review`) | El mecanismo único de confirmación: el programa no decide por su cuenta nada que quede por debajo del umbral o sea discutible, sino que pregunta al usuario (sección 7). |
| **Duplicado** (`duplicate_of`) | Aspecto que coincide en sentido con otro anterior. Ambos se quedan en el pool y pasan a la base de síntesis como un solo punto (sección 6.11). |
| **Obsoleto** (`outdated`) | Marca de un pensamiento o aspecto que un material más reciente o el usuario han considerado ya no vigente. Nada se borra (sección 11.1). |
| **Contradicción** (`conflicts_with`) | Dos aspectos vigentes del mismo tipo que no pueden ser ciertos a la vez. Decide el usuario; hasta la respuesta, la base parte de la suposición del modelo (sección 6.12). |
| **Bifurcación** (ramificación) | La respuesta "ambos son ciertos" («оба верны») a una contradicción: las dos direcciones se quedan en la base de síntesis y los documentos siguen ambas (sección 10.3). |
| **Brote** (`seed`) | Un tipo de contenedor: una idea que puede crecer hasta convertirse en proyecto (sección 3.3). |
| **Operación bajo demanda** | Acción que el usuario inicia por su cuenta además de las Fases 1 y 2: revalidación, búsqueda de nuevos tipos compuestos, consejo sobre umbrales (sección 10). |
| **Perfil de modelo** | Conjunto de ajustes de un modelo de lenguaje: dirección, modelo, clave, parámetros, precios (sección 13.2). |
| **Modo manual** (chat web) | Trabajo sin API: el programa prepara la solicitud en un archivo, el usuario la lleva al chat web del modelo y devuelve la respuesta en un archivo (sección 13.5). |
| **Registro de reflexión** | Registro legible por máquina de pares "suposición del sistema — decisión del usuario" para ajustar los umbrales (sección 15.3). |
| **Umbral** | Número con el que el código compara la evaluación del modelo: por encima, la acción se realiza sola; por debajo, se hace una pregunta. Puede ser general o propio de un contenedor (secciones 10.5, 17). |
| **Instantánea de estado** | El archivo `.system/ui.json`, que el programa escribe después de cada comando. De él toma el plugin todo lo que muestra (sección 18.1). |

## 3. Bóveda

### 3.1 Carpetas y archivos

El programa trabaja con una sola bóveda de Obsidian. Las carpetas y archivos de servicio empiezan por `_` o `.` y no se consideran contenedores. Las demás carpetas de nivel superior son contenedores.

```
Bóveda/
├─ _staging/                    entrada (sección 4)
│   ├─ архив/                   carga masiva (archivo): siempre Bootstrap
│   └─ Чат с ИИ/                cualquier subcarpeta = fuente de entradas (aquí: chat con IA)
├─ Club de lectura/             contenedor de nivel superior
│   ├─ Club de lectura.md       ficha del contenedor
│   ├─ _записи/                 entradas del contenedor
│   ├─ Сводный файл.md          documentos de la Fase 2
│   ├─ Lista de lecturas.md
│   ├─ _аспекты.md              vista del pool de aspectos (solo lectura)
│   ├─ _база синтеза.md         vista de la base de síntesis (solo lectura)
│   └─ Encuentros en línea/     subcontenedor: carpeta anidada con la misma estructura
├─ _shared/                     entradas que pertenecen a varios contenedores
├─ _unsorted/                   entradas sin contenedor
├─ _на_проверку/                cuarentena: entradas a la espera de una respuesta
├─ _исходники/                  archivos de entrada sin cambios
├─ _структура (черновик).md     borrador del árbol de contenedores (en una carga masiva)
├─ open-questions.md            preguntas para el usuario (sección 7)
├─ _логи/                       registros para personas (sección 15)
├─ _веб-чат/                    archivos del modo manual (sección 13.5)
├─ .system/                     datos de trabajo del programa
└─ .obsidian/
    ├─ plugins/vtoroy-mozg/     el plugin
    └─ snippets/vtoroy-mozg.css colores (sección 3.7)
```

Datos de trabajo en `.system/`:

| Ruta | Qué guarda |
| --- | --- |
| `state.json` | Estado de la cadena de procesamiento: archivos recibidos, etapas de entradas y contenedores, colas, sumas de control de los textos (sección 16.7). |
| `questions.json` | Preguntas abiertas para el usuario (sección 16.6); las respondidas pasan a `_логи/архив вопросов.md` (histórico de preguntas). |
| `data/pools/<id>.json` | Pool de aspectos del contenedor (sección 16.3). |
| `data/bases/<id>.json` | Base de síntesis del contenedor; `<id>.prev.json` es la versión anterior para comparar (sección 16.4). |
| `vectors/` | Vectores de tres niveles: entradas, aspectos, contenedores (sección 12.2). |
| `versions/` | Espejo git de las versiones de las bases de síntesis y de los documentos (sección 11.2). |
| `composite_types.json` | Tipos compuestos de aspectos añadidos por el usuario (sección 5.3). |
| `reflection.jsonl` | Registro de reflexión (sección 15.3). |
| `usage.jsonl` | Registro de llamadas a los modelos y de su coste (sección 14.1). |
| `webchat.json` | Solicitudes del modo manual: pendientes de respuesta y ya recibidas (sección 13.5). |
| `ui.json` | Instantánea de estado para el plugin (sección 18.1). |
| `lock`, `stop` | Bloqueo contra una segunda ejecución y la señal "Detener" («Стоп») del plugin (sección 11.3). |

El usuario no necesita entrar en `.system`. La copia de seguridad es toda la carpeta de la bóveda, junto con la carpeta oculta `.system`, más `settings.yaml` y los archivos de claves de la carpeta del programa.

### 3.2 Grafo de proyectos

Los contenedores forman una jerarquía: un contenedor puede tener un padre (`parent`), y un padre, cualquier número de hijos. La profundidad no tiene límite: los nodos aparecen en cualquier nivel. Normalmente, lo más trabajado son los subproyectos, mientras que el padre sigue siendo durante mucho tiempo una descripción con un cúmulo de pensamientos, y eso es normal.

Además del padre, un contenedor puede aplicarse en otras ramas (`applies_to`). Por eso la estructura es un grafo y no un árbol estricto. Ejemplo: el subproyecto "Pulsómetro" (medir el pulso con la cámara del teléfono) forma parte del proyecto "App para correr", pero también se aplica en el proyecto independiente "Monitor de sueño".

```
App para correr
 ├─ entradas: pensamientos, diario, diálogos con IA, recursos
 ├─ Pulsómetro ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┐ applies_to
 │   ├─ entradas                             ▼
 │   └─ Archivo resumen, otros documentos    Monitor de sueño
 └─ Rutas …                                   └─ entradas, documentos
Club de lectura             (proyecto independiente de nivel superior)
_unsorted                   (entradas sin contenedor)
```

La jerarquía también se ve en las carpetas: un contenedor hijo es una carpeta anidada en la del padre. El vínculo `applies_to` no cambia las carpetas.

Las entradas sin contenedor están en `_unsorted`. No es un nodo del grafo: no tiene base de síntesis ni documentos.

### 3.3 Tipos de nodo

El campo `type` de la ficha del contenedor:

| Tipo | Significado |
| --- | --- |
| `project` | Proyecto o subproyecto de cualquier nivel. |
| `seed` | Brote: una idea que puede crecer hasta convertirse en proyecto. |
| `question` | Una pregunta abierta que el usuario se hace a sí mismo. No confundir con las preguntas del programa al usuario (sección 7). |

El tipo puede escribirse en ruso: `проект` (proyecto), `росток` (brote), `вопрос` (pregunta); el programa lo convierte al valor estándar.

**Brote → proyecto.** Cuando en un brote se acumula material, el análisis del pool (sección 6.10) puede proponer convertirlo en proyecto. Si la confianza del modelo no es inferior al umbral alto (`high`, 90), el programa cambia el tipo por su cuenta; si es inferior, pregunta.

**"Muerte silenciosa" de los brotes.** Si un brote activo no ha recibido pensamientos nuevos durante más de `seed_dormancy_days` días (90; campo `last_modified` de la ficha), el programa pregunta si sigue vigente: mantenerlo como brote, congelarlo (`dormant`) o darlo por terminado (`completed`). La comprobación se hace al final de cada Fase 1, por la fecha y sin llamar al modelo.

### 3.4 Contenido del contenedor

Todo contenedor, en cualquier nivel, tiene el mismo conjunto:

- **Ficha** `Nombre.md`: propiedades en el encabezado YAML (sección 16.1) y, debajo, el texto del usuario. En el texto, el programa solo cambia el bloque de servicio entre las líneas `<!-- обновляется программой: начало -->` y `<!-- обновляется программой: конец -->` ("lo actualiza el programa: inicio / fin"): el número de entradas y los enlaces a las entradas compartidas de `_shared`, a los documentos y a las vistas.
- **Entradas** en `_записи/`: pensamientos, diario, diálogos con IA, recursos, preguntas a uno mismo, ediciones manuales de documentos. El tipo de entrada es el campo `content_type`: `thought` (pensamiento), `diary` (lo vivido: qué se hizo, qué pasó), `resource` (un enlace o material para estudiar), `question` (pregunta a uno mismo), `ai_dialogue` (diálogo con IA, sección 4.2), `product_edit` (edición manual de un documento, sección 8.5); el modelo también puede proponer otra palabra breve. El tipo de entrada no cambia el camino de procesamiento: todas las entradas pasan por los mismos pasos.
- **Entradas compartidas**: entradas que pertenecen tanto a este contenedor como a otros. Físicamente están una sola vez en `_shared/`, y la ficha de cada contenedor enlaza a ellas. No hace falta editar en varios sitios ni hay copias desincronizadas. Los aspectos de una entrada compartida van a los pools de todos sus contenedores, y cada contenedor tiene su propia base de síntesis.
- **Documentos** de la Fase 2: el "Archivo resumen" y los adicionales (sección 8).
- **Vistas** `_аспекты.md` y `_база синтеза.md`: el pool y la base de síntesis en forma legible, con una etiqueta de color de la fuente en cada pensamiento. Son de solo lectura: el programa las reescribe tras cada armado.

El pool de aspectos, la base de síntesis y los vectores del contenedor están en `.system`.

El diario no es un tipo especial de entrada con su propia cadena de procesamiento. Las entradas sobre lo vivido pasan por los mismos pasos que las demás, y el diario como documento lo redacta el modelo en la Fase 2 si en la base de síntesis hay aspectos de experiencia (`experience`, sección 5.2). Ni el contenedor ni la bóveda tienen un diario obligatorio.

### 3.5 Estado del contenedor

El campo `container_status`:

| Estado | Significado |
| --- | --- |
| `active` | En curso (por defecto). |
| `dormant` | Congelado. Las entradas se siguen repartiendo aquí; los brotes con este estado no se comprueban por "muerte silenciosa". |
| `completed` | Terminado: el resultado queda fijado. El trabajo no se bloquea; se puede seguir mejorando. En el "Archivo resumen", el modelo siempre destaca una sección "Resultado final" («Итоговый результат») aparte de la descripción viva actual. |

También en ruso: `в работе`, `заморожен`, `завершён` y formas parecidas.

### 3.6 Qué se edita a mano

El principio: un campo se puede editar directamente si **no lo ha calculado el modelo**. Los datos organizativos (nombres, vínculos, estados, colores) pertenecen al usuario. Los datos calculados (pools, bases de síntesis, valoraciones) solo cambian con una entrada nueva o con la respuesta a una pregunta. Una metáfora: el usuario es el jefe de un depósito de locomotoras. Contrata al personal (elige los modelos para cada paso), repinta los vagones y cambia los horarios, pero no reconstruye la caldera en marcha ni cambia las agujas a espaldas del maquinista: aporta combustible nuevo (una entrada) o responde a las preguntas del maquinista.

El programa detecta las ediciones manuales al inicio de cada Fase 1 y las aplica; el resultado se anota en el registro de cambios con la marca «пользователь» (usuario).

**Ficha del contenedor:**

- `type`: proyecto, brote o pregunta;
- `parent`: el padre en forma de `[[Nombre]]`; vacío significa nivel superior; la carpeta se mueve sola;
- `applies_to`: con qué otros contenedores está vinculado;
- `color`: el color;
- `container_status`: el estado (sección 3.5);
- `description`: la descripción; el programa se apoya en ella para decidir qué pertenece aquí;
- `thresholds` y `style`: umbrales propios (sección 10.5) y estilo de los documentos (sección 8.3). Es más cómodo cambiarlos en la pestaña "Contenedor" («Контейнер») del panel;
- el texto bajo las propiedades, salvo el bloque de servicio.

**Cambio de nombre.** El nombre del contenedor es el nombre de su ficha. Basta con renombrar el archivo (`Club de lectura.md` → `Círculo de lectura.md`): la carpeta se renombra sola y los enlaces `[[…]]` se actualizan. No hace falta renombrar la carpeta por separado: el programa le devuelve el nombre de la ficha.

**Contenedor nuevo a mano.** Una nota con el nombre del contenedor y la propiedad `type` (sin `id`). El padre se toma de `parent` o de la carpeta en la que está la nota. Al inicio de la siguiente Fase 1, el programa asigna al contenedor un `id`, una carpeta, un color y los campos que falten.

Si se borra la ficha de un contenedor, sus entradas pasan a `_unsorted` con un aviso. No conviene hacerlo: es más sencillo cambiar el estado.

**Entrada:**

- `container`: mover la entrada a otro contenedor. El programa mueve el archivo y los aspectos, y anota en el registro de reflexión que su reparto fue impugnado (sección 10.2);
- `also_in`: la entrada también hace falta en otros contenedores: pasa a `_shared` y sus aspectos se añaden a los pools de esos contenedores;
- `conflicts_with`: indicar que la entrada contradice a otra: `[[nombre de la entrada]]`. Estos pares pasan a la base de síntesis como una lista aparte y se tienen en cuenta en la síntesis (sección 6.12);
- `status: outdated` (o `устарела`): el pensamiento ya no está vigente, y todos sus aspectos se marcan como obsoletos. Para recuperarlo, `status: processed`, y los aspectos se restauran.

**No se edita directamente:**

- **El texto de una entrada procesada** (sección 4.3). El programa guarda una suma de control del texto. Si el texto ha cambiado, sigue trabajando con el anterior y pregunta: convertir la edición en una entrada nueva o simplemente restaurar el texto original. Mientras la entrada no haya pasado todos los pasos (por ejemplo, si espera en cuarentena), la edición del texto se acepta.
- **Los pools de aspectos, las bases de síntesis y las vistas**: la capa calculada, que el programa reconstruye por su cuenta. Una edición manual chocaría con la reconstrucción.
- **La carpeta `.system`**.

Las entradas no se borran: en lugar de borrarlas, `status: outdated`.

Hay tres formas legítimas de influir en lo calculado: (1) una entrada nueva a través de `_staging`; (2) la respuesta a una pregunta; (3) una edición manual de un documento de la Fase 2, que se convierte en una entrada nueva y pasa por la Fase 1 (sección 8.5).

### 3.7 Colores

- Los contenedores de nivel superior reciben colores de la paleta base por turnos (diez colores).
- Los hijos reciben tonos del color del padre: el color se mezcla con blanco, tanto más cuantos más hijos tenga ya el padre (del 25 % al 60 %).
- Las entradas de `_записи/` se resaltan con el color de su contenedor.
- Las entradas compartidas, con el color medio de todos sus contenedores.

El color es el campo `color` de la ficha y se puede cambiar. El estilo es el fragmento CSS `.obsidian/snippets/vtoroy-mozg.css`, que el programa actualiza después de cada comando. El programa lo activa por su cuenta una vez (`.obsidian/appearance.json`); si el usuario lo desactiva después, ya no toca ese ajuste.

Las fuentes también tienen colores propios (sección 4.2): con ellos se etiquetan los pensamientos en las vistas.

## 4. Entrada: `_staging`

Todas las entradas sin excepción, desde un pensamiento suelto hasta el material acumulado durante varios años, entran en el sistema a través de la carpeta `_staging`. Es un canal permanente: se pueden dejar archivos en cualquier momento y el programa los recibirá en la siguiente Fase 1.

### 4.1 Qué se puede dejar

- **Archivos de texto** `.txt` y `.md`, sin marcado obligatorio: notas breves, exportaciones de mensajería, diálogos con IA, un diario de años, un texto largo que mezcla de todo. El programa no lee archivos de otros formatos: los enumera en un aviso y los deja en `_staging`. Los archivos cuyo nombre empieza por `.` o `~` se omiten.
- **Dónde dejarlos**: de ello dependen la fuente y el modo:

| Lugar | Fuente (`source`) | Modo |
| --- | --- | --- |
| raíz de `_staging/` | `заметка` (nota) | se determina automáticamente (sección 6.2) |
| `_staging/<subcarpeta>/` | el nombre de la subcarpeta, por ejemplo `Чат с ИИ` (chat con IA) | se determina automáticamente |
| `_staging/архив/` | `архив` (archivo histórico) | carga masiva (Bootstrap) |
| `_staging/архив/<subcarpeta>/` | el nombre de la subcarpeta más anidada, por ejemplo `Telegram` | carga masiva |

- **Un archivo, una nota.** Hay dos excepciones: un diario con fechas se divide en entradas por fecha (sección 4.2), y en una carga masiva la clasificación divide un texto largo en segmentos por temas (sección 6.4). En el modo normal la entrada se mantiene entera aunque afecte a varios contenedores: el vínculo con los demás se hace mediante entradas compartidas (sección 6.5).

**Recepción del archivo.** El programa lee el archivo, analiza el encabezado de servicio, copia el archivo sin cambios a `_исходники/` con el nombre `AAAA-MM-DD nombre` (si el nombre ya empieza por una fecha, no se añade otra) y lo borra de `_staging`. Las subcarpetas vacías de `_staging` se eliminan, salvo `архив`. Un archivo vacío también se guarda en `_исходники`, pero no hay nada que procesar en él, y así lo indica un aviso. Los archivos recibidos se marcan con una suma de control: si tras un fallo un archivo se queda en `_staging`, no se recibirá por segunda vez.

### 4.2 Formato del archivo

**La codificación** se detecta sola: UTF-8 (con o sin BOM) o Windows-1251, el caso típico de los txt antiguos. Los saltos de línea se normalizan.

**El encabezado de servicio**: líneas opcionales al principio del archivo, antes del texto principal (el programa mira las cinco primeras líneas no vacías):

- una línea con una fecha `dd.mm.aaaa` (puede llevar «г.», la abreviatura rusa de "año"): la fecha de la entrada;
- una línea `hint: …` (o `подсказка: …`): una pista sobre dónde clasificar la entrada (sección 4.4).

El programa entiende también el encabezado YAML de Obsidian: los campos `hint` (`подсказка`) y `date`, `created` (`дата`). Otras dos líneas de servicio las escribe el propio programa: `content_type: …`, en los archivos que crea a partir de ediciones manuales, y `mode: steady_state` (`режим: одна запись`, "modo: una sola entrada"), en los de "Nuevo pensamiento" (sección 4.5): un archivo así siempre se procesa como una sola entrada.

**La fecha de la entrada** se determina en este orden:

1. la fecha del encabezado de servicio;
2. si no la hay, la más antigua de las dos fechas del archivo, la de creación y la de modificación. Al copiar, Windows pone como fecha de creación el momento de la copia, mientras que la de modificación se conserva; por eso se toma la más antigua;
3. las fechas dentro del texto son contenido, no la fecha de la nota: una mención como "reunión 12.05.2025" no se convierte en la fecha de la entrada.

**Los diálogos con IA** se marcan con prefijos de intervención al comienzo de la línea: por defecto `я:` ("yo:") e `ИИ:` ("IA:") (ajuste `dialogue_markers`; las listas de prefijos se pueden ampliar). Una intervención dura hasta el siguiente prefijo. Un archivo con intervenciones de ambas partes recibe automáticamente `content_type: ai_dialogue`. Para los demás archivos, el tipo de entrada lo propone la clasificación (sección 6.4).

**Párrafos.** El código numera los párrafos, y todas las referencias posteriores a partes del texto son números de párrafo. Un párrafo es un bloque entre líneas vacías; si el archivo no tiene líneas vacías, cada línea es un párrafo. Una línea con prefijo de intervención siempre empieza un párrafo nuevo. Un párrafo de más de 8000 caracteres se divide por líneas y frases; así cualquier archivo puede partirse en porciones para el modelo.

**Fuente.** Se determina por la ubicación del archivo (sección 4.1) y sirve para dos cosas: las etiquetas en las vistas (cada fuente tiene su color) y el desplazamiento del umbral de condensación (sección 6.7). La fuente no influye en los pesos ni en la ordenación: una entrada de diario puede resultar vacía y un pensamiento casual, muy sustancioso; por eso la prioridad se basa en el tipo de aspecto y en su valor (sección 5.4). La lista de fuentes es el ajuste `sources`: nombre, color y `compaction_shift`, es decir, cuántos puntos bajar el umbral de condensación para esa fuente. Por defecto: `архив` y `заметка`, sin desplazamiento; `Чат с ИИ`, 20 (los diálogos con IA suelen ser prolijos). Para crear una fuente propia basta con dejar archivos en una subcarpeta con su nombre; los ajustes solo hacen falta si se quiere un color o un desplazamiento.

**Diario por fechas.** Un archivo cuyas entradas empiezan con una línea de fecha (un diario de años) se divide en varias entradas, cada una con su fecha (ajuste `input.split_by_dates`, activado por defecto):

- el inicio de una entrada es una línea que solo contiene una fecha: `12.03.2021`, `12.03.21`, `2021-03-12`, `12 марта 2021` (mes en ruso); puede llevar día de la semana, hora, la palabra «г.», un encabezado `#` o resaltado `**`. La propia línea de la fecha no entra en el texto de la entrada;
- si no hay tales líneas, una fecha al comienzo de un párrafo largo (de 300 caracteres o más) tras una línea vacía, siempre que esos párrafos sigan el orden de las fechas (ascendente o descendente). La fecha se recorta del párrafo;
- el texto anterior a la primera fecha: si el encabezado del archivo tiene su propia fecha, es una entrada aparte con esa fecha; si no, un texto corto (hasta 200 caracteres, normalmente un título) se une a la primera entrada, y uno largo se convierte en una entrada aparte con la fecha del archivo;
- no se dividen: los archivos con las líneas de servicio `content_type` o `mode: steady_state`, los diálogos con IA y los archivos con menos de dos fechas (la fecha del encabezado también cuenta);
- cada parte es una entrada aparte con el campo `source_part` (número de la parte y su fecha). El archivo original es uno solo y se guarda entero en `_исходники/`. Después las partes siguen el camino habitual; en una carga masiva, la clasificación aún puede dividirlas.

### 4.3 Borrador e inmutabilidad

**Antes de la Fase 1, una entrada es un borrador.** Mientras el archivo está en `_staging`, se puede editar libremente: completarlo, corregir una errata, reformularlo.

**Después de la Fase 1, el texto de la entrada es inmutable.** A la entrada ya hacen referencia aspectos, duplicados, contradicciones y vectores; una edición retroactiva inadvertida restaría valor a esos vínculos. Cambiar el contenido de un pensamiento procesado significa añadir una **entrada nueva** a través de `_staging`. En la Fase 1, la entrada nueva puede:

- complementar la antigua: los aspectos nuevos simplemente se añaden al pool, y los que coinciden en sentido se vinculan como duplicados (sección 6.11);
- revisarla: el programa propone marcar el aspecto antiguo como obsoleto (`outdated`);
- contradecirla (`conflicts_with`, sección 6.12).

**Si aun así se editó una entrada procesada.** El programa guarda una suma de control del texto de cada entrada. Al detectar una discrepancia, sigue trabajando con el texto anterior y hace una pregunta (sección 7):

- "Convertir la edición en una entrada nueva" («Сделать из правки новую запись»): en `_staging` aparece un archivo «правка — <запись>» ("edición — <entrada>") con una pista hacia el mismo contenedor y la marca `одна запись` (una sola entrada). Solo contiene lo que cambió: «Автор добавил или переписал: …» ("El autor añadió o reescribió: …") y «Автор убрал: …» ("El autor quitó: …"), frase por frase. El texto original de la entrada se restaura desde `_исходники`;
- "Simplemente restaurar el texto original" («Просто вернуть исходный текст»).

Mientras la entrada no haya pasado todos los pasos (por ejemplo, si espera respuesta en cuarentena), la edición de su texto se acepta sin preguntar.

### 4.4 Pistas

Una pista es una línea `hint: …` en el encabezado del archivo (o el campo "Dónde clasificar" («Куда отнести») de la ventana "Nuevo pensamiento"). Normalmente es el nombre de un contenedor, existente o nuevo. La pista no dicta el resultado, sino que **desplaza la confianza** a favor de la opción indicada. El modelo evalúa, el código decide:

1. El modelo (prompt "Clasificación", «Классификация») devuelve dos evaluaciones: su propia elección de contenedor con una confianza **sin tener en cuenta la pista** y, por separado, la confianza para la opción de la pista.
2. El código suma a la confianza de la opción de la pista el desplazamiento `hint_shift` (15 puntos) y compara el resultado con el umbral:
   - si el modelo y la pista apuntan a lo mismo, se toma la mayor de las dos evaluaciones;
   - si la opción de la pista supera el umbral con el desplazamiento, la entrada se clasifica según la pista, aunque la confianza propia del modelo estuviera por debajo del umbral. Para un contenedor existente el umbral es `classification` (70); para uno nuevo, `high` (90);
   - si no lo supera ni siquiera con el desplazamiento, la pista no encaja con el contenido. No se impone ni se ignora: la entrada va a cuarentena con una pregunta por el motivo `user_hint_mismatch`: "se indicó X, pero por el contenido parece Y".
3. Sin pista, rige la regla habitual de umbrales (sección 6.5).

Al registro de reflexión va la evaluación "pura" del modelo, sin la pista; así se ve cuánto ayudan realmente las pistas (sección 15.3).

### 4.5 "Nuevo pensamiento"

El comando "Nuevo pensamiento" del plugin (un botón en el panel o la paleta de comandos) es la forma más rápida de anotar un pensamiento. La ventana tiene: el texto; "Dónde clasificar", una pista opcional a elegir entre los contenedores existentes; la fecha (hoy por defecto); la fuente (nota o cualquiera de `sources`, salvo `архив`); y la casilla "Procesar ahora (Fase 1)" («Сразу обработать (Фаза 1)»), desactivada por defecto: así se pueden apuntar varios pensamientos y procesarlos de una vez. Ctrl+Enter guarda.

El plugin guarda el pensamiento en `_staging` (o en la subcarpeta de la fuente) como un archivo `AAAA-MM-DD HH-MM <inicio del texto>.txt` con un encabezado que contiene la fecha, la pista y la línea `mode: steady_state`. Por eso un archivo así siempre es una sola entrada: no se divide ni por fechas ni en segmentos.

## 5. Aspectos

Un aspecto es una unidad de sentido que el modelo extrae de una entrada (sección 6.9). No es un archivo aparte ni un bloque dentro de la entrada, sino un elemento del pool de aspectos del contenedor (`.system/data/pools/<id>.json`, sección 16.3) con un enlace a la entrada de origen; la entrada tiene los enlaces inversos `aspect_ids`. Todos los cálculos se basan en los aspectos: valor, duplicados, contradicciones, ordenación.

Los aspectos **no son lo mismo** que los documentos de la Fase 2. Los aspectos son la materia prima; los documentos, el texto escrito a partir de ellos.

### 5.1 Tipos simples (nivel 0)

La lista es fija:

| Tipo | Esencia |
| --- | --- |
| `fact` | Constatación de algo que ocurrió o existe, sin interpretación. |
| `observation` | Un detalle o una regularidad observados; se verifica con menos rigor que un hecho. |
| `hypothesis` | Una suposición no comprobada. |
| `idea` | Propuesta de una dirección o de una solución. |
| `conclusion` | Conclusión extraída de lo anterior. |
| `question` | Una incertidumbre abierta. |
| `plan` | Una acción o intención futura declarada. |
| `judgment` | Una valoración o reacción subjetiva. |

### 5.2 Tipos compuestos (nivel 1)

Un aspecto compuesto es un conjunto de aspectos simples de **un mismo contenedor** (no necesariamente de una misma entrada) que forma un todo. Lista inicial:

| Tipo compuesto | Se arma a partir de |
| --- | --- |
| `experience` (experiencia) | `plan` + `fact` + `observation`/`judgment` + `conclusion` |
| `resolved_decision` (decisión fundamentada) | `question` + varios `hypothesis`/`idea` + `conclusion` |
| `open_conflict` (bifurcación) | dos o más `hypothesis`/`idea` sobre una misma pregunta que no convergen en un `conclusion` común |

Ejemplo de experiencia en el contenedor "Pulsómetro": el plan "comprobar la medición con poca luz" + el hecho "con la luz de una lamparita de noche, el pulso saltaba 15 latidos" + la observación "el flash del teléfono estabiliza la señal" + la conclusión "encender el flash automáticamente".

La fórmula de composición no es solo la definición del tipo, sino también un algoritmo de selección en funcionamiento. Para cada fórmula, el código selecciona de antemano los aspectos libres de los tipos adecuados (si entre ellos hay al menos dos tipos distintos) y pasa estos candidatos al análisis del pool. Si encajan en un todo (sobre un mismo suceso, pregunta o decisión) lo decide el modelo (sección 6.10). El modelo intenta primero completar un compuesto existente de la misma fórmula y después armar uno nuevo. Un compuesto que ya no se sostiene (por ejemplo, porque parte de su composición quedó obsoleta) puede ser disuelto por el modelo: sus partes vuelven a quedar libres.

Los componentes de un compuesto armado reciben el estado `in_composite`, y a la base de síntesis va el aspecto compuesto entero.

**Obsolescencia dentro de un compuesto.** Si un aspecto simple que forma parte de un compuesto se marca como obsoleto, el compuesto recibe el estado `needs_review` y el contenedor, una revisión completa en el siguiente armado de la base: el modelo completa o disuelve el compuesto. No se queda obsoleto en silencio. En la base de síntesis, un compuesto así lleva la marca «на пересмотре» (en revisión).

### 5.3 Nuevos tipos compuestos

La lista de tipos compuestos está abierta. El modelo puede proponer un tipo nuevo si observa un conjunto recurrente de tipos simples, pero solo mediante una pregunta al usuario: con la fórmula, un ejemplo de cómo se vería y una justificación de por qué es un patrón estable y no una coincidencia. La búsqueda la inicia el usuario (operación "Patrones", «Паттерны», comando `patterns`). Se hace en dos etapas para no hacer pasar al modelo por toda la base:

1. **Etapa técnica, sin modelo.** En el pool de cada contenedor se toman los aspectos libres (`active`, no duplicados). Cada aspecto se vincula con sus vecinos más cercanos (hasta seis) si la similitud de sus vectores no es inferior a `pattern_similarity` (0,8). Los grupos conectados son candidatos. Sirven los grupos de tres o más aspectos con tres o más tipos distintos cuyo conjunto de tipos no encaja en ninguna fórmula existente. Se toman hasta ocho de los grupos más grandes, con veinte aspectos cada uno.
2. **Etapa de contenido, prompt "Nuevo tipo compuesto"** («Новый составной тип»). El modelo recibe las fórmulas existentes y los grupos candidatos y decide si entre ellos hay un patrón estable. Como máximo dos propuestas cada vez, cada una como pregunta al usuario. Los nombres rechazados se recuerdan y no se vuelven a proponer.

Un tipo confirmado se guarda en `.system/composite_types.json` y desde ese momento participa en el análisis del pool igual que los integrados.

### 5.4 Tabla de prioridad

La tabla fija el orden de los grupos de aspectos en la base de síntesis, es decir, en qué orden se entregan los grupos al modelo al redactar documentos. Es el segundo eje de ordenación, independiente del primero. El primero, el valor de contenido, divide los elementos en principales y secundarios **dentro** de cada grupo (sección 6.10). La tabla no lo sustituye ni lo duplica: un plan valioso y urgente destaca dentro de su grupo, esté donde esté el grupo.

El único criterio de la tabla es la solidez de la afirmación: primero lo que ya ha ocurrido o se ha meditado hasta el final; después, lo menos asentado.

| Puesto | Tipo |
| --- | --- |
| 1 | `resolved_decision` |
| 2 | `fact` |
| 3 | `experience` |
| 4 | `conclusion` |
| 5 | `observation` |
| 6 | `open_conflict` |
| 7 | `hypothesis` |
| 8 | `plan` |
| 9 | `idea` |
| 10 | `judgment` |
| 11 | `question` |

Los nuevos tipos compuestos añadidos por el usuario se colocan justo después de `open_conflict`.

### 5.5 Estados del aspecto

| Estado | Significado |
| --- | --- |
| `active` | Aspecto simple libre: participa por sí mismo en la base de síntesis. |
| `in_composite` | El aspecto simple ha pasado a formar parte de un compuesto; en la base de síntesis está dentro del compuesto. |
| `outdated` | Obsoleto: revisado por material más reciente o marcado por el usuario. Se queda en el pool, pero no participa en la síntesis. Al lado figura con qué se sustituyó (`replaced_by`). |
| `needs_review` | Solo en compuestos: parte de la composición está obsoleta y hay que volver a armarlo. |

Independientemente del estado, un aspecto puede tener la marca `duplicate_of` (un enlace a un aspecto anterior con el mismo sentido, sección 6.11), una valoración `value` y la marca `pinned`, "fijado por el usuario" («закреплено пользователем», sección 6.13). Los duplicados quedan obsoletos junto con el aspecto principal. Si todos los aspectos de una entrada están obsoletos, la entrada entera recibe `status: outdated`.

## 6. Fase 1: procesamiento

La Fase 1 (comando `run`, botón "Fase 1" del panel) convierte los archivos nuevos en entradas repartidas por contenedores, extrae de ellas aspectos y vuelve a armar las bases de síntesis de los contenedores que han cambiado. Se inicia a mano y puede extenderse a lo largo de varias sesiones: una ejecución interrumpida continúa desde el mismo punto (sección 11.3).

### 6.1 Orden de los pasos

Cada ejecución sigue este orden:

1. **Comprobación del modelo de embeddings.** Si los vectores se calcularon con otro modelo, se recalculan (sección 12.2).
2. **Ediciones manuales.** El programa aplica lo que el usuario cambió en las fichas y en las entradas: tipo, padre, vínculos, estados, traslado de entradas, contenedores creados a mano (sección 3.6). Detecta las ediciones del texto de entradas procesadas y pregunta por ellas (sección 4.3).
3. **Respuestas a las preguntas** de `open-questions.md` (sección 7.3). Los pares "suposición — decisión" van al registro de reflexión.
4. **El borrador de estructura aprobado**, si el usuario lo ha marcado (sección 6.3).
5. **Las ediciones manuales de los documentos** de la Fase 2 se convierten en entradas nuevas en `_staging` (sección 8.5).
6. **Recepción de archivos** de `_staging` (sección 4.1).
7. **Borrador de estructura** para una nueva carga masiva: Bootstrap, pasada 1 (sección 6.3). Mientras el borrador no esté aprobado, los archivos de esa carga esperan.
8. **Procesamiento de los archivos**, de los antiguos a los nuevos según la fecha de la entrada: la clasificación (sección 6.4) y los umbrales (6.5) crean las entradas, y cada una pasa enseguida por sus pasos: preguntas aclaratorias (6.6), condensación (6.7), vectores (6.8), extracción de aspectos (6.9). El orden cronológico es necesario para que "lo más reciente revisa lo más antiguo" coincida con la cronología real.
9. **Armado de la base de síntesis** de cada contenedor al que llegaron aspectos nuevos o en el que cambiaron estados (sección 6.10), y comparación con la versión anterior (6.13).
10. **"Muerte silenciosa" de los brotes**: comprobación de los brotes que llevan mucho tiempo sin desarrollarse (sección 3.3).

Al final de la ejecución, el programa vuelve a generar `open-questions.md`, los bloques de servicio de las fichas y los colores, registra las versiones en el espejo git y escribe la instantánea para el plugin.

Cada entrada tiene una etapa: `classified` → `asked` → `compacted` → `embedded` → `done`; una entrada en cuarentena, `quarantine` → `quarantine_wait`. Un contenedor cuya base está desactualizada tiene una etapa de armado: `analysis` → `value` → `assemble` → `compare`. Las etapas se guardan tras cada paso, de modo que una ejecución interrumpida continúa desde la misma entrada y el mismo paso.

### 6.2 Modo: Bootstrap o Steady-state

Dentro de la Fase 1 hay dos tareas de naturaleza distinta, pero no dos cadenas de procesamiento distintas:

- **Steady-state**: una entrada nueva se reparte según la estructura de contenedores existente. La entrada siempre se mantiene entera.
- **Bootstrap**: no hay estructura o se sabe que está incompleta. No solo hay que repartir el material, sino también descubrir los propios contenedores y dividir los textos largos en segmentos por temas. Aquí la entrada no suele ser una dispersión de pensamientos atómicos, sino un relato largo y coherente o un revoltijo semicoherente en el que hay que reconstruir los límites de los proyectos y sus vínculos.

El modo se determina antes de la clasificación, porque de él depende si se divide el texto:

1. **Aún no hay contenedores** (primera ejecución) → siempre Bootstrap.
2. **El archivo está en `_staging/архив/`** → Bootstrap por indicación explícita del usuario.
3. **El archivo está en otro lugar de `_staging`** → el modo no está fijado. Lo supone la clasificación por el volumen y la forma del texto: un texto largo sin marcadores explícitos se acerca a una carga masiva; un pensamiento breve y aislado es claramente Steady-state. Si la confianza es inferior a `mode_guess` (70), el archivo espera la respuesta a la pregunta "Cómo procesar el archivo" («Как обработать файл»): dividirlo en partes por temas o procesarlo como una sola entrada.
4. **La línea de servicio `mode: steady_state`** (así guarda los archivos "Nuevo pensamiento") → siempre Steady-state.

El Bootstrap completo en dos pasadas (con borrador de estructura) se hace con la bóveda vacía y para `_staging/архив/`. Si se elige Bootstrap para un archivo de la raíz de `_staging` (con seguridad o tras una respuesta), el archivo se divide en segmentos y se reparte según la estructura existente, sin borrador.

### 6.3 Borrador de estructura (Bootstrap, pasada 1)

Si el material de una carga masiva se repartiera archivo por archivo, creando contenedores sobre la marcha, la estructura la marcarían los primeros archivos que aparecieran y surgirían duplicados con facilidad: por ejemplo, "Pulsómetro" y "proyecto sobre el pulso con la cámara" como dos contenedores distintos. Por eso la carga masiva se hace en dos pasadas.

**Pasada 1.** El prompt "Estructura" («Структура») revisa todo el material de la carga y propone un árbol de contenedores: nombre, tipo (`project`, `seed`, `question`), descripción breve, padre y vínculos `applies_to`. Si el material no cabe en una sola solicitud, el código lo divide en partes, y cada parte siguiente precisa el borrador ya armado. Si ya existe una estructura, el borrador la muestra junto con los cambios propuestos.

El borrador es el archivo `_структура (черновик).md`: una lista anidada de líneas como

```
- App para correr (проект) — correr, entrenamientos, un servicio para corredores <!-- n1 -->
    - Pulsómetro (проект) — pulso con la cámara del teléfono | применяется в: Monitor de sueño <!-- n2 -->
- Monitor de sueño (росток) — idea de una app para analizar el sueño <!-- n3 -->
```

El anidamiento se indica con la sangría; el tipo va entre paréntesis (el programa lo escribe en ruso, `проект`, `росток`, `вопрос`, pero también entiende `project`, `seed`, `question`); tras el guion va la descripción; tras «| применяется в:» ("se aplica en:"), los vínculos separados por «;». La marca de servicio al final de la línea es `<!-- k… -->` en un contenedor existente y `<!-- n… -->` en uno propuesto: gracias a ella el programa reconoce el contenedor después de un cambio de nombre, de modo que los vínculos "se aplica en" sobreviven al cambio de nombre. Una línea sin marca o con una marca copiada es un contenedor nuevo.

El usuario corrige el borrador en un solo archivo: cambia nombres, cambia la subordinación (modifica la sangría), fusiona y elimina temas (si se borra una línea, las entradas de ese tema se repartirán entre los restantes), cambia el tipo y la descripción. Un contenedor existente no se puede eliminar desde el borrador. La aprobación es la casilla «Структура утверждена» ("Estructura aprobada") en el mismo archivo. Es una sola revisión en lugar de cientos de preguntas sueltas.

Al inicio de la siguiente Fase 1, el programa aplica el borrador: crea los contenedores nuevos, renombra y resubordina los existentes y establece los vínculos. El borrador aprobado se traslada a `_логи/` («структура утверждена ГГГГ-ММ-ДД», "estructura aprobada AAAA-MM-DD"), y el resultado (cuántos contenedores se propusieron y aprobaron, qué se eliminó, añadió o renombró) se anota en el registro de cambios y en el registro de reflexión.

**Pasada 2.** Los archivos de la carga pasan por los pasos habituales de la Fase 1 según el árbol aprobado, divididos en segmentos y en orden cronológico. Los contenedores nuevos que aparecen por el camino se crean según la regla general de umbrales (sección 6.5).

### 6.4 Clasificación

El prompt "Clasificación" se llama para cada archivo nuevo (o parte de un diario). Como entrada, el modelo recibe:

- los párrafos numerados del texto (sección 4.2);
- la fecha, la fuente, el tipo de entrada si ya se conoce, los prefijos de intervención de los diálogos y la pista del usuario;
- el modo (`bootstrap`, `steady_state` o "no fijado");
- todos los contenedores: `id`, nombre, tipo, padre, descripción y un resumen breve, que es el comienzo del "Archivo resumen" (hasta 1200 caracteres) o, si aún no hay documentos, un resumen de los aspectos más valiosos del pool. Cuando hay más de `max_containers_in_prompt` (150) contenedores, la lista se reduce de antemano con una búsqueda vectorial sobre el texto del archivo; los padres de los encontrados se añaden como contexto.

El modelo devuelve:

- **segmentos**: rangos de párrafos, cada uno de los cuales se convertirá en una entrada aparte. Solo se puede dividir en Bootstrap; en Steady-state hay exactamente un segmento que incluye todos los párrafos. El código copia el texto del segmento del original literalmente;
- para cada segmento: el contenedor principal, existente (`id`) o nuevo (nombre, tipo, padre supuesto, descripción), con una confianza de 0 a 100 **sin tener en cuenta la pista**; la confianza para la opción de la pista, si la hay (sección 4.4); alternativas con su confianza; contenedores adicionales en los que la entrada también es aplicable, con su confianza; el tipo de entrada (`content_type`), si no venía dado; la marca "entrada incompleta" (`incomplete`), es decir, un pensamiento sin las explicaciones que solo conoce el autor; una valoración del ruido de 0 a 100 para la condensación (sección 6.7); y el razonamiento (`reasoning`);
- una suposición sobre el modo con su confianza, si el modo no está fijado.

Si el archivo no cabe en la ventana del modelo, el código divide los párrafos en porciones (ventanas) de forma determinista, para que tras un fallo la división se repita exactamente igual. Cada ventana se clasifica por separado; el progreso se guarda tras cada ventana y tras cada entrada creada: un fallo no creará una entrada dos veces.

El nombre del archivo de la entrada es la fecha y las primeras palabras del texto. La entrada recibe un enlace al original (`source_file`) y, si es parte de un archivo, el rango de párrafos (`segment`).

### 6.5 Aplicación de los umbrales

Decide el código comparando las evaluaciones del modelo con los umbrales. Se usan los umbrales del contenedor en el que se coloca la entrada (propios o heredados, sección 10.5); para un contenedor nuevo, los de su padre supuesto.

| Caso | Umbral | Igual o por encima del umbral | Por debajo del umbral |
| --- | --- | --- | --- |
| Contenedor existente | `classification` (70) | la entrada se reparte sola | cuarentena `_на_проверку` y la pregunta "Dónde clasificar la entrada" («Куда отнести запись») |
| Contenedor nuevo | `high` (90) | el contenedor se crea solo y la entrada se coloca en él | cuarentena y una pregunta con la opción "Crear …" («Создать …») |
| No encaja ningún contenedor | `classification` | la entrada va a `_unsorted` | cuarentena y una pregunta |
| Contenedor adicional | `high` | la entrada pasa a ser compartida: se traslada a `_shared` y sus aspectos se añaden también a este contenedor | la pregunta "¿La entrada también hace falta en otro contenedor?" («Запись нужна и в другом контейнере?») |
| Modo no fijado | `mode_guess` (70) | se acepta el modo | la pregunta "Cómo procesar el archivo" |

La pista desplaza la confianza de su opción en `hint_shift` (sección 4.4); si no encaja con el contenido, la entrada va a cuarentena por el motivo `user_hint_mismatch`.

En la pregunta "Dónde clasificar la entrada", las opciones las reúne el código: la elección del modelo, la opción de la pista, el contenedor nuevo propuesto, las alternativas y "Sin contenedor" («Без контейнера»). Una respuesta libre es el nombre de un contenedor; si no existe, se crea un proyecto nuevo de nivel superior, y el tipo se puede indicar entre paréntesis: "Nombre (seed)" (también en ruso: «Название (росток)»).

Las entradas sin contenedor (`_unsorted`) reciben vectores, pero no aspectos: los aspectos se extraen cuando la entrada recibe un contenedor.

### 6.6 Preguntas aclaratorias y cuarentena

El prompt "Preguntas" («Вопросы») se llama solo si la confianza de la clasificación está por debajo del umbral (la entrada está en cuarentena) o si la entrada está marcada como incompleta. El modelo recibe el texto de la entrada, el motivo, la elección del modelo con su confianza y alternativas, la pista y las descripciones de los contenedores candidatos, y formula hasta `max_questions_per_entity` (3) preguntas breves, con opciones de respuesta cuando es posible.

- **Una entrada dudosa** espera en cuarentena (`_на_проверку`) hasta que el usuario responda dónde clasificarla. Las preguntas aclaratorias le ayudan a decidir.
- **Una entrada segura pero incompleta** sigue avanzando por los pasos, y las preguntas sobre ella van a `open-questions.md`. La respuesta se convierte en una entrada nueva en `_staging` con un enlace a la original: el texto de la entrada procesada no cambia (sección 4.3).
- **En Bootstrap**, solo se hacen preguntas a las entradas en cuarentena; las incompletas reciben `incomplete: true` y siguen sin preguntas; de lo contrario, un archivo histórico antiguo generaría cientos de preguntas.

Una entrada con preguntas abiertas lleva en el YAML las marcas `needs_review: true` y `review_reason` (`low_confidence`, `user_hint_mismatch`, `new_container`, `incomplete`).

### 6.7 Condensación

Un paso aparte, **anterior** a la extracción de aspectos: comprimir un texto largo o ruidoso hasta una forma densa y legible, para que la extracción no se ahogue en el ruido. La extracción aísla el sentido de un texto ya hecho; la condensación comprime un texto originalmente prolijo. Si ambos pasos se mezclan en un mismo razonamiento, el modelo decide a la vez "qué quitar" y "qué destacar", y los dos resultados salen perjudicados. Ejemplo: un diálogo con una IA suele estar lleno de repeticiones, preguntas aclaratorias y explicaciones prolijas.

Si hace falta condensar se decide por el contenido real de cada texto, no por su fuente: un diálogo breve y al grano no necesita condensación; un pensamiento largo y embrollado, quizá sí. El nivel de ruido (0–100) lo evalúa el modelo durante la clasificación, cuando ya ha leído todo el texto. El código llama al prompt "Condensación" («Уплотнение») si

```
ruido ≥ compaction − compaction_shift de la fuente
```

(`compaction` es 60; la fuente `Чат с ИИ` tiene un desplazamiento de 20, es decir, un umbral de 40). La decisión y la valoración se anotan en el registro de reflexión.

La versión condensada se guarda en la misma entrada como una sección aparte, «Уплотнённая версия (создана программой)» ("Versión condensada (creada por el programa)"), bajo el texto original, y en el YAML aparece `compacted: true`. El texto original no cambia. A partir de ahí (vectores, extracción) se usa la versión condensada. El programa comprueba que el texto comprimido sea realmente más corto que el original.

**Diálogos con IA.** La base son las intervenciones del usuario (`я:`) como fuente primaria del pensamiento. Las intervenciones del modelo (`ИИ:`) se tienen en cuenta como contexto y como motivo, no como contenido propio. La excepción es una propuesta de la IA que el usuario aceptó explícitamente ("sí, lo haré así"): eso ya es su postura y se conserva («Принял предложение ИИ: …», "Aceptó la propuesta de la IA: …"). La misma regla se aplica en la extracción de aspectos.

La condensación funciona igual en ambos modos: en Bootstrap, de forma masiva; en Steady-state, entrada por entrada.

### 6.8 Vectores y entradas parecidas

El código (sin el modelo de lenguaje) calcula el vector de la entrada, a partir de la versión condensada si la hay. Los vectores de tres niveles (entradas, aspectos, contenedores) se describen en la sección 12.

**Revalidación gratuita.** En el modo normal, el programa busca entre las entradas procesadas de otros contenedores alguna casi idéntica en sentido (similitud no inferior a `neighbor_similarity`, 0,88). Si la encuentra, quizá una de las dos esté mal clasificada, y el usuario recibe la pregunta "Entradas parecidas en distintos lugares" («Похожие записи в разных местах»): mover la nueva, mover la antigua, hacer compartida la nueva o dejarlo como está. Es una comprobación barata del reparto antiguo que surge como efecto secundario del trabajo normal (sección 10.1). En Bootstrap no se hace: la estructura apenas se está formando.

### 6.9 Extracción de aspectos

El prompt "Extracción" («Извлечение») descompone una entrada en aspectos simples (sección 5.1). El modelo recibe el texto de la entrada (condensado, si lo hay), la fecha, el tipo de entrada y el nombre y la descripción del contenedor, y no ve el resto del pool: es una descomposición honesta de esta entrada concreta, sin mirar a las vecinas. Los vínculos entre aspectos son cosa del análisis del pool (sección 6.10).

Los aspectos se añaden al pool del contenedor de la entrada (y a los pools de todos sus contenedores adicionales) con un enlace a la entrada y su fecha; para cada aspecto se calcula un vector. La entrada recibe `status: processed` y la lista `aspect_ids`. Si la extracción se interrumpió, al repetirla se eliminan los restos del intento interrumpido y no quedan aspectos sobrantes. El contenedor se marca para volver a armar su base de síntesis.

### 6.10 Armado de la base de síntesis

Para cada contenedor al que en esta ejecución llegaron aspectos nuevos o en cuyo pool cambiaron estados:

**1. Análisis del pool** (prompt "Análisis del pool", «Анализ пула»). Una sola llamada sobre todo el pool del contenedor. Cada aspecto se entrega con la fecha de su entrada de origen, para distinguir lo nuevo de lo antiguo. Además de los propios aspectos, el modelo recibe: las fórmulas de los tipos compuestos y los candidatos para cada fórmula seleccionados por el código (sección 5.2); los compuestos existentes; qué aspectos son nuevos en esta ejecución; pares de aspectos parecidos procedentes de la búsqueda vectorial (similitud no inferior a `duplicate_similarity`, 0,86; hasta 150 pares); los pares ya decididos por el usuario, para no volver a proponerlos; y la lista de entradas del contenedor. Si el pool es muy grande, el código lo divide en partes.

El modelo encuentra:

- **aspectos compuestos**: completar uno existente o armar uno nuevo con aspectos libres; disolver un compuesto que ya no se sostiene. Se aplica de inmediato;
- **duplicados**: aspectos que coinciden en sentido con otros ya existentes. Se vinculan de inmediato (sección 6.11);
- **material obsoleto**: aspectos que el material nuevo revisa. Siempre es solo una propuesta: la pregunta "¿El pensamiento nuevo revisa el antiguo?" («Новая мысль пересматривает старую?») con la confianza del modelo. Queda obsoleto el más antiguo por fecha;
- **contradicciones** entre aspectos del mismo tipo, con una suposición sobre cuál es el correcto (sección 6.12);
- **propuestas de estructura**: convertir un brote en proyecto; separar un subcontenedor a partir de un grupo de entradas. Si la confianza no es inferior a `high` (90), el programa lo hace por su cuenta; si es inferior, pregunta.

**2. Valoración** (prompt "Valor"). Una llamada aparte. Cada elemento que puede entrar en la base (aspectos simples libres que no son duplicados y compuestos enteros) recibe una valoración de 0 a 100 en el contexto de todo el contenedor. El valor de un mismo hecho depende de qué más hay en el contenedor, por lo que la valoración se recalcula en cada armado. Los elementos se entregan en partes de `max_items_per_value_call` (400). Los duplicados reciben la valoración de su aspecto principal.

**3. Filtro** (código). Los elementos con un valor inferior a `value_min` (30) no entran en la base, pero se quedan en el pool y en la vista. Los fijados por el usuario (`pinned`) pasan siempre.

**4. Agrupación por tipo** (código). Las contradicciones del análisis se plantean como pregunta solo si ambos aspectos pasaron el filtro. Las demás se guardan y saldrán a la luz si más adelante el aspecto pasa el filtro.

**5. Ordenación dentro del grupo** (código): un valor no inferior a `value_primary` (70) es principal; si no, secundario. Lo fijado es siempre principal; una alternativa rechazada por el usuario, siempre secundaria. Dentro del grupo van primero los principales y después por valor descendente y por fecha.

**6. Orden de los grupos** (código), según la tabla de prioridad (sección 5.4).

Cada elemento de la base guarda el texto, el valor, el rango, la fecha, todas las entradas de origen (incluidas las de los duplicados), la composición en el caso de los compuestos y las marcas: «спорит с …» (contradice a …), «предположительно уступает» (presumiblemente cede), «развилка» (bifurcación), «рассмотренная и отклонённая альтернатива» (alternativa considerada y rechazada), «на пересмотре» (en revisión), «закреплено вами» (fijado por usted). Las contradicciones entre entradas marcadas a mano por el usuario (`conflicts_with`) forman una lista aparte. El formato está en la sección 16.4. La vista `_база синтеза.md` muestra la base en forma legible, y su texto se registra en el espejo git como una versión.

Si el pool solo cambió en lo organizativo (la respuesta a una pregunta sobre una contradicción, una obsolescencia fuera de un compuesto, la restauración de un elemento), el análisis y la valoración no se repiten: el código vuelve a armar la base con las valoraciones ya existentes, sin nuevas llamadas al modelo.

### 6.11 Duplicados y revisión de pensamientos

El modelo nunca escribe un texto nuevo de un pensamiento en lugar del usuario ni crea "pensamientos fusionados". Hay dos casos posibles.

- **Lo nuevo cambia lo antiguo.** Ejemplo: antes el autor pensaba que para lanzar el club bastarían 500 euros; al recalcular, resulta que hacen falta 1200. Deja el pensamiento nuevo en `_staging`. El análisis del pool ve que su aspecto revisa el antiguo y propone marcar el antiguo como obsoleto. Tras la confirmación, la base de síntesis se vuelve a armar con el valor nuevo; el pensamiento antiguo queda intacto. Si el usuario responde "ambos son ciertos", la propuesta no se repite.
- **Duplicados.** Entradas distintas dicen lo mismo sin refutar nada. El análisis del pool, teniendo en cuenta los pares parecidos de la búsqueda vectorial, vincula los aspectos coincidentes: el más reciente recibe `duplicate_of` apuntando al más antiguo. En la base de síntesis van como un solo punto con enlaces a todas las entradas de origen. El vínculo se aplica de inmediato, sin preguntar: no se pierde nada, todos los aspectos y entradas siguen en su sitio. La lista de pares vinculados del contenedor se acumula en una sola pregunta, "Revise los duplicados vinculados" («Проверьте связанные дубли»): un vínculo erróneo se puede deshacer escribiendo el número del duplicado (por ejemplo, `a12`).

Si el usuario quiere reunir varios pensamientos en uno, escribe él mismo un pensamiento nuevo. Este pasa por la Fase 1 como una entrada normal, y a partir de ahí se aplican los mismos dos casos.

### 6.12 Contradicciones

Un caso distinto de la obsolescencia: dos aspectos vigentes del mismo tipo se contradicen en su contenido, no porque uno haya quedado obsoleto, sino porque la decisión aún no se ha tomado o se trata de direcciones legítimamente distintas.

**La detección** se hace en el análisis del pool. Se comparan entre sí aspectos del mismo tipo (experiencia con experiencia, idea con idea), no mezclados. La contradicción encontrada se guarda en el pool, y las entradas de origen reciben enlaces mutuos `conflicts_with`. La pregunta al usuario solo se plantea si ambos aspectos pasaron el filtro de valor.

**Resolución optimista.** Junto con la contradicción, el modelo da enseguida su suposición: es correcto el primero, el segundo o ambos (bifurcación). Mientras el usuario no responda, la base de síntesis parte de esa suposición: el supuesto perdedor **no se elimina**, sino que se queda en la base con la marca «предположительно уступает» (presumiblemente cede), y los documentos se redactan teniéndolo en cuenta. La respuesta se aplica volviendo a armar la base con el código, sin una nueva llamada al modelo; si coincide con la suposición, casi no hay nada que recalcular. La suposición y la respuesta van al registro de reflexión.

Opciones de respuesta:

- **"Es correcto el primero" / "Es correcto el segundo"** («Верно первое» / «Верно второе»): el otro aspecto se queda en la base como alternativa considerada y rechazada (secundaria). El documento puede mencionarla si es valiosa para el contexto;
- **"Ambos son ciertos: es una bifurcación"** («Оба верны — это развилка»): ramificación (sección 10.3); ambas direcciones se quedan en la base con la marca de bifurcación, y la síntesis sigue las dos;
- **"No es una contradicción"** («Это не противоречие»): se quita la marca, se eliminan los enlaces `conflicts_with` entre las entradas y el modelo ya no vuelve a proponer este par.

Una contradicción también se puede marcar a mano: el campo `conflicts_with` de la entrada (sección 3.6). Estos pares pasan a la base de síntesis como una lista aparte, «отмечены автором» (marcadas por el autor), y la síntesis los tiene en cuenta.

### 6.13 Comparación con la versión anterior de la base

El último paso del armado es una comparación de la nueva base de síntesis con la anterior por su contenido, no por su texto. El código encuentra los elementos que se han caído de la base o han perdido su condición de principales y descarta las pérdidas explicables: una obsolescencia confirmada por el usuario; la vinculación de duplicados; la inclusión en un compuesto; el traslado de una entrada a otro contenedor; una alternativa rechazada; una pérdida ya reconocida como intencionada. El resto lo evalúa el prompt "Comparación de versiones" («Сравнение версий»): si la pérdida es significativa. Una pérdida significativa da lugar a la pregunta "¿Se ha caído algo importante de la base de síntesis?" («Из базы синтеза выпало важное?»):

- "Así debe ser: la pérdida es intencionada" («Так и нужно — потеря намеренная»): el elemento se anota en `accepted_losses` del pool y no vuelve a plantearse en comparaciones posteriores;
- "Devolver a la base como principal" («Вернуть в базу как первостепенное»): el elemento se fija (`pinned`); a partir de entonces pasa el filtro y es siempre principal.

Mientras la pregunta esté abierta, la base lleva la marca `needs_review` con el motivo «значимая потеря по сравнению с предыдущей версией» ("pérdida significativa respecto a la versión anterior").

## 7. Preguntas y confirmación (`needs_review`)

Un mecanismo único para todos los casos de incertidumbre. El modelo nunca decide estas cuestiones por su cuenta: propone, y el usuario confirma. Mientras no hay respuesta, el trabajo no se detiene: la entrada espera en cuarentena o la base de síntesis parte de la suposición del modelo (sección 6.12), y todo lo demás sigue su curso.

### 7.1 De dónde salen las preguntas

| Tipo (`kind`) | Cuándo | Opciones de respuesta |
| --- | --- | --- |
| `classify`: "Dónde clasificar la entrada" | Confianza inferior al umbral, contenedor nuevo por debajo del umbral alto, la pista no encaja con el contenido (sección 6.5) | La elección del modelo, la opción de la pista, un contenedor nuevo, alternativas, "Sin contenedor"; una respuesta libre es el nombre de un contenedor |
| `mode`: "Cómo procesar el archivo" | El modo del archivo no está claro (sección 6.2) | Dividir en partes por temas / procesar como una sola entrada |
| `also_in`: "¿La entrada también hace falta en otro contenedor?" | Contenedor adicional por debajo del umbral alto | Sí / No |
| `clarify`: "Aclaración sobre una entrada" («Уточнение к записи») | Entrada dudosa o incompleta (sección 6.6) | Opciones del modelo; respuesta libre |
| `outdated`: "¿El pensamiento nuevo revisa el antiguo?" | Análisis del pool (sección 6.11) | Sí, lo antiguo está obsoleto / No, ambos son ciertos |
| `conflict`: "Contradicción entre pensamientos" («Противоречие между мыслями») | Análisis del pool, ambos aspectos pasaron el filtro (sección 6.12) | Es correcto el primero / el segundo / bifurcación / no es una contradicción |
| `dup_fix`: "Revise los duplicados vinculados" | El análisis del pool vinculó duplicados (sección 6.11) | Todos los vínculos son correctos; una respuesta libre son los números de los duplicados erróneos |
| `structure_seed`: "¿El brote se ha convertido en proyecto?" («Росток дорос до проекта?») | Análisis del pool, confianza por debajo del umbral alto | Sí / No |
| `structure_sub`: "¿Separar un subcontenedor?" («Выделить под-контейнер?») | Análisis del pool, confianza por debajo del umbral alto | Sí / No; una respuesta libre es otro nombre |
| `base_loss`: "¿Se ha caído algo importante de la base de síntesis?" | Comparación de versiones de la base (sección 6.13) | La pérdida es intencionada / devolver como principal |
| `product_loss`: "¿Ha desaparecido algo importante en la nueva versión del documento?" («В новой версии документа пропало важное?») | Comparación de versiones del documento (sección 8.4) | La pérdida es intencionada / recuperarlo en la próxima síntesis / revertir el documento |
| `revalidate`: "Entradas parecidas en distintos lugares", "Nueva comprobación: …" («Перепроверка: …») | Entradas parecidas en contenedores distintos (sección 6.8), revalidación profunda (sección 10.1) | Mover, hacer compartida, dejar como está |
| `composite_type`: "¿Nuevo tipo compuesto de aspectos?" («Новый составной тип аспектов?») | Búsqueda de patrones (sección 5.3) | Sí, añadir el tipo / No |
| `dormant`: "El brote lleva mucho tiempo sin desarrollarse" («Росток давно не развивался») | "Muerte silenciosa" de los brotes (sección 3.3) | Sigue vigente / congelar / terminado |
| `text_changed`: "Ha cambiado el texto de una entrada procesada" («Изменён текст обработанной записи») | Edición del texto tras la Fase 1 (sección 4.3) | Convertir la edición en una entrada nueva / restaurar el texto original |

Un caso especial es el borrador de estructura de una carga masiva: no se aprueba mediante una pregunta, sino entero, en un solo archivo (sección 6.3).

Las preguntas iguales no se duplican: cada una tiene una clave, y volver a proponer lo mismo no crea una segunda pregunta. Las decisiones "no" se recuerdan en el pool del contenedor (`rejected`), y el modelo no vuelve a proponer lo mismo.

### 7.2 Dónde se ven las preguntas

- **`open-questions.md`** en la raíz de la bóveda: la lista conjunta de preguntas abiertas de todos los contenedores. El archivo se vuelve a generar al final de cada comando a partir del registro de máquina `.system/questions.json` (sección 16.6). Cada pregunta tiene un número (`Q12`), un título, una fecha, un texto con enlaces a entradas y contenedores, opciones de respuesta y, si procede, un campo de respuesta libre. Encima de las preguntas aparecen los avisos del programa (por ejemplo, «черновик структуры ждёт проверки», "el borrador de estructura espera revisión").
- **La pestaña "Preguntas" del panel del plugin** («Вопросы»): las mismas preguntas, con botones para las opciones y un campo de respuesta (sección 18.2).
- **La propia entrada**: en el YAML, `needs_review: true` y `review_reason`, visibles al abrir el archivo. Las entradas en cuarentena están en `_на_проверку/`.
- **Una base de síntesis y un documento** con una pregunta abierta sobre una pérdida también llevan las marcas `needs_review` y `review_reason`.

### 7.3 Cómo responder

**En `open-questions.md`:**

- en una pregunta con opciones, marcar **exactamente una** opción (`- [x]`; también sirve la «х» cirílica). Si hay varias marcadas, el programa deja la pregunta abierta y escribe encima qué falla;
- una respuesta libre, después de «Ответ:» ("Respuesta:"), en una o varias líneas;
- las respuestas del archivo se aplican al inicio de la siguiente Fase 1.

**En el panel**, la respuesta se aplica en el acto (comando `answer`). Si la respuesta no sirve, el panel muestra por qué.

Qué hace una respuesta libre:

- en "Dónde clasificar la entrada", es el nombre de un contenedor; si no existe, se crea un proyecto nuevo de nivel superior, y el tipo se puede indicar entre paréntesis: "Piso (seed)" (o en ruso, «Квартира (росток)»);
- en una pregunta aclaratoria, la respuesta se convierte en una **entrada nueva** en `_staging`, «уточнение — <запись>» ("aclaración — <entrada>"), con una pista hacia el contenedor de la entrada original, la marca `одна запись` (una sola entrada) y pares «Вопрос — Ответ» ("Pregunta — Respuesta"). El texto de la entrada original no cambia. La entrada nueva se procesa en la siguiente Fase 1 (si se responde en el archivo, en la misma ejecución);
- en "Revise los duplicados vinculados", los números de los duplicados erróneos separados por comas: los vínculos se deshacen;
- en "¿Separar un subcontenedor?", otro nombre para el subcontenedor.

Una respuesta que el programa no puede aplicar (por ejemplo, porque la entrada ya se ha borrado) no se pierde: la pregunta sigue abierta con una observación.

### 7.4 Después de la respuesta

Cada respuesta aplicada:

- se anota en el registro de reflexión junto con la suposición original del sistema y una indicación de si coincidieron (sección 15.3);
- pasa, con el texto de la pregunta y la respuesta elegida, a `_логи/архив вопросов.md`: las preguntas no se borran;
- quita la marca `needs_review` de la entrada si no tiene otras preguntas abiertas;
- marca los contenedores afectados para volver a armar su base de síntesis. Si solo hay que cambiar el orden y las marcas (una contradicción resuelta, un elemento fijado), el código vuelve a armar la base sin llamadas al modelo.

## 8. Fase 2: documentos

Los documentos son una categoría distinta de los aspectos. Los aspectos son materia prima, como las fuentes de la bibliografía de un trabajo académico. Un documento es un texto autónomo que el modelo escribe después de comprender **toda** la base de síntesis del contenedor en su conjunto, no un resumen ni un empalme de aspectos uno por uno.

- **"Archivo resumen"** («Сводный файл»): el documento obligatorio, una descripción general del proyecto en su estado actual.
- **Documentos adicionales**: un conjunto abierto que el modelo determina según el material; por ejemplo, "Modelo financiero" si hay importes y cálculos; "Diario" si hay experiencia, y entonces con las entradas en orden cronológico y con fechas; "Plan", "Preguntas abiertas". No se crea un documento solo por crearlo.

La estructura del contenido de los documentos **no se fija a propósito**: cada material pide una forma distinta, y una plantilla rígida estorbaría. Lo que se configura es el estilo de redacción (sección 8.3). La elección del conjunto de documentos adicionales no está separada de la síntesis: es una única tarea creativa coherente sobre un mismo material, por eso la resuelve un solo prompt, "Síntesis".

### 8.1 Ejecución

La Fase 2 se ejecuta a mano para un contenedor: un botón en la pestaña "Contenedor" del panel o el comando `synth "Nombre"`. No hay programación: el modelo no trabaja de forma continua.

Antes de la síntesis, el programa:

1. acepta las ediciones manuales de los documentos (sección 8.5);
2. comprueba que la base de síntesis está al día. Si el contenedor tiene cambios que la Fase 1 aún no ha integrado, la síntesis no empieza: "primero ejecute la Fase 1" («сначала запустите Фазу 1»). Lo mismo ocurre si todavía no hay base (el contenedor no tiene pensamientos procesados);
3. compara la "firma" de los datos de entrada (la base, el estilo, los datos del contenedor, los documentos actuales, las pérdidas intencionadas y las peticiones de recuperar) con la firma de la síntesis anterior. Si nada ha cambiado, los documentos están al día y no se llama al modelo. Aun así, se puede reescribir todo (`--force`; en la ventana del plugin, respondiendo a una pregunta);
4. estima la ejecución y, si es grande, pide confirmación (sección 14.4).

### 8.2 Qué recibe el modelo

El prompt "Síntesis" recibe:

- los datos del contenedor: nombre, tipo, estado, descripción, padre y vínculos;
- el estilo de redacción (sección 8.3);
- la base de síntesis como texto: los grupos por orden de prioridad y, en cada uno, los elementos con su rango (`primary`/`secondary`), fecha, valor, número de entradas de origen y marcas («спорит с …» (contradice a …), «предположительно уступает (автор ещё не решил)» (presumiblemente cede; el autor aún no ha decidido), «развилка: оба направления живы» (bifurcación: ambas direcciones siguen vivas), «рассмотренная и отклонённая автором альтернатива» (alternativa considerada y rechazada por el autor), «на пересмотре» (en revisión)); en los compuestos, su composición; al final, las contradicciones que el autor ha marcado a mano;
- las versiones actuales de los documentos, si las hay, junto con las ediciones manuales del autor;
- las pérdidas reconocidas como intencionadas (no deben recuperarse) y las peticiones de recuperar lo desaparecido (deben tenerse en cuenta obligatoriamente);
- para un contenedor terminado (`completed`), la exigencia de destacar en el "Archivo resumen" una sección "Resultado final" («Итоговый результат»).

Reglas principales del prompt: todo lo principal debe reflejarse en los documentos; las hipótesis, ideas y planes se presentan como hipótesis, ideas y planes, no como hechos; las contradicciones y bifurcaciones se muestran con honestidad; de las versiones anteriores se conserva lo que sigue siendo cierto, sobre todo las ediciones del autor; no se inventa nada; los documentos se escriben en el idioma de las notas.

La respuesta es texto normal (Markdown): los documentos uno tras otro, y cada uno empieza con la línea `=== ФАЙЛ: Название ===` (=== ARCHIVO: Nombre ===). El programa comprueba que haya al menos un documento, que entre ellos esté el "Archivo resumen", que los nombres no se repitan y que los documentos no estén vacíos; si no, pide al modelo que corrija la respuesta (sección 13.4).

### 8.3 Estilo

El estilo de redacción se configura en tres niveles:

- **general**: `style.global` en los ajustes, para todos los contenedores. Por defecto: «Пиши ясно и по делу, без воды и общих фраз. Сохраняй формулировки автора там, где они точны.» ("Escribe con claridad y al grano, sin relleno ni frases hechas. Conserva las formulaciones del autor donde sean precisas.");
- **del contenedor**: el campo `style` de la ficha (o la pestaña "Contenedor" del panel). También se aplica a los contenedores anidados que no tienen uno propio; prevalece sobre el general;
- **del documento**: el campo `style_override` en el YAML del documento, solo para ese documento en ese contenedor.

El modelo recibe a la vez todos los niveles vigentes, con la indicación de cuál prevalece.

### 8.4 Escritura de documentos y comparación de versiones

Para cada documento cuyo texto ha cambiado, el programa, **antes de escribir los archivos**, compara la versión anterior y la nueva con el prompt "Comparación de versiones" (tipo de objeto: documento). El modelo recibe ambas versiones y las pérdidas ya reconocidas como intencionadas, y enumera lo que ha desaparecido indicando si es significativo. Una pérdida significativa que aún no se ha reconocido como intencionada se convierte en la pregunta "¿Ha desaparecido algo importante en la nueva versión del documento?" («В новой версии документа пропало важное?»):

- **"Así debe ser: la pérdida es intencionada"** («Так и нужно — потеря намеренная»): la pérdida se anota en `accepted_losses` del documento y no vuelve a plantearse. Así el usuario cierra una dirección que ha excluido conscientemente: no está obsoleta, simplemente este documento ya no la necesita;
- **"Recuperar en la próxima síntesis"** («Вернуть при следующем синтезе»): lo desaparecido se pasa a la siguiente síntesis como obligatorio;
- **"Revertir el documento a la versión anterior"** («Откатить документ к прежней версии»): el texto anterior se toma del espejo git (sección 11.2).

Después, los documentos se escriben en la carpeta del contenedor, un archivo por documento, con un encabezado YAML (sección 16.5): el tipo (`summary`, el archivo resumen; `supplementary`, uno adicional), la fecha de generación, a partir de qué armado de la base se escribió, `style_override` y `accepted_losses` de la versión anterior, y la marca `needs_review` si hay una pregunta abierta sobre el documento. Un documento cuyo nombre coincide con el del contenedor o empieza por `_` recibe el añadido «(документ)» ("(documento)") para no confundirse con la ficha ni con las vistas. La nueva versión de cada documento se registra en el espejo git.

Los documentos que el modelo no ha reescrito esta vez se quedan como están: no se elimina nada. Tras la síntesis, las peticiones de recuperar lo desaparecido se retiran y el contenedor se reindexa: el comienzo del "Archivo resumen" pasa a ser su representación para la clasificación (sección 6.4).

### 8.5 Ediciones manuales de los documentos

Un documento se puede editar a mano. La edición no es un cambio directo de la base de síntesis (la base no se edita a mano), sino **material nuevo de entrada**. Al comienzo de cada Fase 1 (y antes de cada Fase 2), el programa compara cada documento con su última versión en el espejo git. Si difieren, en `_staging` aparece una entrada «правка документа — <документ> (<контейнер>)» ("edición del documento — <documento> (<contenedor>)"): con una pista que apunta al contenedor, el tipo `product_edit` y solo las líneas modificadas: «Автор добавил или переписал: …» ("El autor añadió o reescribió: …"), «Автор убрал: …» ("El autor quitó: …"). A partir de ahí pasa por la Fase 1 como una entrada normal: sus aspectos entran en el pool, la base de síntesis se vuelve a armar y la siguiente síntesis tiene en cuenta la edición como una fuente de pleno derecho, en pie de igualdad con las demás.

La edición en sí se conserva en el documento: el modelo recibe la versión actual del documento con las ediciones y las mantiene si siguen siendo ciertas.

## 9. Prompts

Todas las llamadas al modelo de lenguaje se reúnen en un conjunto de prompts. Cada prompt es un archivo Markdown aparte en la carpeta `prompts/` del programa: se puede leer y modificar. Los mismos prompts funcionan en el modo API y en el modo manual a través de un chat web (sección 13.5).

### 9.1 Cómo están construidos

**Criterio de separación.** Hay un prompt aparte donde la decisión es de naturaleza fundamentalmente distinta (la clasificación, la extracción y la síntesis de texto son "cabezas" de razonamiento diferentes) o donde el paso por sí mismo puede terminar en una pregunta al usuario. Se unen los pasos que son lógicamente inseparables (el segundo no tiene sentido sin el resultado del primero dentro de un mismo razonamiento) y que juntos caben en un volumen razonable.

**El contexto no se recorta.** El límite es el dinero, no los tokens (sección 14): los prompts no se comprimen artificialmente, y la calidad del análisis importa más que el volumen. Si el material no cabe en la ventana del modelo, el propio código lo divide en partes (sección 13.4).

**Sustituciones.** Las partes variables del prompt se escriben como `{{nombre}}`. Antes de enviarlo, el programa comprueba que cada sustitución tenga valor; las listas y los objetos se sustituyen como JSON.

**Formato de respuesta.** Los prompts cuya respuesta analiza el programa responden estrictamente en JSON. El campo `reasoning` va primero (una decisión escrita después de la explicación es más precisa) y pasa directamente al registro de razonamientos (sección 15.2). "Condensación" y "Síntesis" escriben texto normal (Markdown). El programa comprueba cada respuesta: si se puede analizar, si están todos los campos, si existen los `id` mencionados y si los números están dentro de los límites permitidos. Si hay un error, el modelo recibe una lista de observaciones y envía una respuesta corregida (sección 13.4).

**Idioma.** Los prompts están escritos en ruso. Las respuestas del modelo (textos de aspectos, preguntas, documentos) están en el idioma de las notas.

**Edición de prompts.** Los prompts se pueden adaptar, con cuidado: el programa espera que la respuesta mantenga el mismo formato. Al actualizar el programa, las nuevas versiones de los prompts se instalan encima, y las que el usuario modificó se guardan en `prompts/_прежние/` (anteriores) (sección 19.3).

### 9.2 Lista de prompts

| Prompt | Cuándo se llama | Qué hace | Respuesta |
| --- | --- | --- | --- |
| "Estructura" («Структура») | Bootstrap, pasada 1 (sección 6.3) | A partir de todo el material de la carga propone un árbol de contenedores: nombre, tipo, descripción, padre, vínculos; cada parte siguiente del material precisa el borrador | JSON |
| "Clasificación" («Классификация») | Cada archivo nuevo o parte de un diario (sección 6.4); revalidación profunda (sección 10.1) | Segmentos (solo en Bootstrap), el contenedor con su confianza sin la pista y la confianza de la opción de la pista, alternativas, contenedores adicionales, tipo de entrada, carácter incompleto, nivel de ruido, una suposición sobre el modo | JSON |
| "Preguntas" («Вопросы») | Entrada en cuarentena o incompleta (sección 6.6) | Preguntas aclaratorias breves al autor, con opciones de respuesta cuando es posible | JSON |
| "Condensación" («Уплотнение») | Nivel de ruido por encima del umbral (sección 6.7) | Comprime el texto a una forma densa sin perder nada de contenido; en los diálogos se apoya en las réplicas del usuario | texto |
| "Extracción" («Извлечение») | Cada entrada con contenedor (sección 6.9) | Descompone una entrada en aspectos simples, sin mirar el resto del pool | JSON |
| "Análisis del pool" («Анализ пула») | Cada contenedor con cambios (sección 6.10) | Aspectos compuestos (montar, ampliar, disolver), duplicados, lo obsoleto, contradicciones con una suposición, propuestas sobre la estructura | JSON |
| "Valor" («Ценность») | Cada contenedor con cambios (sección 6.10) | Valora de 0 a 100 el valor de contenido de cada elemento en el contexto del contenedor | JSON |
| "Comparación de versiones" («Сравнение версий») | Armado de la base de síntesis (sección 6.13) y Fase 2 (sección 8.4) | Si es significativa cada pérdida entre la versión anterior y la nueva. Una sola plantilla; el tipo de objeto es un parámetro: base de síntesis o documento | JSON |
| "Síntesis" («Синтез») | Fase 2 (sección 8) | El "Archivo resumen" y un conjunto de documentos adicionales a partir de toda la base de síntesis | texto |
| "Nuevo tipo compuesto" («Новый составной тип») | Búsqueda de patrones, tras la selección técnica de grupos (sección 5.3) | Si entre los grupos candidatos hay un patrón estable; fórmula, nombre y ejemplo del nuevo tipo | JSON |
| "Umbrales" («Пороги») | Consejo sobre los umbrales del contenedor (sección 10.5) | Propone valores de umbrales con una explicación a partir de las estadísticas de decisiones | JSON |

### 9.3 Lo que hace el código y no el modelo

No hace falta un modelo de lenguaje cuando la decisión es determinista. De esto se encarga el código:

- detectar la codificación, la fecha y el marcado de diálogos; dividir un diario por fechas; numerar párrafos y copiar segmentos literalmente;
- aplicar los umbrales y el desplazamiento de la pista; crear contenedores, mover entradas, entradas compartidas;
- búsqueda vectorial: entradas parecidas, pares de posibles duplicados, reducción de la lista de contenedores, grupos candidatos a nuevos tipos compuestos;
- preselección de aspectos según las fórmulas de los tipos compuestos;
- filtrado, agrupación y ordenación por rango según las valoraciones de valor ya hechas; orden de los grupos según la tabla de prioridad;
- búsqueda de elementos caídos al comparar versiones de la base de síntesis y descarte de las pérdidas explicables;
- estadísticas de decisiones para el consejo sobre umbrales y comprobación de los valores propuestos;
- comprobación del formato de cada respuesta del modelo.

## 10. Operaciones bajo demanda

Mecanismos que funcionan por encima del trabajo principal de las Fases 1 y 2. El usuario los invoca cuando decide que hacen falta. Unos son gratuitos (una acción organizativa, sin modelo); otros gastan llamadas al modelo, y entonces el programa muestra de antemano una estimación (sección 14.4).

| Operación | Cómo invocarla | Modelo |
| --- | --- | --- |
| Revalidación profunda | el botón "Revalidación…" («Ревалидация…») del panel o "Comprobar de nuevo el reparto" («Перепроверить раскладку») en la pestaña "Contenedor"; `revalidate` | una llamada por entrada |
| Impugnar el reparto | el campo `container` de la entrada | no hace falta |
| Ramificación | la respuesta "Ambos son ciertos: es una bifurcación" a la pregunta sobre una contradicción | no hace falta |
| Búsqueda de patrones | el botón "Patrones" («Паттерны»); `patterns` | una llamada |
| Consejo sobre umbrales | "Consultar a la IA" («Посоветоваться с ИИ») en la pestaña "Contenedor"; `advise` | una llamada |

### 10.1 Revalidación

Un reparto hecho una vez puede quedarse anticuado con el tiempo: aparecen contenedores nuevos, las descripciones de los antiguos se precisan, se acumula contexto. Se puede volver a comprobar de dos maneras.

**Gratuita: por vecinos.** Funciona sola, como efecto secundario de la Fase 1 normal: si una entrada nueva coincide casi por completo en significado con una entrada de otro contenedor, el programa pregunta si todo está bien repartido (sección 6.8). Ni una sola llamada adicional al modelo.

**Profunda: a petición.** El usuario elige un contenedor o todas las entradas a la vez. Para cada entrada procesada, por orden de fechas, el programa vuelve a llamar al prompt "Clasificación", en modo normal, con la lista actual de contenedores y **sin la pista** del autor: hace falta la opinión limpia del modelo. Se usa el texto de trabajo (el condensado, si existe).

- El modelo asigna la entrada a otro contenedor existente con una confianza no inferior al umbral `classification` de ese contenedor: pregunta "Nueva comprobación: ¿la entrada está en el lugar equivocado?" («Перепроверка: запись лежит не там?»): moverla, hacerla compartida (si la entrada ya está en un contenedor) o dejarla como está.
- El modelo propone un contenedor nuevo con una confianza no inferior a `high`: pregunta "Nueva comprobación: ¿hace falta un contenedor nuevo?" («Перепроверка: нужен новый контейнер?»): crearlo y mover la entrada, o dejarla como está.
- En otro caso, el reparto queda confirmado y no hay pregunta.

El modelo no mueve nada por su cuenta: solo propone. Cada una de sus opiniones se escribe en el registro de reflexión (`deep_revalidation`), con la respuesta del usuario al lado.

Es una llamada al modelo por cada entrada, así que antes de empezar el programa muestra el número de entradas y una estimación de tiempo y dinero, y **siempre** pide confirmación. Sin el plugin ni la consola, se confirma con la opción `--yes`; `--count` solo cuenta las entradas. El progreso se guarda después de cada entrada: una revalidación interrumpida (un fallo, el botón "Detener") continúa desde el mismo punto en la siguiente ejecución para el mismo objetivo.

Cuándo conviene ejecutarla: la estructura ha cambiado de forma notable (se han separado subcontenedores, un brote se ha convertido en proyecto), han aparecido contenedores nuevos o el reparto de entradas antiguas genera dudas.

### 10.2 Impugnar el reparto

Gratis y sin modelo: basta con cambiar el campo `container` de la entrada y escribir el `[[nombre]]` de otro contenedor (sección 3.6). Si el campo queda vacío, la entrada va a `_unsorted`; si el contenedor no existe, aparece un aviso y la entrada se queda donde está.

Al comienzo de la siguiente Fase 1, el programa mueve el archivo de la entrada, quita sus aspectos del pool del contenedor anterior y los añade al pool del nuevo (sin nueva extracción: los aspectos son los mismos), y las bases de síntesis de ambos contenedores se vuelven a armar. Si la entrada no tenía contenedor, sus aspectos se extraen de nuevo.

El traslado queda en el registro de cambios («классификация оспорена правкой YAML», "clasificación impugnada mediante una edición del YAML") y en el registro de reflexión: a la suposición original del modelo se añade la decisión del usuario con la marca «не совпало» ("no coincidió"). Así se acumulan estadísticas de errores de reparto: el consejo sobre umbrales ve cuántas entradas repartidas sin pregunta movió después el usuario (sección 10.5).

### 10.3 Ramificación

A veces dos pensamientos divergen no porque uno sea erróneo u obsoleto, sino porque son direcciones legítimamente distintas y el autor quiere mantener ambas. Ejemplo: en "App para correr" hay una idea de vender la aplicación con un pago único y otra de suscripción, y todavía no se ha elegido.

El programa no crea ramas por su cuenta ni prepara una infraestructura aparte para ellas. La ramificación es una decisión consciente del usuario: la respuesta "Ambos son ciertos: es una bifurcación" («Оба верны — это развилка») a la pregunta "Contradicción entre pensamientos" (sección 6.12). Tras esa respuesta:

- ambos aspectos se quedan en la base de síntesis en pie de igualdad, con la marca «развилка: оба направления живы» (bifurcación: ambas direcciones siguen vivas); ninguno pasa a ser una alternativa rechazada;
- la síntesis desarrolla ambas direcciones: el "Archivo resumen" muestra la bifurcación con honestidad, entre las preguntas abiertas, en lugar de elegir un ganador en nombre del autor;
- esta pareja ya no se plantea como contradicción.

El modelo también puede suponer por sí mismo una bifurcación cuando encuentra una contradicción; en ese caso, hasta que el usuario responda, ambos aspectos también van a la base con esa marca.

Cuando se haya tomado la decisión, basta con escribir una entrada nueva sobre ello: el análisis del pool verá que el pensamiento nuevo revisa el antiguo (sección 6.11).

### 10.4 Búsqueda de patrones

Busca conjuntos estables de distintos tipos simples de aspectos que no cubre ningún tipo compuesto existente, y propone un nuevo tipo compuesto. Cómo funciona la selección y qué pasa después de la respuesta se describe en la sección 5.3. Es una llamada al modelo para todos los grupos encontrados; si no hay grupos adecuados, el programa no llama al modelo. Las propuestas llegan como la pregunta "¿Nuevo tipo compuesto de aspectos?" («Новый составной тип аспектов?»); un tipo aceptado pasa a ser permanente para todos los contenedores, y uno rechazado no se vuelve a proponer.

Tiene sentido ejecutarla de vez en cuando, cuando se han acumulado muchos aspectos en los contenedores.

### 10.5 Umbrales del contenedor y consejo del modelo

**Umbrales generales y propios.** Las decisiones que toma el código (sección 6.5) se basan en umbrales. Los generales se fijan en los ajustes (`thresholds`), pero los contenedores son distintos: para un proyecto vivo con notas frecuentes conviene repartir con más audacia; para un tema delicado, preguntar más a menudo. Por eso casi cualquier umbral puede tener un valor propio en un contenedor. El umbral propio se aplica al contenedor y a todos los anidados en él, mientras el anidado no tenga el suyo; si no, se aplica el general. El origen de cada valor (propio, del padre o general) se ve en la pestaña "Contenedor".

| Umbral | Clave | Por defecto | Qué decide |
| --- | --- | --- | --- |
| Reparto sin pregunta («Раскладка без вопроса») | `classification` | 70 | A partir de qué confianza la entrada se reparte sola; por debajo, cuarentena y pregunta |
| Peso de su pista («Вес вашей подсказки») | `hint_shift` | 15 (0–50) | Cuántos puntos de confianza se suman a la opción de la pista |
| Confianza alta («Высокая уверенность») | `high` | 90 | A partir de qué confianza el programa crea por sí mismo contenedores y subcontenedores, hace compartida una entrada, convierte un brote en proyecto |
| Suposición sobre el modo del archivo («Догадка о режиме файла») | `mode_guess` | 70 | A partir de qué confianza se acepta el modo del archivo sin pregunta. Solo general: el archivo aún no está repartido |
| Condensación («Уплотнение») | `compaction` | 60 | A partir de qué nivel de ruido la entrada se comprime primero (con el ajuste de la fuente, sección 6.7) |
| Valor mínimo («Минимальная ценность») | `value_min` | 30 | Los aspectos con más valor que este van a la base de síntesis |
| Principal («Первостепенное») | `value_primary` | 70 | A partir de qué valor un aspecto es principal |
| Similitud para buscar duplicados («Похожесть для поиска дублей») | `duplicate_similarity` | 0,86 | A partir de qué similitud se muestran al modelo pares de aspectos como posibles duplicados |
| Similitud de vecinos («Похожесть соседей») | `neighbor_similarity` | 0,88 | A partir de qué similitud las entradas de contenedores distintos generan una pregunta sobre el reparto |
| Similitud para patrones («Похожесть для паттернов») | `pattern_similarity` | 0,8 | Cuánto deben parecerse los aspectos para que la búsqueda de patrones los considere un conjunto |
| Días hasta la pregunta sobre el brote («Дней до вопроса о ростке») | `seed_dormancy_days` | 90 (7–3650) | Tras cuántos días de silencio un brote recibe la pregunta "¿sigue vigente?". Solo en brotes |

Escalas: confianza, nivel de ruido y valor, de 0 a 100; similitud, de 0,5 a 0,99.

Qué contenedor determina el umbral: en el reparto, aquel donde se coloca la entrada (para un contenedor nuevo, su futuro padre; para uno adicional, el propio contenedor adicional); en la condensación y la búsqueda de vecinos, el contenedor de la entrada; en el armado de la base, la búsqueda de duplicados, las propuestas sobre la estructura y la búsqueda de patrones, el contenedor del pool.

**Dónde se fijan.** En la pestaña "Contenedor" del panel: un control deslizante y un campo para cada umbral; un campo vacío significa el valor del padre o el general (se muestra en gris), y "↺" quita el umbral propio. O a mano, en el campo `thresholds` de la ficha del contenedor:

```yaml
thresholds:
  classification: 80
  дубли: 0,9
```

Se admiten nombres en ruso (раскладка — reparto, подсказка — pista, высокая — alta, уплотнение — condensación, ценность — valor, первостепенное — principal, дубли — duplicados, соседи — vecinos, паттерны — patrones, дремота — letargo), la coma en los decimales y el signo de porcentaje ("80%"; en la escala de 0 a 1, "86%" equivale a 0,86). Un umbral desconocido o un valor fuera de rango se omite con un aviso.

Cuándo surten efecto: los umbrales de reparto y condensación, en las entradas nuevas; los umbrales de valor, en la siguiente Fase 1, cuando el código vuelve a armar la base de síntesis sin llamar al modelo. Los cambios de los umbrales propios y del estilo quedan en el registro de cambios con la marca «пользователь» ("usuario").

**Consejo del modelo.** Elegir los umbrales a ojo es difícil, por eso el programa puede consultar al modelo. Primero, el código reúne las estadísticas de decisiones de este contenedor a partir del registro de reflexión y del estado: cuántas entradas se repartieron sin pregunta y cuántas de ellas movió después el usuario; cuántas preguntas de reparto hubo y si el modelo acertó; con qué frecuencia la pista discrepó de la opinión del modelo; cuántas propuestas de "la entrada también hace falta aquí" y de reorganización de la estructura se aceptaron y cuántas se rechazaron; la distribución del nivel de ruido y del valor (mínimo, cuartiles, mediana, histograma) y cuántos elementos están justo en los umbrales; cuántas pérdidas devolvió el usuario a la base y cuántas reconoció como intencionadas; cuántos vínculos de duplicados se quitaron a mano; cómo terminaron las preguntas sobre vecinos parecidos; para un brote, cuántos días lleva sin pensamientos nuevos.

El prompt "Umbrales" («Пороги») recibe la descripción del contenedor, una tabla de umbrales (valor actual, de dónde viene, valor general, rango admitido), estas estadísticas y un breve resumen de ellas en lenguaje humano. El modelo responde con una conclusión en palabras sencillas y recomendaciones: el umbral, el nuevo valor y en qué cifras se basa. El código comprueba cada recomendación (umbral conocido, valor dentro del rango, `seed_dormancy_days` solo para un brote, sin repeticiones) y descarta los consejos de "dejarlo como está".

El consejo **no cambia nada por sí mismo**. La ventana "Consejo de la IA sobre los umbrales" («Совет ИИ по порогам») muestra la conclusión, los cambios propuestos "antes → después" con explicaciones (todos marcados por defecto) y una lista desplegable "En qué se basa el consejo" («На чём основан совет»). "Aplicar lo seleccionado" («Применить выбранное») escribe los valores marcados en el campo `thresholds` del contenedor; surten efecto a partir de la siguiente Fase 1. El último consejo se guarda y se ve en la pestaña "Contenedor" ("Hay un consejo de la IA", «Есть совет ИИ»).

El consejo se escribe en el registro de reflexión (`thresholds_advice`). Cuando después el usuario cambia los umbrales del contenedor, el programa añade al consejo la decisión: aceptado por completo, en parte o rechazado, y qué valores exactamente se tomaron. Así se ve hasta qué punto se puede confiar en los consejos del modelo.

## 11. Fiabilidad

### 11.1 No se elimina nada

El programa no borra nada de lo que ha llegado del usuario o se ha derivado de ello. Lo obsoleto, lo erróneo y lo rechazado se marca y se queda en su sitio: la historia de un pensamiento siempre se puede seguir.

| Qué | En lugar de eliminarlo |
| --- | --- |
| Archivo recibido | Se guarda sin cambios en `_исходники/` (sección 4.1) |
| Texto de una entrada procesada | No cambia; una edición se convierte en una entrada nueva (sección 4.3) |
| Entrada | `status: outdated`: el pensamiento ya no es vigente y sus aspectos quedan obsoletos (sección 3.6) |
| Aspecto | El estado `outdated` con un enlace al aspecto que lo sustituyó, la marca `duplicate_of`, la inclusión en un compuesto (sección 5.5) |
| El lado perdedor de una contradicción | Se queda en la base de síntesis como alternativa rechazada (sección 6.12) |
| Un elemento caído de la base | Se queda en el pool; las pérdidas reconocidas como intencionadas, en `accepted_losses` (sección 6.13) |
| Versiones anteriores de documentos y bases | El espejo git (sección 11.2); un documento se puede revertir respondiendo a una pregunta (sección 8.4) |
| Contenedor | El estado `completed` o `dormant` (sección 3.5) |
| Una pregunta respondida | Pasa a `_логи/архив вопросов.md` (histórico de preguntas) junto con la respuesta (sección 15) |
| Un "no" a una propuesta del modelo | Se recuerda, y la propuesta no se repite (sección 7) |

Lo único que el usuario puede eliminar por sí mismo es la ficha de un contenedor; sus entradas pasan entonces a `_unsorted` con un aviso (sección 3.6). No hace falta eliminar archivos de entradas: para eso existe `status: outdated`.

### 11.2 Versiones

Se guardan versiones de lo que el programa reescribe por completo: las bases de síntesis y los documentos de la Fase 2. El resto no necesita versiones: las entradas no cambian después de procesarse, y la historia de los pools se sigue por las marcas (sección 11.1).

Técnicamente es un espejo git en `.system/versions/`. Git está integrado en el programa (la biblioteca dulwich), no hace falta instalarlo aparte. Al espejo van versiones de texto: para una base de síntesis, su vista (`_база синтеза.md`); para un documento, su texto. Al final de cada comando, si algo ha cambiado, el programa hace un commit «прогон <дата и время>» ("ejecución <fecha y hora>"). Sin la biblioteca, el programa sigue funcionando, solo que sin historial.

El espejo sirve para tres fines:

- **comparar versiones de un documento**: la Fase 2 contrasta la versión nueva con la anterior (sección 8.4);
- **ediciones manuales de documentos**: la diferencia entre el archivo de la bóveda y la última versión del espejo es precisamente la edición del usuario (sección 8.5);
- **reversión**: la respuesta "revertir el documento" devuelve la versión anterior desde el espejo.

Para comparar bases de síntesis, el programa también guarda una versión anterior legible por máquina: `data/bases/<id>.prev.json` (sección 6.13).

### 11.3 Fallos e interrupciones

**Guardado después de cada paso.** El estado de la cadena de procesamiento (`.system/state.json`), las preguntas y los vectores se guardan después de cada paso: un archivo aceptado, una entrada clasificada, una porción de un archivo grande, una extracción, una etapa del armado de la base de síntesis, un documento. No hace falta un intervalo fijo: guardar cuesta menos que una sola llamada al modelo. Al reiniciar tras un fallo, se continúa desde el último paso guardado, no desde el principio. Una extracción interrumpida no deja aspectos de más: el reintento empieza desde cero. En el modo manual a través de un chat web, esto mismo permite detenerse mientras se espera una respuesta y continuar más tarde (sección 13.5).

**Detención.** El plugin tiene dos botones:

- "Detener" («Стоп»): se cancela la cola de ejecuciones (salvo las acciones rápidas sin modelo, como las respuestas a preguntas y las ediciones del YAML), y la ejecución actual termina su paso, lo guarda todo y se detiene. El plugin deja la marca `.system/stop`, y el programa la comprueba en cada paso, antes de cada llamada al modelo y durante las pausas entre reintentos;
- "Interrumpir ya" («Прервать сразу»): el proceso termina de inmediato; el paso actual no se guardará, pero todo lo hecho antes está intacto.

En la consola hace lo mismo Ctrl+C (como "Detener") o cerrar la ventana. La detención por presupuesto (sección 14.3) lo guarda todo igual que "Detener". Después de cualquier detención, el panel ofrece "Continuar (Fase 1)" («Продолжить (Фаза 1)»).

**Bloqueo.** Dos ejecuciones simultáneas sobre la misma bóveda son imposibles: el archivo `.system/lock` se bloquea con los medios del sistema operativo, y la segunda ejecución recibe el mensaje «Программа уже работает с этим хранилищем в другом окне» ("El programa ya está trabajando con esta bóveda en otra ventana"). Si el programa se ha caído, el bloqueo se libera solo. El plugin pone sus ejecuciones en cola, así que desde él esta situación no se produce.

**Fallos de conexión con el modelo.** La petición se repite ante una respuesta 429 (demasiadas peticiones), errores del servidor 5xx, una conexión cortada o una respuesta que no está en JSON, con pausas de 5, 20, 60 y 120 segundos; "Detener" interrumpe la pausa. Una clave incorrecta (401, 403) y el desbordamiento de la ventana del modelo no se reintentan: el programa se detiene con un mensaje claro (sección 13.4).

**Operaciones con archivos.** En Windows, un archivo a veces está ocupado durante un instante por Obsidian, un antivirus o la sincronización en la nube. El programa repite la operación varias veces con pausas cortas. Todos los archivos se escriben de forma atómica: primero en un archivo temporal al lado y luego por sustitución, así que un fallo a mitad de la escritura no deja un archivo cortado.

**Un error inesperado** se registra en `_логи/ошибки.log` (errores) con detalles, y con ellos se arma un informe para el desarrollador (sección 15.4).

## 12. Búsqueda de lo parecido: embeddings

### 12.1 Para qué

Un embedding es un vector numérico que transmite el significado de un texto: cuanto más cercanos son los vectores, más cercano es el significado. Los vectores los calcula un modelo de embeddings aparte, sin el modelo de lenguaje y sin pagar por cada decisión. El programa los usa donde hace falta encontrar rápidamente algo parecido entre muchos elementos:

| Dónde | Qué se busca | Nivel de vectores | Umbral |
| --- | --- | --- | --- |
| Revalidación gratuita (sección 6.8) | Entradas casi coincidentes de otros contenedores (las 5 más cercanas) | entradas | `neighbor_similarity` |
| Análisis del pool (sección 6.11) | Pares de aspectos que pueden ser duplicados y se muestran al modelo | aspectos | `duplicate_similarity` |
| Clasificación (sección 6.4) | Si hay más contenedores que `limits.max_containers_in_prompt` (150), en la petición van los más cercanos por significado y sus padres | contenedores | — |
| Búsqueda de patrones (sección 5.3) | Grupos de aspectos cercanos de tipos distintos | aspectos | `pattern_similarity` |

El modelo de embeddings no depende de la elección del modelo de lenguaje: devuelve un vector, el almacén de vectores lo guarda y busca en él, y no necesitan saber nada el uno del otro. Por defecto funciona **en este ordenador**: no necesita los recursos del modelo de lenguaje, y las notas personales en bruto no salen fuera ni siquiera para buscar. Los embeddings en la nube son una opción (sección 12.4). El modelo solo se necesita durante las ejecuciones (Fase 1, comprobación de conexión); no ocupa memoria de forma permanente.

### 12.2 Almacén de vectores

Vectores de tres niveles:

- **entradas**: a partir del texto de trabajo de la entrada (el condensado, si existe);
- **aspectos**: a partir del texto del aspecto;
- **contenedores**: a partir del nombre, la descripción y el comienzo del "Archivo resumen" (hasta 1500 caracteres); mientras no hay documentos, a partir de los 12 aspectos más valiosos del pool. El vector de un contenedor se actualiza cuando el contenedor se crea o cambia, después de armar su base de síntesis y después de la Fase 2.

Se guardan en `.system/vectors/` en archivos propios: una matriz de números (numpy) por nivel y, al lado, la lista de `id` y el nombre del modelo con el que se calcularon. La búsqueda es por similitud coseno, comparando con todos: para miles y decenas de miles de entradas lleva fracciones de segundo. No hace falta una base de datos vectorial aparte, y la instalación en Windows no requiere compilar nada ni dependencias adicionales. La escala del uso personal está lejos del techo de esta solución.

**Cambio de modelo.** Los vectores de modelos distintos son incompatibles. El nombre del modelo en los ajustes (`embeddings.model`) sirve de etiqueta de los vectores: si al iniciar es otro, el programa avisa de cuánto tardará y recalcula por sí mismo todos los vectores de entradas, aspectos y contenedores. Cambiar el modelo de lenguaje no requiere recalcular.

**Textos largos.** Un texto más largo que `embeddings.max_chars` (6000 caracteres) se recorta para la búsqueda; la entrada en sí no cambia. Si el servidor responde que el texto no cabe en la ventana del modelo, el programa lo acorta a la mitad y lo vuelve a intentar. Los textos se envían en lotes de `batch` (16); para el modelo propio, además, con un máximo de 16 000 caracteres por petición, para que el cálculo en el procesador no choque con el tiempo de espera de la respuesta.

**Fallos.** Si no hay respuesta o hay un error del servidor, se reintenta con pausas de 3, 10 y 30 segundos. Si el servidor del modelo propio no está en marcha, el programa lo inicia por sí mismo (sección 12.3) y espera mientras se carga el modelo. Si aun así no consigue conectar, el programa se detiene e indica qué hacer.

### 12.3 Modelo propio en llama.cpp

Por defecto es **KaLM-Embedding-Gemma3 12B**: un modelo multilingüe con una ventana de hasta 32 768 tokens (cuantización Q4_K_S, unos 6,9 GB; 48 capas, un vector de 3840 números). Funciona a través de `llama-server` del proyecto llama.cpp en formato OpenAI (`/v1/embeddings`).

No hace falta instalar nada a mano. El botón "Iniciar el modelo…" («Запустить модель…») (Ajustes → Segundo Cerebro → Modelos → Embeddings → "Modelo propio"; en la interfaz: Второй мозг → Модели → Эмбеддинги → «Своя модель») abre la ventana de inicio:

- **qué tiene el ordenador**: procesador, núcleos e hilos, memoria RAM (total y libre), tarjetas gráficas y su memoria;
- **parámetros:** dónde calcular (procesador o tarjeta gráfica); la compilación de llama.cpp para la tarjeta gráfica; cuántas capas del modelo mantener en la tarjeta gráfica (las que quepan, todas o un número propio); contexto; cuantización de la caché KV; hilos del procesador (botón "Por núcleos", «По ядрам»); puerto; tras cuántos minutos de inactividad descargar el modelo de la memoria; si el propio programa debe iniciar el servidor cuando haga falta; carpeta del modelo;
- **avisos**: falta memoria o no se encuentra la tarjeta gráfica;
- **qué se descargará** (una sola vez) y si hay suficiente espacio en disco.

"Iniciar" («Запустить»; el comando `llama start`) descarga lo que falta, inicia el servidor en segundo plano, espera a que el modelo se cargue en memoria (hasta 15 minutos en un disco lento) y escribe por sí mismo la dirección del servidor y el nombre del modelo en los ajustes. El progreso de la descarga se ve en el panel; "Detener" la interrumpe, y el siguiente inicio la reanuda desde el mismo punto. La integridad del modelo se comprueba con una suma de control.

**Qué se descarga:**

| Qué | De dónde | Tamaño |
| --- | --- | --- |
| Modelo | Hugging Face, `mradermacher/KaLM-Embedding-Gemma3-12B-2511-GGUF` | unos 6,9 GB |
| llama.cpp para procesador | GitHub, compilaciones listas de `ggml-org/llama.cpp` | unos 25 MB |
| llama.cpp Vulkan, para cualquier tarjeta gráfica | el mismo sitio | unos 38 MB |
| llama.cpp CUDA, para NVIDIA, solo Windows | el mismo sitio, junto con las bibliotecas CUDA | unos 680 MB |
| Bibliotecas de Microsoft Visual C++ | Microsoft, solo Windows y solo si faltan | unos 25 MB |

En macOS hay una sola compilación (con Metal); en Linux, para procesador o Vulkan. Si `llama-server` ya está instalado en el ordenador, también sirve para calcular en el procesador.

**Parámetros** (`embeddings.server` en los ajustes):

| Parámetro | Por defecto | Significado |
| --- | --- | --- |
| `device` | `cpu` | `cpu`, procesador; `gpu`, tarjeta gráfica (muchas veces más rápida) |
| `build` | `auto` | Compilación para la tarjeta gráfica: `auto`, CUDA para NVIDIA y, si no, Vulkan; `cuda`; `vulkan` |
| `gpu_layers` | `auto` | Capas en la tarjeta gráfica: `auto`, las que quepan; `all`, las 48; o un número; el resto lo calcula el procesador |
| `ctx` | 4096 | Contexto, en tokens: el texto más largo que se procesa de una vez (4096 son unos 12–14 mil caracteres). El programa recorta igualmente los textos largos (sección 12.2), por eso 4096 suele bastar |
| `kv_cache` | `f16` | Cuantización de la caché KV. A este modelo casi no le aporta nada: lee cada texto entero de una sola pasada y no guarda caché KV |
| `threads` | 0 | Hilos del procesador; 0, llama.cpp decide por sí mismo |
| `port` | 8081 | La dirección del servidor es `http://127.0.0.1:<puerto>/v1`; el servidor solo escucha en este ordenador |
| `sleep_min` | 15 | Tras cuántos minutos de inactividad descargar el modelo de la memoria (la siguiente petición lo carga en unos segundos); 0, no descargarlo |
| `autostart` | `true` | Si el servidor no está en marcha (por ejemplo, tras reiniciar), el programa lo inicia por sí mismo en la Fase 1 o en la comprobación de conexión, con los parámetros guardados y sin descargar nada |
| `models_dir` | vacío | Carpeta del modelo; vacío, `models/` en la carpeta del programa |

**Memoria.** Cuánto ocupa el servidor con el modelo: el propio modelo más un búfer de trabajo que crece con el contexto:

| Contexto, tokens | 2048 | 4096 | 8192 | 16 384 | 32 768 |
| --- | --- | --- | --- | --- | --- |
| Memoria, GB | 7,8 | 8,4 | 9,6 | 12,6 | 20,1 |

En el procesador hacen falta al menos 16 GB de RAM; si hay menos o el contexto elegido no cabe, la ventana de inicio avisa. Para que todo el modelo quepa en la tarjeta gráfica, hacen falta unos 8 GB de memoria de vídeo; si hay menos, parte de las capas se queda en la RAM: más lento, pero funciona.

**Cómo se inicia el servidor.** `llama-server -m <modelo> --embedding --pooling last --alias <nombre> --host 127.0.0.1 --port <puerto> -c <contexto> -np 1 -b <contexto> -ub <contexto>`; para el procesador, además, `-ngl 0`; para la tarjeta gráfica, el número de capas; y si hace falta, los hilos y el tiempo de inactividad. El tamaño del lote es igual al contexto por una razón: el modelo no es causal y lee el texto entero de una sola pasada, por eso todo el texto debe caber en un lote; si no, el servidor responde "input is too large".

**Dónde está cada cosa** (en la carpeta del programa): `models/`, el modelo; `llama.cpp/<compilación>/`, llama-server y sus bibliotecas; `llama.cpp/server.json`, el servidor en marcha (número de proceso, puerto, parámetros); `llama.cpp/server.log`, el registro del servidor del último inicio (se puede abrir desde los ajustes).

**Gestión.** En los ajustes se ve si el modelo está descargado, qué compilaciones de llama.cpp hay y si el servidor está en marcha; "Parar" («Остановить») libera memoria (el programa volverá a iniciar el servidor cuando haga falta); "Reiniciar…" («Перезапустить…») lo reinicia con parámetros nuevos. Comandos: `llama status`, `llama start`, `llama stop`, `llama download` (sección 20).

**Errores típicos**, cada uno con una indicación de qué hacer: el puerto lo ocupa otro programa (elegir otro puerto); no se encuentra la tarjeta gráfica (actualizar el controlador, elegir otra compilación o el procesador); falta memoria (reducir el contexto); en el puerto ya funciona un servidor con este modelo que no inició el programa (el programa lo usa, pero no puede cambiar sus parámetros).

### 12.4 Otro servidor o la nube

El modelo propio no es la única opción:

- **otro servidor local**: cualquiera que admita `/v1/embeddings` en formato OpenAI (por ejemplo, un `llama-server` propio con otro modelo). En los ajustes, la dirección (`embeddings.base_url`) y el nombre del modelo (`embeddings.model`); la clave solo hace falta si el servidor se inició con clave;
- **embeddings en la nube**: `embeddings.mode: cloud`, la dirección y el modelo del proveedor, la clave en el archivo `embeddings_api_key.txt` junto al programa, y el precio `price_input` ($ por 1 millón de tokens) para calcular los costes y el presupuesto (sección 14).

"Comprobar conexión" («Проверить связь») envía al modelo un texto corto e informa de si se ha recibido un vector. Al cambiar de modelo, los vectores se recalculan solos (sección 12.2).

## 13. Modelos de lenguaje y perfiles

El programa no está atado a un modelo ni a un proveedor. Sirve cualquier servicio con una API en formato OpenAI (`/chat/completions`), en la nube o un servidor propio en este ordenador, y sin API existe el modo manual a través de un chat web. Los prompts son los mismos en todos los casos. El modelo de embeddings se elige aparte y no depende de esta elección (sección 12).

### 13.1 Modos

El modo principal es `llm.mode`:

| Modo | Dónde funciona el modelo | Qué importa |
| --- | --- | --- |
| `cloud`: "Modelo en la nube (API)" («Облачная модель (API)») | En el proveedor, con una clave | De pago, por tokens (sección 14); ventana grande; los textos de las notas van al servidor del proveedor |
| `local`: "Modelo local (en este ordenador)" («Локальная модель (на этом компьютере)») | Un servidor propio de llama.cpp u otro compatible con OpenAI, en este ordenador o en la red doméstica | Gratis, los datos no salen a ningún sitio; suele ser más débil que uno en la nube y con una ventana menor |
| `webchat`: "A mano a través del chat web" («Вручную через веб-чат») | En el chat web de cualquier modelo; el usuario lleva las peticiones y las respuestas | Sin API ni claves; lento y manual (sección 13.5) |

No se impone ninguna opción. Un modelo en la nube es un compromiso consciente: los pensamientos personales en bruto van a un servidor ajeno, pero la calidad es mayor y la ventana, más grande. Allí el límite es el dinero, no el tamaño de la ventana, por eso los prompts no se recortan para ahorrar (sección 9.1). Un modelo local es la opción más privada, a costa de la calidad y de la configuración.

**El servidor propio del modelo de lenguaje** lo inicia el usuario (a diferencia del servidor de embeddings, sección 12.3), por ejemplo: `llama-server -m modelo.gguf -c 16384 --port 8080`, y escribe en el perfil local la dirección `http://127.0.0.1:8080/v1`. Para las direcciones de este ordenador y de la red doméstica (`localhost`, `127.*`, `10.*`, `192.168.*`, `172.16–31.*`, `*.local`) la clave no es obligatoria: solo hace falta si el servidor se inició con clave.

### 13.2 Perfiles

Los ajustes del modelo se guardan en **perfiles** (`llm.profiles`). Puede haber tantos perfiles como se quiera: dos modelos del mismo proveedor, uno en la nube y uno propio, uno potente y uno rápido. Funciona el perfil elegido para el modo: `cloud_profile` en el modo en la nube, `local_profile` en el local.

| Campo | En el plugin | Significado |
| --- | --- | --- |
| `id` | — | Código corto del perfil (`p1`, `p2`…), al que hacen referencia los ajustes |
| `name` | "Nombre del perfil" («Имя профиля») | Cómo se llama el perfil en las listas, en "Costes" y en el registro |
| `kind` | — | `cloud` o `local` |
| `base_url` | "Dirección de la API" / "Dirección del servidor" («Адрес API» / «Адрес сервера») | Dirección en formato OpenAI |
| `model` | "Modelo" («Модель») | Nombre del modelo exactamente como lo escribe el proveedor; para llama.cpp, cualquiera |
| `api_key_file` | "Clave de API" / "Clave" («Ключ API» / «Ключ») | Archivo con la clave junto al programa (ver más abajo) |
| `temperature` | "Temperatura" («Температура») | 0–2, por defecto 0,2: más baja, respuestas más estables |
| `max_input_chars` | "Límite de la petición, caracteres" («Предел запроса, знаков») | Si el material es más largo, se divide en partes (sección 13.4). Por defecto, 300 000 (≈ 100 000 tokens) en uno en la nube y 40 000 en uno local; para un servidor propio, unos 3 caracteres por token de la ventana |
| `max_tokens` | "Límite de longitud de la respuesta (tokens)" («Предел длины ответа (токенов)») | Vacío: como lo tenga el proveedor |
| `timeout_sec` | "Espera de respuesta, segundos" («Ожидание ответа, секунд») | 600 en uno en la nube, 1800 en uno local |
| `json_mode` | "Modo JSON" («Режим JSON») | Activarlo si el servidor admite `response_format: json_object`: menos errores de formato |
| `extra` | "Parámetros especiales de la petición" («Особые параметры запроса») | Se añaden a la petición tal cual, por ejemplo `{"thinking": {"type": "disabled"}}` |
| `prices` | precios, $ por 1 millón de tokens | Solo en la nube: entrada, entrada desde caché, salida (sección 14.2) |
| `budget_month` | "Límite mensual del perfil, $" («Лимит профиля в месяц, $») | Solo en la nube: un límite propio por encima del presupuesto general (sección 14.3) |

**Las claves** no se guardan en la bóveda ni en `settings.yaml`, sino en archivos aparte junto al programa: `api_key.txt` para el primer perfil y `api_key_<id>.txt` para los nuevos. Así la clave no entra en la sincronización ni en las copias de seguridad de las notas, y cada perfil tiene su propio archivo: la clave de un proveedor nunca se envía a la dirección de otro. En el plugin, la clave se introduce en un campo que no la muestra entera, y el programa la guarda en el archivo. Una copia de un perfil usa por defecto el mismo archivo; el botón "Clave aparte" («Отдельный ключ») le crea uno propio.

En el plugin (Ajustes → Segundo Cerebro → Modelos; en la interfaz: Второй мозг → Модели): "Modo" («Режим»), los perfiles principales en la nube y local, "Perfil que editar" («Профиль для правки») con los campos del perfil elegido, los botones "＋ En la nube" («＋ Облачный»), "＋ Local" («＋ Локальный»), "Copia" («Копия») y la eliminación del perfil.

### 13.3 Modelos para pasos concretos

A cada paso (prompt) se le puede asignar su propio perfil o el chat web: `llm.roles`, en el plugin "Modelos para pasos concretos" («Модели для отдельных шагов»). Por ejemplo, "Síntesis" al modelo más potente, la frecuente "Clasificación" a uno rápido o al propio en llama.cpp, y "Preguntas" al chat web:

```yaml
llm:
  roles: {"Синтез": "p2", "Классификация": "p3", "Вопросы": "webchat"}
```

Las claves son los nombres rusos de los prompts, como en la carpeta `prompts/` («Синтез», Síntesis; «Классификация», Clasificación; «Вопросы», Preguntas).

"Como el principal" («Как основная»; sin línea en `roles`): el paso funciona con el perfil del modo principal. En el modo de chat web, los perfiles solo hacen falta si a pasos concretos se les han asignado modelos propios. Los costes se registran a nombre del perfil que realmente respondió (sección 14).

### 13.4 Llamada al modelo

**Preparación.** El programa sustituye las variables en el prompt (sección 9.1) y, si la petición del paso supera el límite, divide el material en partes. Se dividen tres pasos con material largo: "Estructura", los archivos de la carga por partes, y cada parte precisa el borrador; "Clasificación", los párrafos de un archivo largo por ventanas; "Análisis del pool", los aspectos del pool por partes. El límite es el del perfil que responde al paso (o el del chat web, `llm.webchat.max_input_chars`); al material le corresponde el límite menos una reserva para la tarea y las listas (unos 40–60 mil caracteres; para límites pequeños, la mitad). "Valor" valora los elementos en porciones de no más de `limits.max_items_per_value_call` (400).

**Antes de la llamada**, el programa comprueba el presupuesto (para un perfil en la nube, sección 14.3) y la marca "Detener"; mientras el modelo piensa, el plugin muestra «Ждём ответа модели: <время> · <шаг> · <профиль>» ("Esperando la respuesta del modelo: <tiempo> · <paso> · <perfil>").

**Comprobación de la respuesta.** Cada respuesta se analiza y se comprueba (sección 9.1). Si algo no está bien, el programa continúa el mismo diálogo: envía al modelo su respuesta y una lista de observaciones y le pide que mande la respuesta corregida completa. Hay `llm.max_format_retries` (2) intentos de este tipo, es decir, tres respuestas en total; después el programa se detiene y enumera los errores.

**Corte por longitud.** Si una respuesta se cortó por el límite de longitud (`finish_reason: length`), se pide al modelo que la envíe de nuevo, más corta. Para "Síntesis" esto no tiene sentido (un documento no se puede escribir más corto por encargo), así que el programa se detiene enseguida y aconseja aumentar el "Límite de longitud de la respuesta" («Предел длины ответа») del perfil o dejarlo vacío.

**Errores de conexión y del servidor** (sección 11.3): ante 429, 5xx, una conexión cortada o una respuesta que no está en JSON, reintentos con pausas de 5, 20, 60 y 120 segundos; si el servidor propio no responde en absoluto, el programa no espera mucho y sugiere comprobar si está en marcha y si la dirección es correcta. Una clave incorrecta (401, 403) supone una detención con la indicación de qué perfil corregir. El desbordamiento de la ventana del modelo supone una detención con un consejo: para los pasos que se pueden dividir, reducir el "Límite de la petición" («Предел запроса»); para los demás, asignar el paso a un perfil con una ventana mayor; a un servidor propio de llama.cpp se le puede dar una ventana mayor con la opción `-c`.

**Contabilidad.** Cada llamada se anota en el registro de llamadas: paso, perfil, modelo, tokens, tiempo y coste (sección 14.1). Si el proveedor no ha informado de los tokens, se estiman por el número de caracteres; en llama.cpp, los tokens y la caché se toman de su informe de tiempos. El campo `reasoning` de la respuesta va al registro de razonamientos (sección 15.2), y el nombre del modelo, al registro de reflexión (sección 15.3).

**Comprobación de conexión** ("Comprobar conexión", «Проверить связь»; el comando `check`): comprueba la bóveda, los prompts y el historial de versiones, envía a cada modelo en uso una petición corta con respuesta en JSON y al modelo de embeddings un texto corto, e informa de quién responde y en cuántos segundos.

### 13.5 Modo manual a través de un chat web

Para quien no tiene API: el programa prepara las peticiones como archivos, y el usuario las lleva al chat web de cualquier modelo. Los prompts son los mismos que para la API.

1. En cada llamada, el programa deja en la carpeta `_веб-чат/` (chat web) dos archivos: `001 <шаг> — запрос.md` (petición) y uno vacío, `001 <шаг> — ответ.md` (respuesta), y se detiene. El panel muestra "Esperando respuesta del chat web" («Ждёт ответа из веб-чата») con los botones "Abrir la petición" («Открыть запрос») y "Abrir el archivo de respuesta" («Открыть файл ответа»).
2. El usuario copia en el chat web todo lo que hay debajo de la línea «скопировать всё ниже» ("copiar todo lo de abajo"), pega la respuesta completa del modelo en el archivo de respuesta y lo guarda.
3. "Continuar" («Продолжить»; o "Continuar (Fase 1)"): el programa comprueba la respuesta igual que una respuesta por API. Si todo es correcto, la pareja de archivos pasa a `_веб-чат/готово/` (hecho) y el trabajo sigue hasta la siguiente petición. Si no, en la parte superior del archivo de petición aparece un aviso con la lista de observaciones: se pueden enviar al modelo y sustituir la respuesta por la corregida.

Las peticiones se numeran por orden; las respuestas ya recibidas se recuerdan (`.system/webchat.json`), así que repetir un paso tras una detención no crea una petición nueva. Detenerse mientras se espera una respuesta no hace perder nada: el trabajo continúa desde el mismo punto (sección 11.3). En este modo no se muestran el tiempo ni lo "restante": todo depende de cuándo se pegue la respuesta. Los embeddings también se calculan como de costumbre en este modo (sección 12).

## 14. Costes, presupuesto y estimación de la ejecución

El límite de un modelo en la nube es el dinero, no el tamaño de la ventana (sección 9.1). Por eso el programa lleva la cuenta de cada llamada, mantiene un presupuesto mensual y, antes de una ejecución grande, estima cuánto costará.

### 14.1 Registro de llamadas

`.system/usage.jsonl`: una línea por cada llamada al modelo de lenguaje y al modelo de embeddings (un lote de textos es una llamada):

| Campo | Qué |
| --- | --- |
| `ts`, `run`, `cmd` | Hora, ejecución y comando (`run`, `synth`, `revalidate`…) |
| `kind` | `llm` o `emb` |
| `prompt` | El paso: el nombre del prompt; en los embeddings, «Эмбеддинги» (Embeddings); en la comprobación de conexión, «Проверка связи» (Comprobación de conexión) |
| `profile`, `profile_name` | El perfil: `id` y nombre en el momento de la llamada |
| `ptype` | Tipo: `cloud`, `local`, `webchat` o `fake` (el modelo de prueba) |
| `model` | Modelo |
| `in`, `out`, `cached` | Tokens de entrada, de salida y, de los de entrada, cuántos vinieron de la caché del proveedor |
| `est` | Los tokens se estimaron por el número de caracteres: el proveedor no informó de ellos |
| `sec` | Cuánto tardó la respuesta |
| `cost` | Coste en dólares según los precios en el momento de la llamada |

El programa toma los tokens de la respuesta del proveedor; en llama.cpp, de su informe de tiempos. Si el proveedor no informó de nada, los tokens se estiman como el número de caracteres dividido entre 3.

### 14.2 Coste

El dinero solo se cuenta en los modelos en la nube. Los precios están en el perfil (`prices`, $ por 1 millón de tokens); en los embeddings en la nube, en `embeddings.price_input`:

coste = (entrada − entrada desde caché) × precio de entrada + entrada desde caché × precio de caché + salida × precio de salida

Si no hay precio de caché, la entrada desde caché cuenta como entrada normal. Los precios están en `settings.yaml`, no en una base aparte: se ven y se pueden corregir en un solo sitio, en el perfil (Ajustes → Segundo Cerebro → Modelos) o directamente en la pestaña "Costes" («Расходы») del panel.

El coste se fija junto con la llamada: cambiar los precios no reescribe el pasado. El recálculo es explícito: después de guardar precios nuevos, el panel pregunta "¿Recalcular las llamadas anteriores?" («Пересчитать прошлые обращения?»); el comando es `usage --reprice <id del perfil | emb | all>`. El registro anterior al recálculo se guarda al lado como `.bak`. Las llamadas en la nube que no tenían precio al registrarse se estiman en los resúmenes con los precios actuales; si tampoco ahora hay precios, van en una línea aparte, «без стоимости» ("sin coste"), y se marcan con un asterisco.

Los modelos locales son gratuitos: para ellos se muestran los tokens y el tiempo de trabajo. Para el chat web, el número de intercambios. El modelo de prueba cuenta como el perfil al que está asociado; esto hace falta para las pruebas.

### 14.3 Presupuesto

- `budget.monthly_usd`: para todos los modelos en la nube juntos, por mes natural; vacío, sin presupuesto;
- `budget_month` del perfil: el límite propio de ese perfil;
- `budget.warn_pct` (80): a partir de qué porcentaje avisar.

Antes de cada llamada de pago, el programa comprueba cuánto se ha gastado en el mes (el registro más la ejecución actual). A partir de `warn_pct`, un aviso por ejecución: en la salida, en el panel y como notificación. Al 100 %, la pregunta "Presupuesto agotado" («Бюджет исчерпан»): "Continuar hasta el final de esta ejecución" («Продолжить до конца этого запуска») o "Parar" («Остановить»). Si no se puede preguntar (una ejecución sin el plugin y sin consola), el programa se detiene. La detención por presupuesto lo guarda todo igual que "Detener" (sección 11.3); se puede continuar aumentando el presupuesto o volviendo a ejecutar y eligiendo "Continuar".

El presupuesto se fija en los ajustes (pestaña "Costes") o directamente en la pestaña "Costes" del panel, donde también está la barra «потрачено из бюджета» ("gastado del presupuesto").

### 14.4 Estimación de la ejecución

Antes de la primera llamada al modelo, el programa estima lo que viene:

- **Fase 1**: qué pasos se llamarán y cuántas veces, según los archivos de `_staging` (con los diarios divididos por fechas) y la cola de archivos aceptados, las partes de los archivos largos y el número esperado de entradas y contenedores;
- **Fase 2**: la síntesis a partir de la base de síntesis y los documentos anteriores del contenedor, más la comparación de versiones;
- **revalidación**: una clasificación por entrada.

Las medias por llamada (tokens y tiempo) se toman del registro para el mismo paso y perfil si tiene al menos tres llamadas; si no, la longitud del prompt más el material y unos valores iniciales por paso. El dinero, según los precios de los perfiles que responden a los pasos. La estimación es aproximada (±50 %): cuántas entradas habrá tras el reparto no se sabe de antemano.

Antes de la Fase 1 y la Fase 2, el programa muestra la estimación y pregunta "¿Iniciar?" («Запустить?») si la ejecución es grande, es decir, supera cualquiera de los umbrales: `estimate.calls` (30 llamadas), `estimate.usd` (0,5 $) o `estimate.minutes` (10 minutos). La revalidación pregunta siempre (sección 10.1). `estimate.enabled: false` desactiva la pregunta, y la opción `--yes` la omite una vez. Si no se puede preguntar, la Fase 1 y la Fase 2 se inician sin pregunta, mientras que la revalidación exige `--yes`. La estimación también se puede obtener por separado: `estimate run | synth <contenedor> | revalidate [contenedor]`.

### 14.5 Resumen

La pestaña "Costes" del panel (y el comando `usage` en la consola):

- totales de hoy, de este mes, del mes pasado y de todo el tiempo: dinero, llamadas, tokens de entrada (y cuántos desde caché) y de salida, tiempo de trabajo de los modelos;
- el presupuesto del mes: cuánto se ha gastado y una barra hasta el límite;
- **modelos**: una ficha por perfil con el modelo, en qué pasos trabaja, el gasto del periodo y el límite del perfil; en los perfiles en la nube, campos de precios con un botón "Guardar" («Сохранить»). Aquí también está el modelo de embeddings, así como los perfiles eliminados y los modelos de embeddings anteriores, si hubo llamadas a ellos;
- **por pasos**: llamadas, tokens y coste de cada prompt;
- **por días**: barras de los últimos 31 días (el coste o, sin dinero, el número de llamadas);
- **últimas ejecuciones**: qué se ejecutó y cuánto costó.

Durante una ejecución, en la parte superior del panel se ve cuántos tokens y cuánto dinero ha gastado ya esa ejecución (sección 18.2).

## 15. Registros

Tres registros con tareas distintas: el registro de cambios cuenta qué ha pasado; el registro de razonamientos, por qué el modelo decidió así; el registro de reflexión, hasta qué punto sus suposiciones coinciden con las decisiones del usuario. Los registros para personas están en la carpeta `_логи/` (registros) de la bóveda, y los legibles por máquina, en `.system/`. Se pueden abrir desde la pestaña "Registro" («Журнал») del panel.

| Archivo | Para quién | Qué |
| --- | --- | --- |
| `_логи/изменения AAAA-MM.md` (cambios) | persona | Qué se cambió, cuándo y quién (sección 15.1) |
| `_логи/рассуждения AAAA-MM.md` (razonamientos) | persona | Por qué el modelo tomó sus decisiones (sección 15.2) |
| `_логи/архив вопросов.md` (histórico de preguntas) | persona | Preguntas respondidas, con sus respuestas (sección 7.4) |
| `_логи/структура утверждена AAAA-MM-DD.md` (estructura aprobada) | persona | El borrador de estructura aprobado (sección 6.3) |
| `_логи/ошибки.log`, `_логи/плагин.log` (errores, plugin) | desarrollador | Errores inesperados del programa y del plugin (sección 15.4) |
| `.system/reflection.jsonl` | programa | El registro de reflexión (sección 15.3) |
| `.system/usage.jsonl` | programa | El registro de llamadas y costes (sección 14.1) |

### 15.1 Registro de cambios

Un registro común y legible por personas de todo el sistema, no solo de la Fase 1: qué cambió, cuándo y quién lo hizo: el **usuario**, el **modelo** o el **programa**. Completa el diff técnico de git (sección 11.2) con una explicación del sentido. Cada mes empieza un archivo nuevo. Ejemplo de líneas:

```
- 12.03.2026 14:05 · модель · [[2026-03-12 Pulso con el flash]] → [[Pulsómetro]] (уверенность 84)
- 12.03.2026 14:06 · модель · [[2026-03-12 Pulso con el flash]]: извлечено аспектов — 4
- 13.03.2026 09:30 · пользователь · [[Club de lectura]]: classification: общий → 80
- 13.03.2026 09:31 · программа · Фаза 1: готово — 12 обращений, 41 тыс. токенов, $0,03
```

El programa escribe estas líneas en ruso: модель, modelo; пользователь, usuario; программа, programa; уверенность, confianza; извлечено аспектов, aspectos extraídos; общий, general; готово, hecho; обращений, llamadas; тыс. токенов, miles de tokens.

Aquí quedan el reparto y los traslados de entradas, la extracción de aspectos, la creación y reorganización de contenedores, las ediciones manuales (estados, vínculos, umbrales, estilo), las respuestas a preguntas, los documentos de la Fase 2, el recálculo de vectores y el resultado de cada ejecución.

### 15.2 Registro de razonamientos

Por qué se tomó una u otra decisión: qué generaba dudas, qué alternativas se consideraron. No se genera aparte: se rellena con el campo `reasoning` de las respuestas del modelo (sección 9.1), incluidos los anidados: cada segmento, duplicado o contradicción tiene su propia explicación. Cada registro es un encabezado con la hora, el paso, el objeto y el modelo, y debajo, las explicaciones punto por punto:

```
### 12.03.2026 14:05 · Классификация · файл «pulso.txt» · Z.ai
- **фрагмент 1 → «Pulsómetro»**: se trata de medir el pulso con la cámara del teléfono, el núcleo del subproyecto…
```

(Классификация, Clasificación; файл, archivo; фрагмент, fragmento.) Cada mes empieza un archivo nuevo.

### 15.3 Registro de reflexión

Una capa de servicio por encima del trabajo del sistema. Cada decisión que incluye una suposición del modelo se anota aparte del resultado; cuando aparece la decisión del usuario (una respuesta a una pregunta, un traslado manual, una edición de umbrales), se anota también al lado, y se obtiene una pareja "suposición — decisión". El objetivo son las estadísticas acumuladas para calibrar los umbrales: si el sistema se equivoca sistemáticamente en un mismo sentido con algún contenedor o fuente, se nota, y los umbrales se pueden corregir, por cuenta propia o con el consejo del modelo (sección 10.5).

El formato es JSON Lines, una línea por registro. Una suposición: `type: assumption`, `ref` (un número del tipo `r12`), `kind`, `subject` (de qué trata), `assumption`, `confidence`, `model` (el modelo que tomó la decisión, para que las estadísticas no se mezclen al cambiar de modelo) y campos adicionales según el tipo. Una decisión: `type: decision`, el mismo `ref`, `kind`, `decision` y `matched`, si coincidió con la suposición (`true`, `false` o `partial`).

| Tipo (`kind`) | Suposición | Decisión del usuario |
| --- | --- | --- |
| `classification` | Contenedor y confianza **sin tener en cuenta la pista**; al lado, la pista, la confianza de su opción, el umbral, qué se hizo (repartida, cuarentena) y quién (el modelo o la pista) | Respuesta a "Dónde clasificar la entrada" o un traslado manual (sección 10.2) |
| `mode_guess` | Modo del archivo y confianza | Respuesta a "Cómo procesar el archivo" |
| `compaction` | Si hace falta condensar, nivel de ruido, umbral y fuente | — (estadísticas del nivel de ruido) |
| `structure_draft` | Contenedores propuestos en el borrador | Cuántos se aprobaron, qué se eliminó, añadió o renombró |
| `outdated` | Un aspecto nuevo revisa uno antiguo | Respuesta a "¿El pensamiento nuevo revisa el antiguo?" |
| `conflict` | Una contradicción y la suposición: es correcto el primero, el segundo o es una bifurcación | Respuesta a la pregunta sobre la contradicción |
| `seed_to_project`, `subcontainer` | El brote se ha convertido en proyecto; hace falta un subcontenedor | Respuesta a la pregunta sobre la estructura |
| `base_loss`, `product_loss` | Si es significativa una pérdida detectada al comparar versiones | Respuesta a la pregunta sobre la pérdida |
| `composite_type` | Un nuevo tipo compuesto | Aceptado o rechazado |
| `revalidation_hint` | Una entrada parecida en otro contenedor y la similitud | Traslado o "todo correcto" |
| `deep_revalidation` | El contenedor en la nueva comprobación y la confianza | Respuesta a la pregunta de la nueva comprobación |
| `thresholds_advice` | Valores de umbrales propuestos y los actuales | Qué valores se aceptaron y cuáles no |

El registro solo crece por el final y no necesita versiones: es una capa de servicio acumulativa, no una entidad cuyo contenido cambie.

### 15.4 Errores e informe para el desarrollador

**Errores del programa.** Las situaciones previstas (no hay clave, el servidor no responde, el formato de los ajustes es incorrecto) el programa las explica con palabras sencillas e indica qué hacer. Un error inesperado se escribe en `_логи/ошибки.log` junto con el comando y la traza completa; el usuario ve un mensaje breve: todo lo procesado está guardado, y una nueva ejecución continuará desde el mismo punto.

**Los errores del plugin** se muestran en el mismo lugar, con un marco rojo "Error en el plugin…" («Ошибка в плагине…») y un botón "Copiar el informe" («Скопировать отчёт»), y se escriben en `_логи/плагин.log` (a partir de 512 KB, el registro anterior pasa a ser `плагин.log.old`).

**El informe para el desarrollador**: el botón "Generar el informe" («Собрать отчёт»; Ajustes → Segundo Cerebro → Avanzado, «Дополнительно») o el comando del plugin "Informe para el desarrollador" («Отчёт для разработчика»). El informe incluye las versiones del programa, del plugin, de Obsidian y del sistema, los últimos errores del plugin, el final de `ошибки.log` y la salida de las tres últimas ejecuciones. No contiene claves de API ni textos de notas. El informe se guarda en `_логи/отчёт для разработчика.md` (informe para el desarrollador), se abre y se copia al portapapeles: se puede pegar directamente en un mensaje.

## 16. Formatos de datos

Los datos del programa son archivos normales. En la bóveda son notas Markdown con un encabezado YAML: fichas de contenedores, entradas y documentos. En `.system/` hay archivos JSON: pools de aspectos, bases de síntesis, preguntas, estado, registros. A continuación, los campos de cada formato. Qué se puede editar a mano se indica en la sección 3.6; todo lo demás lo pone y lo cambia el programa.

Los enlaces a otras notas se escriben en YAML como `"[[Nombre]]"`. Junto a cada enlace se guarda el `id` del mismo objeto (`parent` y `parent_id`, `container` y `container_id`): por el `id` el programa reconoce el objeto aunque se haya renombrado, y por una discrepancia entre el enlace y el `id` detecta una edición manual. Los campos `type` y `container_status` también pueden escribirse en ruso: `проект`, `росток`, `вопрос` (proyecto, brote, pregunta); `активный`, `завершён`, `спит` (activo, terminado, dormido).

### 16.1 Ficha del contenedor

```yaml
type: project                  # project | seed | question (sección 3.3)
id: k004                       # lo pone el programa; nombre del contenedor = nombre del archivo de la ficha
color: "#7FB0F5"               # color (sección 3.7)
parent: "[[App para correr]]"  # padre principal; null — nivel superior
parent_id: k001
applies_to: ["[[Monitor de sueño]]"]  # dónde más se aplica (sección 3.2)
applies_to_ids: [k007]
container_status: active       # active | completed | dormant (sección 3.5)
description: "Medición del pulso con la cámara del móvil: el dedo sobre el objetivo, el flash como iluminación."
created: 2026-02-10
last_modified: 2026-03-12      # lo actualiza el programa cuando cambia el contenido del contenedor
needs_review: false
review_reason: null
thresholds:                    # umbrales propios (sección 10.5); sin el campo — los del padre o los generales
  classification: 75
style: "Más breve, en listas"  # estilo propio de los documentos (sección 8.3)
```

| Campo | Significado |
| --- | --- |
| `type` | Tipo de nodo: proyecto, brote o pregunta. |
| `id` | Número permanente del contenedor (`k` y tres cifras). No cambia al renombrarlo ni al moverlo. |
| `color` | Color del contenedor; sus entradas se resaltan con el mismo color. |
| `parent`, `parent_id` | Padre principal: de él depende en qué carpeta está el contenedor. |
| `applies_to`, `applies_to_ids` | Vínculos con contenedores de otras ramas donde se aplica este proyecto. No es anidamiento. |
| `container_status` | Estado: activo, terminado, dormido. |
| `description` | Descripción. El modelo se apoya en ella para decidir qué pertenece al contenedor. Si el usuario creó una ficha sin descripción, el programa toma el primer párrafo del texto. |
| `created`, `last_modified` | Fecha de creación y fecha del último cambio de contenido (pensamientos nuevos, traslado de entradas, respuestas que cambian el pool). Con `last_modified` se comprueban los brotes olvidados (sección 7.1). |
| `needs_review`, `review_reason` | Si hace falta que el usuario revise algo y por qué. |
| `thresholds` | Valores propios de los umbrales. Las claves son los nombres de los umbrales (sección 17) o sus nombres en ruso. Un valor incorrecto no rompe nada: el programa avisa y toma el heredado. |
| `style` | Estilo propio de los documentos. Lo heredan los contenedores anidados que no tienen estilo propio. |

### 16.2 Entrada

```yaml
type: entity
id: e00042                     # lo pone el programa
content_type: thought          # thought | diary | resource | question | ai_dialogue | product_edit | …
source: "заметка"              # fuente: la subcarpeta de _staging (sección 4.1)
container: "[[Pulsómetro]]"
container_id: k004
shared: false                  # true — la entrada está en _shared
also_in: ["[[Monitor de sueño]]"]  # otros contenedores de una entrada compartida
also_in_ids: [k007]
created: 2026-03-12            # fecha del pensamiento: del encabezado, de una fecha del diario o la del archivo
source_file: "_исходники/2026-03-12 pulso.txt"
segment: "3-7"                 # qué párrafos del original; null — el archivo entero
source_part: "2 из 5 · 12.03.2026"  # solo para un diario dividido por fechas (sección 4.2)
hint: "Pulsómetro"             # pista del encabezado del archivo (sección 4.4)
status: processed              # draft → processed; outdated — el pensamiento está obsoleto
conflicts_with: []             # marca manual de disputa con otra entrada: ["[[nombre de la entrada]]"]
needs_review: false
review_reason: null            # low_confidence | new_container | user_hint_mismatch | incomplete
quarantine: false              # true — la entrada está en _на_проверку y espera respuesta
incomplete: false              # el modelo consideró incompleto el pensamiento (sección 6.6)
compacted: false               # si ha pasado por la condensación (sección 6.7)
aspect_ids: [a118, a119]       # enlaces a los aspectos del pool del contenedor
```

El programa escribe estos valores en ruso: `заметка` (nota) es el nombre de la subcarpeta de la fuente; `2 из 5` significa "2 de 5".

Debajo del encabezado va el texto de la entrada, sin cambios. Si la entrada se ha condensado, debajo del texto se añade una sección `## Уплотнённая версия (создана программой)` ("Versión condensada (creada por el programa)") con el texto comprimido: a partir de entonces se trabaja con él, y el original se queda en su sitio (sección 6.7).

La entrada no contiene los aspectos en sí, solo sus números. Los aspectos de una entrada compartida están en los pools de todos sus contenedores. Estado `draft`: la entrada aún está en proceso; `processed`: ha pasado por la Fase 1 y es inmutable (sección 4.3); `outdated`: está obsoleta y sus aspectos no van a las bases de síntesis.

### 16.3 Pool de aspectos

Archivo `.system/data/pools/<id del contenedor>.json`. Para leerlo una persona, está la vista `_аспекты.md` (aspectos) en la carpeta del contenedor.

```json
{
  "container_id": "k004",
  "aspects": {
    "a118": {"id": "a118", "type": "fact", "text": "La luz del flash atraviesa el dedo y produce una pulsación visible.",
             "source_entity": "e00042", "date": "2026-03-12", "status": "active", "value": 74, "duplicate_of": null},
    "a131": {"id": "a131", "type": "fact", "text": "Con el flash, la pulsación a través del dedo se ve bien.",
             "source_entity": "e00057", "date": "2026-03-20", "status": "active", "value": 70, "duplicate_of": "a118"}
  },
  "composites": {
    "c3": {"id": "c3", "composite_type": "experience", "from": ["a101", "a118", "a120"],
           "text": "Probé a medir el pulso sin flash: ruido; con flash, la señal es limpia.",
           "status": "active", "value": 82, "created": "2026-03-12"}
  },
  "conflicts": [
    {"key": "a140|a152", "a": "a140", "b": "a152", "type": "plan", "assumed": "b",
     "assumption": "más reciente y más detallado", "reasoning": "…", "status": "asked", "decision": null,
     "ref": "r305", "created": "2026-03-21T10:02:11"}
  ],
  "rejected": [{"kind": "duplicate", "a": "a160", "b": "a118"}],
  "accepted_losses": []
}
```

**Aspecto simple** (`aspects`):

| Campo | Significado |
| --- | --- |
| `id`, `type`, `text` | Número (`a…`), tipo simple (sección 5.1) y formulación. |
| `source_entity`, `date` | La entrada de origen y su fecha. |
| `status` | `active`, `in_composite` (ha entrado en un compuesto y no va a la base por separado), `outdated` (sección 5.5). |
| `value` | Valor de contenido 0–100; se recalcula en cada armado de la base. |
| `duplicate_of` | Si el aspecto es un duplicado de otro: el número del original. |
| `replaced_by`, `outdated_by`, `status_before` | Si el aspecto está obsoleto: qué aspecto lo sustituyó, de dónde viene la marca (`user`: respuesta a una pregunta; `entity`: la entrada está marcada `status: outdated`) y qué estado tenía antes, para poder recuperarlo. |
| `pinned` | El usuario recuperó el aspecto tras una pérdida: cuenta como principal en cualquier valoración. |

**Aspecto compuesto** (`composites`): número (`c…`), `composite_type` (sección 5.2), `from` (de qué aspectos simples está formado), `text`, `status` (`active`; `needs_review`: uno de sus componentes está obsoleto y el análisis del pool revisará el compuesto; `outdated`: el compuesto se ha disuelto y sus componentes vuelven a estar `active`), `value`, `created`, `note` (por qué se disolvió el compuesto).

**Contradicciones** (`conflicts`): un par de aspectos `a` y `b` del mismo tipo; `assumed`, lo que el programa considera correcto hasta la respuesta (`a`, `b` o `both`, una bifurcación); `assumption` y `reasoning`, por qué; `status` (`open` → `asked` → `resolved`; `rejected`: el usuario dijo que no hay contradicción); `decision`, la respuesta del usuario; `ref`, el número de la suposición en el registro de reflexión (sección 15.3).

**Propuestas rechazadas** (`rejected`): pares a los que el usuario ya dijo "no", para no volver a proponerlos. Tipos: `duplicate`, `outdated`, `conflict`, `seed_to_project`, `subcontainer`.

**Pérdidas aceptadas** (`accepted_losses`): aspectos cuya salida de la base el usuario consideró intencionada (sección 6.13).

### 16.4 Base de síntesis

Archivo `.system/data/bases/<id del contenedor>.json`; junto a él, la versión anterior `<id>.prev.json` para comparar. Para leerla una persona, está la vista `_база синтеза.md` (base de síntesis).

```json
{
  "type": "synthesis_base",
  "container_id": "k004",
  "container": "Pulsómetro",
  "built": "2026-03-21T10:05:40",
  "groups": [
    {"type": "experience", "items": [
      {"id": "c3", "type": "experience", "text": "…", "rank": "primary", "value": 82, "date": "2026-03-12",
       "sources": ["e00031", "e00042"], "dups": [],
       "parts": [{"id": "a101", "type": "action", "text": "…"}, {"id": "a118", "type": "fact", "text": "…"}]}
    ]},
    {"type": "fact", "items": [
      {"id": "a118", "type": "fact", "text": "…", "rank": "primary", "value": 74, "date": "2026-03-12",
       "sources": ["e00042", "e00057"], "dups": ["a131"]}
    ]}
  ],
  "excluded": ["a95"],
  "manual_conflicts": [],
  "needs_review": false,
  "review_reason": null,
  "thresholds": {"value_min": 30, "value_primary": 70}
}
```

| Campo | Significado |
| --- | --- |
| `built` | Cuándo se armó. Los documentos de la Fase 2 guardan esta hora en `based_on_synthesis`. |
| `groups` | Grupos por tipo, en el orden de la tabla de prioridad (sección 5.4). |
| `items` | Los puntos del grupo: primero los principales y, dentro de ellos, por valor. |
| `rank` | `primary` (valor no inferior a `value_primary` o aspecto recuperado por el usuario) o `secondary`. |
| `sources`, `dups` | Todas las entradas de origen, incluidas las de los duplicados, y los números de los duplicados fusionados. |
| `parts` | En un compuesto, sus componentes. |
| `conflict` | Números de los aspectos con los que este punto está en disputa. |
| `assumed_loser` | Según la suposición del programa, el punto pierde la disputa (aún no hay respuesta). |
| `fork` | Bifurcación: ambas variantes son ciertas en condiciones distintas (sección 10.3). |
| `rejected_alt` | El usuario eligió la otra variante; el punto se queda como alternativa rechazada y siempre es secundario. |
| `review` | El compuesto espera revisión: uno de sus componentes está obsoleto. |
| `pinned` | Punto recuperado por el usuario tras una pérdida. |
| `excluded` | Aspectos por debajo del umbral de valor: no entraron en la base, pero siguen en el pool. |
| `manual_conflicts` | Pares de entradas marcados por el usuario en `conflicts_with`. |
| `thresholds` | Con qué umbrales de valor se armó la base. |

Los aspectos obsoletos, los duplicados y los componentes de los compuestos no entran en la base como puntos aparte: un duplicado añade una fuente al punto original, y un componente se ve dentro de su compuesto.

### 16.5 Documento

```yaml
type: product
product_kind: summary          # summary — el "Archivo resumen"; supplementary — un documento adicional
title: "Сводный файл"
container: "[[Pulsómetro]]"
container_id: k004
last_generated: 2026-03-21
style_override: null           # estilo de este documento en concreto (sección 8.3)
based_on_synthesis: "2026-03-21T10:05:40"  # de qué armado de la base se escribió
accepted_losses: []            # pérdidas que el usuario consideró intencionadas
needs_review: false
review_reason: null            # «значимая потеря по сравнению с предыдущей версией»
```

`Сводный файл` es el nombre fijo del "Archivo resumen". El programa escribe el motivo en ruso; el del ejemplo significa "pérdida significativa respecto a la versión anterior".

Debajo del encabezado va el texto del documento. Se puede editar a mano: el programa detectará la edición y creará con ella una entrada (sección 8.5). `style_override` y `accepted_losses` se conservan cada vez que se reescribe el documento.

### 16.6 Preguntas

Archivo `.system/questions.json`: el contador de números `next` y las preguntas abiertas `open`. Una pregunta respondida se quita de `open` y se añade al final de `_логи/архив вопросов.md` (histórico de preguntas). Para las personas, las preguntas están en `open-questions.md` y en la pestaña "Preguntas" («Вопросы») del panel (sección 7.2).

```json
{
  "next": 13,
  "open": {
    "Q12": {"id": "Q12", "kind": "classify", "title": "Куда отнести запись",
            "text": "Запись: [[Medición del pulso después de correr]] (22.03.2026). …",
            "options": [{"label": "«Pulsómetro» — вариант модели (уверенность 64)", "value": {"to": "k004"}},
                        {"label": "Без контейнера (unsorted)", "value": {"unsorted": true}}],
            "free_text": true, "free_hint": "Или напишите название контейнера. …",
            "data": {"entity": "e00063"}, "dedup": "classify:e00063", "ref": "r311",
            "created": "2026-03-22T09:15:02", "note": null}
  }
}
```

El programa escribe los textos de las preguntas en ruso: «Куда отнести запись» — "Dónde clasificar la entrada", «Запись:» — "Entrada:", «вариант модели (уверенность 64)» — "opción del modelo (confianza 64)", «Без контейнера» — "Sin contenedor", «Или напишите название контейнера» — "O escriba el nombre de un contenedor".

`kind` es el tipo de pregunta; cada tipo tiene su propio manejador de respuestas: `classify` (dónde clasificar), `mode` (carga masiva o una sola entrada), `also_in` (entrada compartida), `clarify` (aclarar un pensamiento incompleto), `outdated` (si algo está obsoleto), `conflict` (contradicción), `structure_seed` y `structure_sub` (de brote a proyecto, subcontenedor), `base_loss` y `product_loss` (pérdida en la base y en un documento), `composite_type` (nuevo tipo compuesto), `dormant` (si el brote sigue vivo), `revalidate` (resultado de la revalidación), `text_changed` (ha cambiado el texto de una entrada procesada), `dup_fix` (corregir una fusión errónea). `options` son las opciones de respuesta; `free_text`, si se puede responder con palabras propias; `data`, a qué se refiere la pregunta; `dedup`, la clave con la que el programa evita hacer dos veces la misma pregunta; `ref`, el número de la suposición en el registro de reflexión al que irá la respuesta; `note`, por qué no se pudo aplicar la respuesta (se muestra bajo la pregunta, y la pregunta sigue abierta).

### 16.7 Estado

El archivo `.system/state.json` es el punto de control de la cadena de procesamiento. El programa lo escribe después de cada paso, así que una ejecución interrumpida continúa desde el mismo lugar (sección 11.3).

| Clave | Qué guarda |
| --- | --- |
| `counters` | Contadores de números: contenedores `k`, entradas `e`, aspectos `a`, compuestos `c`, archivos recibidos `i`, suposiciones del registro de reflexión `r`. |
| `items` | Archivos recibidos aceptados: ruta en `_исходники`, nombre y ruta en `_staging`, suma de control, codificación, fuente, fecha, pista, modo, etapa (`new` → `await_structure` → `ready` → `done`; `await_mode`: espera la respuesta sobre el modo), parte del diario, entradas creadas, avance de la clasificación por partes de un archivo grande. |
| `entity_stage` | Etapa de cada entrada: `classified` → `asked` → `compacted` → `embedded` → `done`; cuarentena: `quarantine` → `quarantine_wait`. |
| `cls` | Resultado de la clasificación de cada entrada: contenedor elegido, confianza, alternativas, razonamiento, modo, archivo de origen. |
| `dirty` | Contenedores cuya base hay que volver a armar, con los motivos y la etapa del armado: `analysis` → `value` → `assemble` → `compare`. |
| `new_aspects` | Aspectos llegados desde el último armado, por contenedor. |
| `text_hash` | Sumas de control de los textos de las entradas procesadas (sección 4.3). |
| `structure` | Borrador de la estructura: si espera aprobación y si se ha aprobado alguna vez. |
| `revalidation` | Cola de una revalidación sin terminar. |
| `restore_requests` | Lo que el usuario pidió recuperar en los documentos (respuesta a una pregunta sobre una pérdida, sección 8.4); se tiene en cuenta en la siguiente Fase 2. |
| `synth_sig` | Huella de los datos de la última Fase 2, por contenedor: si coincide, los documentos están al día y no se llama al modelo (sección 8.1). |
| `advice`, `thr_seen` | El último consejo sobre umbrales y los últimos umbrales y estilos de contenedores vistos, para el registro de reflexión (sección 10.5). |
| `rejected_types` | Nuevos tipos compuestos que el usuario rechazó. |
| `user_outdated`, `auto_outdated`, `auto_cw`, `cw_seen` | Quién puso las marcas "obsoleto" y "contradice a", el usuario o el programa: para distinguir una edición manual de una propia. |
| `css_enabled_once` | El fragmento CSS de colores ya se activó una vez (sección 3.7). |

### 16.8 Registros JSONL

Los registros legibles por máquina tienen una línea JSON por evento; al archivo solo se le añaden líneas:

- `.system/reflection.jsonl`: el registro de reflexión, parejas "suposición del programa — decisión del usuario" (campos: sección 15.3);
- `.system/usage.jsonl`: cada llamada al modelo y a los embeddings: hora, ejecución, paso, perfil, modelo, tokens, tiempo de respuesta, coste (campos: sección 14.1).

Los registros para personas son archivos Markdown en `_логи/` (sección 15).

## 17. Ajustes

Todos los ajustes del programa están en un solo archivo, `settings.yaml`, en la carpeta del programa (no en la bóveda). La lista completa de campos, con sus valores por defecto y una explicación en cada línea, está en la plantilla [`settings.template.yaml`](settings.template.yaml); aquí se explica cómo está organizado el archivo y qué hay en cada grupo.

### 17.1 El archivo

- El paquete del programa no trae el propio `settings.yaml`, sino la plantilla `settings.template.yaml`. El instalador `Установка.bat` (o el propio programa al ejecutar por primera vez cualquier comando) copia la plantilla en `settings.yaml`. Por eso una versión nueva descomprimida encima de la antigua no sobrescribe los ajustes (sección 19.3).
- Las claves de API no están en los ajustes, sino en archivos aparte junto al programa: `api_key.txt`, `api_key_<id>.txt` para los demás perfiles y `embeddings_api_key.txt` para los embeddings en la nube (sección 13.2).
- Los campos que faltan toman su valor por defecto; los ajustes de versiones anteriores se convierten al formato actual al leerlos.
- El archivo puede guardarse en UTF-8 o en "ANSI" (cp1251): el programa entiende ambos. Una ruta de Windows con barras invertidas entre comillas (`"D:\Notas"`) la corrige él mismo a barras normales.
- Un error en el YAML no provoca un fallo incomprensible: el programa indica el número de línea y las causas frecuentes: una sangría hecha con la tecla Tab, una comilla perdida, dos puntos dentro de un texto sin comillas.

### 17.2 Cómo se editan

Lo más cómodo es hacerlo en Obsidian: **Ajustes → Segundo Cerebro** (en la interfaz: «Второй мозг»; sección 18.3). La ventana se construye según el esquema que entrega el programa: cada campo tiene nombre, explicación, límites y valor por defecto. Los cambios se guardan solos, un segundo después de editar. El programa comprueba todos los valores a la vez y, si todo es correcto, reescribe `settings.yaml` entero, con las mismas explicaciones que la plantilla; el archivo anterior queda como `settings.yaml.bak`. Un valor incorrecto no se guarda: en la parte superior de la pestaña aparece "No guardado: …" («Не сохранено: …») con el motivo. El botón ↺ junto a un campo restablece el valor por defecto. El buscador de la parte superior de la ventana busca en los nombres y las explicaciones de todas las pestañas.

El archivo también puede editarse en cualquier editor de texto: el programa lo leerá en el siguiente comando.

### 17.3 Grupos

| Grupo | Qué define | Pestaña del plugin | Más detalles |
| --- | --- | --- | --- |
| `vault` | La carpeta de la bóveda, para ejecutar comandos desde la consola; el plugin siempre trabaja con la bóveda abierta. La escribe `Установка.bat`. | — | sección 19.1 |
| `llm` | Modo (`cloud`, `local`, `webchat`), perfiles de modelos, perfiles principales en la nube y local, modelos para pasos concretos (`roles`), límite de la petición del chat web, número de reintentos tras un error de formato. | "Modelos" («Модели»), "Avanzado" («Дополнительно») | secciones 13.1–13.5 |
| `embeddings` | Dónde se calculan los embeddings (`local` o `cloud`); dirección, modelo, clave y precio de los de la nube; tamaño del lote, límite de texto, espera; `server`: parámetros del modelo propio en llama.cpp. | "Modelos" | sección 12 |
| `budget` | Presupuesto mensual para los modelos en la nube y umbral de aviso (`warn_pct`, 10–99 %). | "Costes" («Расходы») | sección 14.3 |
| `estimate` | Estimación antes de una ejecución grande: si está activada y a partir de qué número de llamadas, coste o duración se pide confirmación. | "Costes" | sección 14.4 |
| `input` | `split_by_dates`: dividir el diario por fechas. | "Recibidos" («Входящие») | sección 4.2 |
| `updates` | `check_on_start`: si se buscan actualizaciones al iniciar Obsidian. | "General" («Основное») | sección 19.3 |
| `thresholds` | Umbrales generales: reparto sin pregunta, peso de la pista, confianza alta, suposición sobre el modo, condensación, valor mínimo y principal, similitud de duplicados, de vecinos y de patrones. | "Umbrales" («Пороги») | sección 6.5 |
| `seed_dormancy_days` | Tras cuántos días sin pensamientos nuevos se pregunta si un brote sigue vivo. | "Umbrales" | sección 7.1 |
| `dialogue_markers` | Con qué empiezan las réplicas del usuario (`я:`, "yo:") y de la IA (`ИИ:`, "IA:") en los diálogos. | "Recibidos" | sección 4.2 |
| `sources` | Fuentes, es decir, subcarpetas de `_staging`: nombre, color de la etiqueta, desplazamiento del umbral de condensación. | "Recibidos" | secciones 4.1, 6.7 |
| `style` | `global`: el estilo general de los documentos de la Fase 2. | "Documentos" («Документы») | sección 8.3 |
| `limits` | Límites de las peticiones: contenedores en una petición de clasificación (150), elementos por cada evaluación del valor (400), preguntas aclaratorias por entrada (3). Normalmente no hace falta cambiarlos. | "Avanzado" | secciones 6.4, 6.6, 6.10 |

### 17.4 Ajustes del contenedor y del documento

Algunos ajustes pueden redefinirse para un solo contenedor, con los campos `thresholds` y `style` de su ficha (sección 16.1; es más cómodo en la pestaña "Contenedor" del panel, sección 10.5), y el estilo de un solo documento, con el campo `style_override` de su encabezado (sección 16.5). Los umbrales y el estilo propios los heredan los contenedores anidados que no tienen los suyos. El umbral `mode_guess` solo puede ser general: el modo se decide antes de saber en qué contenedor acabará el pensamiento.

Los ajustes del propio plugin (la carpeta del programa, Python, las notificaciones) se guardan aparte, en el archivo del plugin dentro de la bóveda (sección 18.3).

## 18. Plugin de Obsidian

El plugin Segundo Cerebro (en Obsidian figura como «Второй мозг») es la interfaz del programa dentro de Obsidian: botones en lugar de la línea de comandos, una ventana de ajustes en lugar de editar `settings.yaml`, y el avance de la ejecución, las preguntas y los costes siempre a la vista. El plugin no contiene lógica de procesamiento: todo lo hace el programa en Python; el plugin ejecuta sus comandos y muestra el resultado. Las ediciones sencillas —el tipo y el estado de un contenedor, sus umbrales y su estilo, la casilla "Estructura aprobada" («Структура утверждена») del borrador— las hace el propio plugin mediante la API de Obsidian.

### 18.1 Funcionamiento

**Archivos.** El plugin está en la bóveda, en `.obsidian/plugins/vtoroy-mozg/`: `main.js`, `manifest.json`, `styles.css` y `data.json`, que guarda sus propios ajustes (sección 18.3). Lo instala `Установка.bat` (el comando `setup`) o el comando `install-plugin`: copia los tres archivos de la carpeta `plugin/` del programa, escribe en `data.json` la carpeta del programa y la ruta al Python del entorno `.venv`, y activa el plugin en la lista de plugins de la comunidad de la bóveda. La primera vez que se abre una bóveda con el plugin, Obsidian pregunta si confía en el autor de la bóveda: hay que elegir la opción de confiar en el autor y activar los plugins. Si la bóveda está abierta en modo restringido: en los ajustes de Obsidian, en la sección de plugins de la comunidad, desactive el modo restringido y active «Второй мозг». Si Obsidian estaba abierto durante la instalación, hay que reiniciarlo.

**Ejecución de comandos.** Cada comando es un proceso aparte en la carpeta del programa:

```
python -X utf8 -m brain --json [--ask-stdin] --vault <bóveda abierta> <comando>
```

El plugin siempre trabaja con la bóveda abierta en Obsidian, no con la que figura en `settings.yaml`. Los comandos que cambian la bóveda se ejecutan estrictamente de uno en uno: los siguientes esperan en una cola, y una ejecución idéntica que ya está en la cola no se añade otra vez. Las acciones rápidas (responder a una pregunta, editar el YAML) entran en la misma cola para no chocar con una ejecución. Los comandos que no cambian la bóveda (comprobación de conexión, búsqueda de actualizaciones, lectura y guardado de ajustes, estado del modelo propio) se ejecutan en paralelo. El propio programa tampoco deja que dos comandos trabajen con la misma bóveda: el segundo, lanzado por ejemplo desde la consola, se niega con una explicación (sección 11.3). Si no se encuentra la carpeta del programa (se movió o se borró), el panel y los ajustes lo indican y proponen especificar la carpeta.

**Líneas en vivo.** Mientras un comando trabaja, el programa imprime líneas de servicio con las que el plugin dibuja el avance:

| Línea | Qué transmite |
| --- | --- |
| `@@PROGRESS` | La etapa, el número del elemento actual, el total, el nombre del elemento; una etapa anidada, por ejemplo, las partes de un archivo grande. |
| `@@WAIT` | El programa espera la respuesta del modelo: paso, perfil, modelo, desde cuándo. |
| `@@USAGE` | Consumo: cada llamada y el total de la ejecución, en tokens y dinero. |
| `@@NOTICE` | Un aviso sobre la marcha, por ejemplo «израсходовано 80% бюджета» ("gastado el 80 % del presupuesto"). |
| `@@ASK` | Una pregunta en mitad de una ejecución (sección 18.4). |
| `@@RESULT` | El resultado al final: si salió bien, título, contadores, error. |

**Instantánea del estado** `.system/ui.json`. El programa la escribe después de cada comando y con el comando `snapshot`; el plugin la relee cada tres segundos y no calcula nada en la bóveda por su cuenta. La instantánea contiene:

- la versión del programa y la bóveda;
- el estado: número de contenedores, entradas, documentos y preguntas; etapas de las entradas (procesadas, esperando respuesta, en cola) y de los archivos recibidos; archivos nuevos en `_staging`; contenedores cuyas bases esperan un nuevo armado; el borrador de la estructura: si espera aprobación y si se ha aprobado alguna vez; peticiones del chat web que esperan respuesta; si hay trabajo sin terminar;
- contenedores: el árbol, tipo, estado, número de entradas, documentos y preguntas, estado de la base de síntesis, umbrales vigentes y de dónde viene cada uno (propio, del padre, general), estilo;
- preguntas abiertas con sus opciones;
- umbrales generales con descripciones y límites para los controles deslizantes, nombres de tipos y estados, fuentes;
- el resumen de costes (sección 14.5) y el ajuste de búsqueda de actualizaciones;
- enlaces a los registros, avisos y mensajes de la última ejecución.

### 18.2 Panel

El panel se abre con el icono del cerebro de la cinta izquierda o con el comando "Abrir el panel" («Открыть панель») y por defecto se coloca en la barra lateral derecha. Arriba están el nombre, el estado ("listo", "trabajando", "esperan respuesta: 2", "sin conexión con el programa": «готов», «работает», «ждут ответа: 2», «нет связи с программой»), el botón ↻ "Actualizar el estado" («Обновить состояние») y el engranaje, que abre los ajustes del plugin. Debajo hay cinco pestañas.

**Resumen** («Обзор»).

- **En la primera carga**, un asistente de tres pasos. El primero, "Coloque las notas en `_staging`" («Сложите заметки в `_staging`»), muestra cuántos archivos hay ya y ofrece "Abrir la carpeta _staging" («Открыть папку _staging») y "Nuevo pensamiento" («Новая мысль»). El segundo, "Fase 1: borrador de la estructura" («Фаза 1 — черновик структуры»), tiene el botón "Ejecutar la Fase 1" («Запустить Фазу 1»). El tercero, "Revise el borrador y apruébelo" («Проверьте черновик и утвердите»), tiene "Abrir el borrador" («Открыть черновик») y "Aprobar la estructura" («Утвердить структуру»). Al aprobar, el plugin guarda el borrador abierto, marca en él la casilla "Estructura aprobada" y ejecuta la Fase 1.
- **Después**, bloques con lo que requiere atención: el borrador de la estructura espera aprobación ("Abrir el borrador", "Aprobar la estructura"); se espera respuesta del chat web ("Abrir la petición" — «Открыть запрос», "Abrir el archivo de respuesta" — «Открыть файл ответа»); N preguntas esperan respuesta ("Responder" — «Ответить»); hay archivos nuevos en `_staging` ("Procesar (Fase 1)" — «Обработать (Фаза 1)»); el procesamiento no ha terminado ("Continuar (Fase 1)" — «Продолжить (Фаза 1)»). Si no hay nada: "Todo procesado" («Всё обработано»).
- Botones de acción: "Fase 1: procesar lo nuevo" («Фаза 1: обработать новое»), "Nuevo pensamiento", "Fase 2: documentos…" («Фаза 2: документы…»), "Revalidación…" («Ревалидация…»), "Patrones" («Паттерны»), "Comprobar conexión" («Проверить связь»).
- Contadores: contenedores, entradas, documentos, preguntas y una línea de etapas ("procesadas 120 · esperan respuesta 3 · en cola 5").
- El modelo actual y su coste en este mes, el coste de todos los modelos, la barra del presupuesto; el enlace "Costes →" («Расходы →»).
- Los avisos de la última ejecución y el árbol de contenedores con el número de entradas; un contenedor cuya base espera un nuevo armado aparece marcado. Al hacer clic en un contenedor, se abre en la pestaña "Contenedor".

**Preguntas** («Вопросы»). Tarjetas de las preguntas abiertas: el texto, las opciones, un campo "Respuesta propia" («Свой ответ»), enlaces a la entrada y al contenedor. La respuesta se aplica en el acto (comando `answer`); si hay una ejecución en marcha, entra en la cola ("se aplicará después de la ejecución actual" — «применится после текущего запуска»). Filtro por contenedor. Más detalles en la sección 7.3.

**Contenedor** («Контейнер»). El elegido en la lista o el contenedor de la nota abierta (interruptor "según la nota abierta" — «по открытой заметке»). El tipo y el estado son listas desplegables; el plugin los escribe en la ficha. Número de entradas, preguntas, puntos de la base de síntesis y aspectos por debajo del umbral de valor; enlaces a las vistas del pool y de la base. Los documentos del contenedor, con la marca "en revisión" («на проверке»); los botones "Escribir los documentos (Fase 2)" («Написать документы (Фаза 2)») o "Actualizar los documentos (Fase 2)" («Обновить документы (Фаза 2)») y "Comprobar de nuevo el reparto" («Перепроверить раскладку»; revalidación del contenedor, sección 10.1). Los bloques "Umbrales del contenedor" («Пороги контейнера», sección 10.5) y "Estilo de los documentos" («Стиль документов», sección 8.3).

**Costes** («Расходы»). El resumen de la sección 14.5: totales por periodos, presupuesto, tarjetas de modelos con precios, por pasos, por días, últimas ejecuciones. Los precios y el presupuesto se editan aquí mismo; tras cambiar los precios, el plugin propone recalcular las llamadas anteriores.

**Registro** («Журнал»). Las ejecuciones de esta sesión de Obsidian: icono (⧗ en cola, ▶ en marcha, ✓ terminada, ✗ error, ■ detenida), hora, duración, cuánto pensaron los modelos, tokens y dinero, resultado y salida completa del programa ("salida del programa" — «вывод программы»). Enlaces a los registros: "Cambios" («Изменения»), "Razonamientos del modelo" («Рассуждения модели»), "Histórico de preguntas" («Архив вопросов»), "Errores" («Ошибки»), `open-questions.md`.

**Durante una ejecución**, en la parte superior del panel aparece un bloque de avance:

- la etapa y la cuenta ("Análisis de archivos: 12 de 80" — «Разбор файлов: 12 из 80»), una etapa anidada, una barra;
- cuánto lleva la ejecución y cuánto falta, según la velocidad media de la etapa, a partir del primer elemento terminado (en el modo de chat web no hay tiempo: no se espera al modelo);
- "Esperando la respuesta del modelo: 0:15 · Clasificación · Z.ai" («Ждём ответа модели: 0:15 · Классификация · Z.ai»): cronómetro, paso y perfil;
- "Esta ejecución" («Этот запуск»): tokens y dinero;
- "En cola: …" («В очереди: …»): lo que se ejecutará a continuación;
- "Detener" («Стоп») e "Interrumpir ya" («Прервать сразу», con confirmación), sección 11.3; "Salida del programa" («Вывод программы»).

El resultado de una ejecución es un mensaje emergente de Obsidian y una línea en el "Registro".

**La barra de estado** de la parte inferior de la ventana: sin ejecución, «Второй мозг» o «Второй мозг · 3 вопроса» ("Segundo Cerebro · 3 preguntas"); durante una ejecución, qué se está haciendo, la cuenta, la espera del modelo o el tiempo restante, la duración. Un clic abre el panel.

**Columna estrecha.** El panel se adapta a su anchura: las pestañas pasan a una segunda línea, el estado de la cabecera se coloca bajo el nombre y, con anchuras de hasta 360 píxeles, los contadores se muestran de dos en dos.

### 18.3 Ajustes

Ajustes → Segundo Cerebro («Второй мозг»). La ventana se construye según el esquema del programa (comando `settings`): los campos, las explicaciones, los límites, los valores por defecto y la validación están en el programa (sección 17.2). Funciona tanto en una ventana de ajustes aparte como en la ventana modal habitual. Arriba hay una búsqueda en todas las pestañas.

| Pestaña | Qué contiene |
| --- | --- |
| General («Основное») | "Programa" («Программа»): la carpeta del programa, Python, "Comprobación de conexión" («Проверка связи»). "Notificaciones de Windows" («Уведомления Windows»). "Actualizaciones" («Обновления»): "Comprobar al iniciar Obsidian" («Проверять при запуске Obsidian»), "Buscar actualizaciones" («Проверить обновления»). |
| Modelos («Модели») | "Modelo de lenguaje" («Языковая модель»): modo, perfiles, "Perfil que editar" («Профиль для правки»), "＋ En la nube" («＋ Облачный»), "＋ Local" («＋ Локальный»), "Copia" («Копия»), eliminación (sección 13.2). "Modelos para pasos concretos" («Модели для отдельных шагов», sección 13.3). "Embeddings (búsqueda de similares)" («Эмбеддинги (поиск похожего)») con el bloque "Modelo propio" («Своя модель»): qué se ha descargado, si el servidor está en marcha, "Iniciar el modelo…" («Запустить модель…»), "Parar" («Остановить»), el registro del servidor (sección 12.3). "Comprobación de conexión". |
| Umbrales («Пороги») | "Umbrales generales" («Общие пороги»): un control deslizante y un campo para cada uno, más el plazo de comprobación de los brotes. |
| Recibidos («Входящие») | "Fuentes" («Источники»; "Añadir fuente" — «Добавить источник»), "Marcado de diálogos" («Разметка диалогов»), "Dividir el diario por fechas" («Делить дневник по датам»). |
| Documentos («Документы») | El "Estilo general" («Общий стиль») de los documentos. |
| Costes («Расходы») | "Presupuesto" («Бюджет»), "Estimación antes de una ejecución grande" («Оценка перед большим запуском»), enlace a la pestaña "Costes" del panel. |
| Avanzado («Дополнительно») | "Límites" («Пределы»), "Reintentos tras un error de formato" («Повторов при ошибке формата»), "Límite de la petición del chat web" («Предел запроса веб-чата»). "Servicio" («Служебное»): "Abrir la carpeta de prompts" («Открыть папку промптов»), el archivo de ajustes ("Mostrar en la carpeta" — «Показать в папке»), "Generar el informe" («Собрать отчёт», sección 15.4). |

Los campos que solo hacen falta con un valor concreto de otro campo se muestran según esa condición: por ejemplo, la clave y el precio de los embeddings en la nube, solo con "Servicio en la nube" («Облачный сервис»). Si el valor de un campo difiere del valor por defecto, el botón ↺ se ve brillante; con el valor por defecto, apagado. Las claves se escriben en un campo que no las muestra y se guardan en archivos junto al programa (comando `settings --key`); en la ventana solo se ve que la clave está guardada ("clave guardada" — «ключ сохранён»).

**Los ajustes propios del plugin** se guardan en su `data.json`, no en `settings.yaml`:

| Ajuste | Por defecto | Significado |
| --- | --- | --- |
| Carpeta del programa («Папка программы») | la escribe el instalador | Dónde están `brain/` y `Установка.bat`. |
| Python | vacío | Vacío: el Python del entorno `.venv` que creó el instalador. |
| Avisar al terminar una ejecución larga («Сообщать об окончании долгого запуска») | sí | Notificación del sistema al terminar la Fase 1, la Fase 2 o una revalidación. |
| Ejecución larga: más de, minutos («Долгий запуск — дольше, минут») | 2 | 0: avisar de cualquier ejecución. |
| Avisar cuando el programa espera una respuesta («Сообщать, когда программа ждёт ответа») | sí | Por ejemplo, el presupuesto se ha agotado o hay que confirmar una ejecución grande. |
| Solo cuando Obsidian no tiene el foco («Только когда Obsidian не в фокусе») | sí | Desactivado: las notificaciones llegan siempre. |
| Versión omitida («Пропущенная версия») | — | La versión que el usuario decidió no instalar (sección 19.3). |

Las notificaciones son notificaciones del sistema de Windows. De las ejecuciones canceladas no se avisa. Un clic en la notificación abre Obsidian y el panel. "Notificación de prueba" («Пробное уведомление») → "Mostrar" («Показать») comprueba si están permitidas; si la notificación no aparece, hay que permitir las notificaciones de Obsidian en la configuración de Windows (Sistema → Notificaciones).

### 18.4 Comandos y ventanas

Comandos en la paleta de Obsidian (Ctrl+P), todos con el prefijo «Второй мозг:» (Segundo Cerebro:):

| Comando | Qué hace |
| --- | --- |
| Abrir el panel («Открыть панель») | Abre el panel. |
| Fase 1: procesar lo nuevo («Фаза 1: обработать новое») | `run` (sección 6). |
| Nuevo pensamiento («Новая мысль») | La ventana "Nuevo pensamiento" (sección 4.5). |
| Responder a las preguntas («Ответить на вопросы») | La pestaña "Preguntas". |
| Fase 2: escribir los documentos… («Фаза 2: написать документы…») | Elegir un contenedor → `synth` (sección 8). |
| Fase 2 para el contenedor de la nota abierta («Фаза 2 для контейнера открытой заметки») | Lo mismo sin elegir. |
| Mostrar el contenedor de la nota abierta («Показать контейнер открытой заметки») | La pestaña "Contenedor". |
| Consejo de la IA sobre los umbrales del contenedor… («Совет ИИ по порогам контейнера…») | Elegir un contenedor → `advise` (sección 10.5). |
| Revalidación… («Ревалидация…») | Elegir un contenedor o "Todos los contenedores" («Все контейнеры») → `revalidate` (sección 10.1). |
| Patrones: búsqueda de nuevos tipos compuestos («Паттерны: поиск новых составных типов») | `patterns` (sección 10.4). |
| Comprobar la conexión con el modelo («Проверить связь с моделью») | `check`. |
| Costes de los modelos («Расходы на модели») | La pestaña "Costes". |
| Buscar actualizaciones del programa («Проверить обновления программы») | `update --check` (sección 19.3). |
| Actualizar el estado («Обновить состояние») | `snapshot`. |
| Informe para el desarrollador («Отчёт для разработчика») | Sección 15.4. |
| Detener («Стоп») | Igual que el botón "Detener". |

**Ventanas del plugin:** confirmación; elección de una opción (una pregunta del programa en mitad de una ejecución, una propuesta de actualizar, un reinicio de Obsidian); elección de contenedor con búsqueda por nombre; "Nuevo pensamiento" (sección 4.5); "Consejo de la IA sobre los umbrales" («Совет ИИ по порогам», sección 10.5); el resultado de la comprobación de conexión, con cada elemento por separado: la bóveda, cada modelo distinto de los pasos, los embeddings; los parámetros del modelo propio de embeddings (sección 12.3).

**Preguntas en mitad de una ejecución.** Hay decisiones que el programa no puede tomar por sí solo: el presupuesto se ha agotado (sección 14.3), la ejecución es grande o es una revalidación (sección 14.4). Entonces imprime una línea `@@ASK` con la pregunta y las opciones y espera. El plugin abre una ventana con las opciones, escribe "El programa espera su respuesta" («Программа ждёт вашего ответа») en el bloque de la ejecución, envía una notificación si hace falta y pasa la elección a la entrada estándar del programa. Cerrar la ventana equivale a negarse. En la consola, la misma pregunta se hace en la ventana de la consola: el número de la opción o «д/н» (s/n). Si no se puede preguntar, se aplica un valor por defecto seguro, indicado en las secciones 14.3 y 14.4.

Si los documentos del contenedor están al día, la Fase 2 termina sin llamadas al modelo; el plugin pregunta "¿Reescribirlos de todos modos?" («Переписать их всё равно?») y, si se acepta, la vuelve a ejecutar con `--force` (sección 8.1).

**Al iniciar Obsidian** (a los tres segundos), el plugin primero compara el plugin de la carpeta del programa con el suyo: si aquel es más reciente (se descomprimió a mano una versión nueva), propone instalarlo y reiniciar Obsidian. Después, si la búsqueda de actualizaciones está activada, busca una versión nueva del programa en GitHub (sección 19.3).

### 18.5 Errores del plugin

- Cada parte de la interfaz se dibuja por separado: la cabecera del panel, cada pestaña del panel, cada sección de cada pestaña de ajustes. Un error en una parte no rompe las demás: en su lugar aparece un marco rojo, "Error en el plugin (panel, pestaña "Costes")" («Ошибка в плагине (панель, вкладка «Расходы»)»), con el texto del error, una pista y el botón "Copiar el informe" («Скопировать отчёт»), que copia las versiones del plugin, del programa, de Obsidian y del sistema, y el error con su pila.
- Los errores no controlados de la ventana en cuya pila aparece el propio plugin también se registran, sin ventanas emergentes. El plugin no toca los errores de otros plugins ni del propio Obsidian.
- El registro es `_логи/плагин.log` (plugin) en la bóveda; al superar 512 KB, el registro anterior pasa a ser `плагин.log.old`. En memoria se guardan los últimos 30 errores; un mismo error repetido seguido se registra una sola vez.
- Copiar al portapapeles también funciona desde una ventana de ajustes aparte.
- "Informe para el desarrollador" («Отчёт для разработчика») reúne todo esto junto con la salida de las últimas ejecuciones (sección 15.4).

## 19. Instalación y actualización

### 19.1 Instalación

**Qué hace falta.** Windows, Obsidian y conexión a internet durante la instalación. Python 3.10 o posterior; si no está, el instalador lo instala él mismo. No hace falta tarjeta gráfica. El modelo de embeddings propio en el procesador necesita al menos 16 GB de RAM (sección 12.3); los embeddings en la nube no lo necesitan.

**Pasos.**

1. Una bóveda de Obsidian, existente o nueva (en Obsidian: crear una bóveda nueva o abrir una carpeta como bóveda). Las carpetas de servicio las crea el propio programa.
2. El ZIP del programa se descomprime en una carpeta aparte, por ejemplo `D:\Programas\Segundo Cerebro`. La carpeta del programa no debe estar dentro de la bóveda: el programa tomaría sus propios archivos por notas.
3. Se ejecuta `Установка.bat`. Indica qué paso está en curso y, si hay un error, qué ha fallado exactamente y qué hacer:
   - **Python.** Busca Python 3.10+ (`py`, `python` y las carpetas de instalación habituales). Si no lo encuentra, pregunta si instalar Python 3.12: lo instala solo para el usuario actual de Windows, sin permisos de administrador, mediante winget o, si no lo hay, con el instalador de python.org.
   - **Entorno.** Crea en la carpeta del programa el entorno `.venv`; si está dañado (por ejemplo, tras reinstalar Python), lo vuelve a crear.
   - **Bibliotecas** de `requirements.txt`: PyYAML, requests, numpy, dulwich. Crea `settings.yaml` a partir de la plantilla y un `api_key.txt` vacío, si aún no existen.
   - **El comando `setup`**: el resto lo hace el propio programa. Elimina los archivos `.bat` de versiones anteriores; encuentra las bóvedas de Obsidian en su lista de bóvedas (primero la que está abierta, después por la hora de la última apertura) y pregunta en cuál instalar el plugin: Enter para la primera, o un número, o la ruta a la carpeta de la bóveda (se puede arrastrar la carpeta a la ventana); si Obsidian está abierto, pide cerrarlo; instala el plugin (sección 18.1) y escribe la carpeta de la bóveda en `settings.yaml`; propone descargar en ese momento el modelo de embeddings y llama.cpp, con sus tamaños y un aviso si hay poca memoria («д/н», s/n; se puede hacer más tarde con el botón "Iniciar el modelo…", «Запустить модель…»); abre Obsidian.
4. En Obsidian, elegir la opción de confiar en el autor y activar los plugins. A la derecha aparecerá el panel «Второй мозг».
5. Ajustes → Segundo Cerebro → Modelos (en la interfaz: Второй мозг → Модели): la clave de API, el modelo del perfil, "Comprobar conexión" («Проверить связь») (sección 13).
6. Las notas, a `_staging/архив/` (archivo histórico); después, "Ejecutar la Fase 1" («Запустить Фазу 1») en el asistente de la primera carga (sección 18.2).

Si `Установка.bat` se ejecuta directamente desde el ZIP (desde una carpeta temporal de Windows), pide descomprimirlo primero.

**Volver a ejecutar** `Установка.bat` repara la instalación: reinstala las bibliotecas y el plugin y vuelve a crear un entorno roto. No toca los ajustes, las claves ni las notas. Conviene ejecutarlo si se movió la carpeta del programa, se reinstaló Python o el plugin desapareció de la bóveda.

### 19.2 Carpeta del programa

| Ruta | Qué es |
| --- | --- |
| `brain/` | El programa en Python (sección 21). |
| `prompts/` | Los prompts (sección 9); `prompts/_прежние/` (anteriores): versiones anteriores de los prompts que el usuario había editado, guardadas tras una actualización. |
| `plugin/` | El plugin compilado: `main.js`, `manifest.json`, `styles.css`. |
| `plugin-src/` | El código fuente del plugin en TypeScript y sus pruebas (secciones 21, 22). |
| `tests/` | Las pruebas del programa (sección 22). |
| `settings.template.yaml` | La plantilla de ajustes. |
| `settings.yaml`, `settings.yaml.bak` | Los ajustes (sección 17) y su versión anterior. |
| `api_key.txt`, `api_key_<id>.txt`, `embeddings_api_key.txt` | Claves de los perfiles y de los embeddings en la nube. |
| `requirements.txt` | Bibliotecas de Python. |
| `installed.json` | Qué versión está instalada, de dónde viene y las sumas de control de sus archivos (sección 19.3). |
| `Установка.bat` | Instalación y reparación. |
| `ИНСТРУКЦИЯ.md` | Instrucciones para el usuario (en ruso). |
| `.venv/` | Python y las bibliotecas del programa; lo crea `Установка.bat`. |
| `models/` | El modelo de embeddings (se puede indicar otra carpeta en `embeddings.server.models_dir`). |
| `llama.cpp/` | Compilaciones de llama-server; `server.json`, el servidor en marcha; `server.log`, su registro (sección 12.3). |

En la bóveda, el programa guarda solo las notas y sus datos de trabajo (sección 3). Las claves y los ajustes se quedan en la carpeta del programa: no entran en la sincronización ni en las copias de seguridad de las notas.

### 19.3 Actualización

**De dónde.** La fuente de las versiones nuevas es un repositorio de GitHub cuyo enlace está escrito en el propio programa: la línea `UPDATE_REPO` de `brain/__init__.py` (del tipo `https://github.com/nombre/repositorio`). En los ajustes del usuario no aparece. Si la línea está vacía, no se buscan actualizaciones y el botón "Buscar actualizaciones" («Проверить обновления») está inactivo. El repositorio debe ser público.

La versión nueva se toma de la última versión publicada (release) del repositorio: el ZIP del programa entre los archivos de la release (un `.zip` con «мозг» o "brain" en el nombre; si no, el primer `.zip`) y, si no lo hay, el archivo de código fuente de la release. Si no hay releases, la rama por defecto; su versión es `__version__` de `brain/__init__.py`. Las versiones se comparan por números: `2.10.0` es más reciente que `2.9.1`.

**Qué cambia.** Las carpetas `brain/`, `prompts/`, `plugin/`, `plugin-src/`, `tests/` y los archivos de la raíz de la carpeta del programa (`.bat`, `.md`, `.txt` y la plantilla `settings.template.yaml`). Los módulos de `brain/` que no están en la versión nueva se eliminan; los `.bat` de versiones anteriores, también. Si ha cambiado `requirements.txt`, el programa instala las bibliotecas que faltan. El plugin también se copia a la bóveda si está instalado allí. Si en la versión nueva la línea `UPDATE_REPO` está vacía y en la instalada hay un enlace, el enlace se conserva; de lo contrario, el programa dejaría de ver las versiones siguientes.

**Nunca se tocan:** `settings.yaml` y `settings.yaml.bak`, los archivos de claves y tokens, la bóveda. `installed.json` no se copia de la versión nueva: el programa lo escribe él mismo, con las sumas de control de los archivos recién instalados.

**Prompts editados por el usuario.** `installed.json` guarda las sumas de control de los archivos instalados. Si un prompt difiere del instalado (se editó): si ese prompt no ha cambiado en la versión nueva, se queda el del usuario; si ha cambiado, se instala el nuevo, el del usuario se copia a `prompts/_прежние/<nombre> (<fecha> <hora>).md` y el resultado de la actualización lo indica.

**Cómo se ejecuta.**

- **Desde el plugin.** Al iniciar Obsidian (si está activado "Comprobar al iniciar Obsidian", «Проверять при запуске Obsidian», `updates.check_on_start`), el plugin ejecuta `update --check`. Si la versión es más reciente, aparece la ventana "Hay una versión nueva" («Вышла новая версия»): el número, de dónde viene, la descripción de la release y "Instalar" («Установить»), "Más tarde" («Позже»), "Omitir esta versión" («Пропустить эту версию»). Una versión omitida ya no se propone al iniciar, pero la siguiente sí; el botón "Buscar actualizaciones" de los ajustes (pestaña "General") comprueba en el acto y muestra cualquier versión nueva. "Instalar" ejecuta `update --yes`: la actualización entra en la cola del plugin y empieza después de la ejecución actual. Después aparece la ventana "Reiniciar Obsidian" («Перезапустить Obsidian»): el plugin nuevo funcionará tras el reinicio.
- **Desde la consola.** `python -m brain update` pide confirmación; `--yes`, sin preguntar; `--check`, solo comprobar; `--force`, instalar aunque la versión no sea más reciente.
- **A mano.** El ZIP nuevo se descomprime encima de la carpeta del programa y después se ejecuta `Установка.bat`: instala las bibliotecas que falten y actualiza el plugin en la bóveda. El ZIP no contiene `settings.yaml` ni las claves, así que los ajustes no se sobrescriben. Los prompts editados se sustituyen por los nuevos al descomprimir a mano: guarde antes copias de sus ediciones. Si no se ejecuta `Установка.bat`, el plugin notará en el siguiente inicio de Obsidian que en la carpeta del programa hay un plugin más reciente y propondrá instalarlo y reiniciar Obsidian.

## 20. Comandos del programa

Normalmente los comandos los ejecuta el plugin. Desde la consola, en la carpeta del programa y con el entorno de Python `.venv`:

```
.venv\Scripts\python.exe -m brain <comando> [parámetros]
```

Sin comando, el programa imprime la lista de comandos. En la consola, las preguntas se hacen en la propia ventana: el número de la opción o «д/н» (s/n).

**Parámetros comunes** (se escriben antes del comando):

| Parámetro | Qué hace |
| --- | --- |
| `--settings <ruta>` | Otro archivo de ajustes; por defecto, `settings.yaml` junto al programa. |
| `--vault <carpeta>` | Otra bóveda; `settings.yaml` no cambia. El plugin siempre pasa la bóveda abierta. |
| `--json` | Al final, una línea `@@RESULT {…}` con el resultado (para el plugin, sección 18.1). |
| `--ask-stdin` | Las preguntas en mitad de una ejecución llegan como línea `@@ASK {…}`; la respuesta es una línea JSON `{"choice": N}` en la entrada estándar (sección 18.4). |

**Comandos:**

| Comando | Qué hace |
| --- | --- |
| `run [--yes]` | Fase 1: aceptar las respuestas a las preguntas y las ediciones manuales, procesar todo lo nuevo de `_staging` y volver a armar las bases de síntesis (sección 6). Antes de una ejecución grande, estimación y pregunta; `--yes`, sin pregunta. |
| `synth [contenedor] [--force] [--yes]` | Fase 2: escribir o actualizar los documentos de un contenedor (sección 8). Sin nombre, se elige de una lista. Si nada ha cambiado desde la última síntesis, no se llama al modelo; `--force`, reescribir de todos modos. |
| `revalidate [contenedor] [--ask] [--yes] [--count]` | Comprobación profunda del reparto (sección 10.1). Sin nombre, todas las entradas; `--ask`, elegir el contenedor de una lista; `--yes`, sin confirmación; `--count`, solo contar las entradas. |
| `patterns` | Búsqueda de nuevos tipos compuestos de aspectos (sección 10.4). |
| `advise [contenedor]` | Consejo del modelo sobre los umbrales del contenedor; por sí mismo no cambia nada (sección 10.5). Sin nombre, se elige de una lista de todos los contenedores. |
| `answer <QID> --option <N>` o `--text "<respuesta>"` | Responder a una pregunta en el acto, sin esperar a la Fase 1. Las opciones se numeran desde cero (sección 7.3). |
| `check` | Comprobar los ajustes y la bóveda, cada modelo distinto (el principal y los de los pasos) con una llamada de prueba y los embeddings con un vector de prueba. El resultado se da para cada elemento por separado. |
| `status` | Qué está en curso ahora: entradas, preguntas, colas, costes. |
| `usage [--reprice <perfil\|emb\|all>]` | Costes: hoy, este mes, desde el principio, por perfiles y por pasos (sección 14.5). `--reprice`: recalcular el coste de las llamadas anteriores con los precios actuales de un perfil, de los embeddings o de todos (sección 14.2). |
| `estimate run`, `estimate synth <contenedor>`, `estimate revalidate [contenedor]` | Estimación de una ejecución sin ejecutarla: llamadas, tiempo, coste (sección 14.4). |
| `llama status [--hw]` | El modelo de embeddings propio (sección 12.3): qué se ha descargado, si el servidor está en marcha; `--hw`, también el hardware del ordenador. |
| `llama start [--params-json <archivo\|->]` | Descargar lo que falte e iniciar el servidor del modelo; los parámetros de arranque, en JSON desde un archivo o desde la entrada estándar. |
| `llama stop` | Parar el servidor del modelo. |
| `llama download [--yes]` | Solo descargar el modelo y llama.cpp. `pull-embeddings` hace lo mismo. |
| `update [--check] [--yes] [--force]` | Actualizar el programa desde GitHub (sección 19.3): `--check`, solo comprobar; `--yes`, sin preguntar; `--force`, aunque la versión no sea más reciente. |
| `snapshot` | Reescribir la instantánea `.system/ui.json` para el plugin (sección 18.1). |
| `settings` | El esquema y los valores actuales de los ajustes en JSON; con ellos el plugin construye la ventana de ajustes. |
| `settings --set-json <archivo\|->` | Aplicar cambios de ajustes desde JSON: comprobarlos, reescribir `settings.yaml` con las explicaciones y dejar el anterior en `settings.yaml.bak` (sección 17.2). |
| `settings --key profile:<id>` o `--key embeddings` | Guardar una clave desde la entrada estándar en el archivo de clave de un perfil o de los embeddings en la nube. |
| `install-plugin [bóveda]` | Solo instalar el plugin en una bóveda (sección 18.1). |
| `setup [bóveda]` | Instalación "todo en uno"; la ejecuta `Установка.bat` después de instalar las bibliotecas (sección 19.1). |

En los comandos, el contenedor se indica por su nombre —sin necesidad de comillas (`synth Club de lectura`)—, por una parte del nombre si no es ambigua (`synth Puls`) o por su `id` (`synth k004`).

Cualquier comando, salvo `setup`, elimina además de la carpeta del programa los archivos `.bat` de versiones anteriores.

**Códigos de salida:**

| Código | Significado |
| --- | --- |
| 0 | Hecho. |
| 1 | Un error comprensible (falta la clave, el servidor no responde, un valor de ajuste incorrecto) o una detención; la salida indica qué hacer. |
| 2 | Un error imprevisto del programa. Los detalles están en `_логи/ошибки.log` (errores); todo lo procesado antes se ha guardado, y una nueva ejecución continuará desde el mismo lugar (sección 15.4). |

## 21. Mapa del código

### 21.1 El programa (`brain/`)

Programa en Python 3.10+; bibliotecas: PyYAML, requests, numpy y dulwich (git sin instalar git). Punto de entrada: `python -m brain` (`__main__.py` → `cli.py`).

**Recorrido de los datos en la Fase 1:** `cli.py` toma el bloqueo de la bóveda y construye el contexto (`context.py`) → `phase1.py` aplica las respuestas (`answers.py`) y las ediciones manuales (`vault.py`) y acepta los archivos (`ingest.py`) → borrador de la estructura (`structure.py`) o clasificación (`classify.py`) → pasos de cada entrada (`pipeline.py`: preguntas, condensación, vectores mediante `embed.py` e `index.py`, extracción de aspectos) → armado de las bases de síntesis (`synthesis_base.py`) → vistas (`views.py`), versiones (`versions.py`), preguntas (`questions.py`), instantánea para el plugin (`snapshot.py`). Todas las llamadas al modelo pasan por `llm.py` con los prompts de `prompts.py`; el consumo lo registra `logs.py`.

| Módulo | Qué hace |
| --- | --- |
| `__init__.py` | La versión del programa (`__version__`) y el enlace al repositorio de actualizaciones (`UPDATE_REPO`). |
| `__main__.py` | Punto de entrada `python -m brain`. |
| `cli.py` | Los comandos y sus parámetros (sección 20), el bloqueo de la bóveda, el resultado `@@RESULT`, los códigos de salida, la anotación de errores imprevistos en `ошибки.log` (errores). |
| `config.py` | Lectura de `settings.yaml`: valores por defecto, conversión de formatos anteriores, mensajes claros sobre errores de YAML. |
| `schema.py` | El esquema de ajustes para el plugin (pestañas, campos, límites, descripciones de los umbrales), la validación de valores, la escritura de `settings.yaml` con explicaciones, los archivos de claves. |
| `profiles.py` | Perfiles de modelos, modo, modelos para pasos concretos (sección 13). |
| `context.py` | El contexto de la ejecución: ajustes, bóveda, modelos, registros, umbrales vigentes del contenedor, la marca de "Detener", el avance. |
| `vault.py` | La bóveda: carpetas, fichas, entradas, documentos, pools, bases de síntesis, estado; ediciones manuales de la estructura (renombrado, traslado, fichas nuevas), colores. |
| `util.py` | Archivos, fechas, encabezados YAML, nombres de archivo seguros, escritura fiable (a través de un archivo temporal, con reintentos si el archivo está ocupado). |
| `ingest.py` | Lectura de los archivos recibidos: codificación, encabezado de servicio, fechas, marcado de diálogos, división del diario por fechas (sección 4). |
| `phase1.py` | La Fase 1 completa (sección 6.1). |
| `structure.py` | El borrador de la estructura y su aprobación (sección 6.3). |
| `classify.py` | Modo del archivo, clasificación con segmentación, aplicación de los umbrales, la pregunta "Dónde clasificar la entrada" (secciones 6.2, 6.4, 6.5). |
| `pipeline.py` | Los pasos de cada entrada: preguntas aclaratorias, condensación, vectores, extracción de aspectos (secciones 6.6–6.9). |
| `aspects.py` | Tipos de aspectos, fórmulas de los compuestos, tabla de prioridad (sección 5). |
| `ops.py` | Operaciones comunes con entradas y contenedores: creación, traslado, adición y eliminación de aspectos, disolución de compuestos. |
| `synthesis_base.py` | Análisis del pool, evaluación del valor, armado de la base de síntesis y comparación con la anterior (secciones 6.10–6.13). |
| `answers.py` | Aplicación de las respuestas: un manejador propio para cada tipo de pregunta, anotación de las decisiones en el registro de reflexión (sección 7.4). |
| `questions.py` | El catálogo de preguntas, `open-questions.md`, la lectura de las casillas marcadas y de las respuestas «Ответ:» (Respuesta:). |
| `phase2.py` | Fase 2: los documentos del contenedor y la comparación de versiones (sección 8). |
| `ondemand.py` | La revalidación y la búsqueda de nuevos tipos compuestos (secciones 10.1, 10.4). |
| `tuning.py` | Umbrales del contenedor y consejo del modelo: estadísticas de decisiones, comprobación de las propuestas (sección 10.5). |
| `llm.py` | El cliente del modelo de lenguaje: API en formato OpenAI, modo manual mediante chat web, modelo de prueba; reintentos, comprobación y corrección del formato de la respuesta (secciones 13.4, 13.5). |
| `prompts.py` | Carga de los prompts de `prompts/` e inserción de los datos (sección 9). |
| `embed.py` | Embeddings (servidor propio, otro compatible, en la nube o de prueba) y el almacén de vectores (sección 12). |
| `index.py` | El índice vectorial de tres niveles: entradas, aspectos, contenedores (sección 12.2). |
| `llama.py` | El modelo de embeddings propio: hardware del ordenador, descarga del modelo y de llama.cpp, elección de la compilación, arranque del servidor con los parámetros elegidos y su parada (sección 12.3). |
| `usage.py` | Coste de las llamadas, presupuesto, recálculo con precios nuevos, resumen de costes (sección 14). |
| `estimate.py` | Estimación de una ejecución: llamadas, tiempo, dinero (sección 14.4). |
| `interact.py` | Las líneas en vivo `@@…` para el plugin y las preguntas en mitad de una ejecución, en la ventana del plugin o en la consola (sección 18.4). |
| `logs.py` | Los registros de cambios y de razonamientos, el registro de reflexión, la anotación de las llamadas en el registro de llamadas (sección 15). |
| `versions.py` | Versiones de las bases de síntesis y de los documentos en el espejo git `.system/versions/` (sección 11.2). |
| `views.py` | Las vistas `_аспекты.md` (aspectos) y `_база синтеза.md` (base de síntesis). |
| `snapshot.py` | La instantánea `.system/ui.json` para el plugin (sección 18.1). |
| `install.py` | Instalación del plugin en la bóveda, búsqueda de bóvedas de Obsidian, limpieza de archivos de versiones anteriores (sección 19.1). |
| `updater.py` | Actualización desde GitHub (sección 19.3). |

Los prompts son archivos Markdown en `prompts/` (sección 9). Los textos de la interfaz, los mensajes del programa y los prompts están en ruso.

### 21.2 El plugin (`plugin-src/`)

El plugin está escrito en TypeScript; esbuild lo empaqueta en un solo archivo, `plugin/main.js`, y coloca a su lado `manifest.json` y `styles.css`. Compilación: Node.js 18+; en la carpeta `plugin-src`, `npm install` y luego `npm run build` (primero la comprobación de tipos, después el empaquetado). Tras compilar, `install-plugin` o `Установка.bat` y reiniciar Obsidian.

| Archivo | Qué hace |
| --- | --- |
| `src/main.ts` | El plugin en sí: comandos de la paleta, el panel, la barra de estado, la lectura de la instantánea `ui.json`, las ediciones del YAML mediante la API de Obsidian, las notificaciones de Windows, las comprobaciones al iniciar Obsidian (plugin más reciente en la carpeta del programa, versión nueva en GitHub), la instalación de la actualización y el reinicio. |
| `src/engine.ts` | La ejecución del programa, la cola de ejecuciones, "Detener" e "Interrumpir ya", el análisis de las líneas en vivo y del resultado `@@RESULT`, las respuestas a `@@ASK`. |
| `src/view.ts` | El panel: el bloque de la ejecución actual y las pestañas "Resumen", "Preguntas", "Contenedor", "Costes" y "Registro". |
| `src/settings.ts` | La ventana de ajustes según el esquema del programa: pestañas, búsqueda, perfiles, modelos de los pasos, ↺, guardado automático, el bloque "Modelo propio". |
| `src/modals.ts` | Ventanas: confirmación, elección de opción, texto, elección de contenedor, "Nuevo pensamiento", consejo sobre umbrales, comprobación de conexión, parámetros del modelo propio. |
| `src/report.ts` | Errores del plugin: captura, marco rojo, `плагин.log`, "Informe para el desarrollador". |
| `src/types.ts`, `src/util.ts` | Tipos de la instantánea y funciones auxiliares. |
| `styles.css` | Estilos basados en las variables del tema de Obsidian: temas claro y oscuro, columna estrecha. |
| `manifest.json`, `package.json`, `tsconfig.json`, `esbuild.config.mjs` | Descripción del plugin, dependencias de compilación, ajustes de TypeScript y del empaquetado. |
| `tests/` | Las pruebas del plugin (sección 22.2). |

**Nombres en las clases.** Las clases del plugin heredan de clases de Obsidian (`Plugin`, `PluginSettingTab`, `ItemView`, `Modal`, `FuzzySuggestModal`). Sus campos y métodos propios no pueden llamarse igual que los miembros internos de esas clases: Obsidian los llama por su cuenta, y un miembro del plugin con el mismo nombre rompe, por ejemplo, la ventana de ajustes. Solo pueden coincidir los nombres de la API pública de `obsidian.d.ts` y los métodos que Obsidian espera de un plugin (`onload`, `display`, `onOpen`…). Esto lo comprueba una prueba en un Obsidian real (sección 22.2).

## 22. Pruebas

El programa y el plugin pueden probarse por completo sin un modelo real, sin internet y sin Windows: en lugar del modelo responde el de prueba, y en lugar de GitHub, Hugging Face y el proveedor, simulaciones locales.

### 22.1 El programa (`tests/`)

**El modelo de prueba.** `tests/fake_llm.py` da respuestas verosímiles a todos los prompts (sección 9.2) según reglas sencillas y una vez responde a propósito con un error de formato, para probar la corrección de la respuesta. Se activa en los ajustes: `llm.mode: fake` (el módulo es `llm.fake_module`, por defecto `tests/fake_llm.py`) y `embeddings.mode: fake`, que da vectores de prueba en lugar del modelo de embeddings.

| Prueba | Qué comprueba | Cómo ejecutarla |
| --- | --- | --- |
| `smoke.py` | Prueba de extremo a extremo con el modelo de prueba, desde una bóveda vacía (véase más abajo). | `python tests/smoke.py [carpeta]`; por defecto, en una carpeta temporal |
| `api_mock.py` | La capa de red sin un proveedor real: un servidor local en formato OpenAI (`chat/completions` y `embeddings`) con errores 429, 500 y 401, una respuesta cortada y una respuesta que no está en JSON; perfiles de modelos y sus claves, tokens de la respuesta del proveedor y de los contadores de llama.cpp, caché, coste, presupuesto y límite del perfil, recálculo con precios nuevos, embeddings en la nube con precio. | `PYTHONPATH=. python tests/api_mock.py` |
| `big_file.py` | Un archivo grande: división en porciones que caben en la ventana del modelo y continuación tras un fallo a mitad de camino, sin duplicados. | `python tests/big_file.py [carpeta]` |
| `update_mock.py` | Actualización sin internet: un servidor local en formato de la API de GitHub, con la última release y el ZIP del programa, el archivo de código fuente, un repositorio sin releases (rama, árbol de archivos, ZIP de la rama) y errores. Los ajustes y las claves quedan intactos, los prompts modificados van a `prompts/_прежние` (anteriores), los módulos obsoletos y los `.bat` de versiones anteriores se eliminan, y el plugin de la bóveda se actualiza. | `python tests/update_mock.py` |
| `fake_llama.py` | No es una prueba, sino simulaciones para el modelo de embeddings propio: Hugging Face (la lista de archivos y el archivo del modelo con descarga reanudable), las releases de llama.cpp en GitHub y un `llama-server` falso en Python (`--help`, `--list-devices`, `/health`, `/v1/models`, `/v1/embeddings`). Las usan `smoke.py` y la prueba del plugin. | — |

**Qué recorre `smoke.py`:**

1. Carga masiva del archivo histórico: fechas, pistas, un diálogo con una IA, un archivo en cp1251, un archivo vacío, una imagen.
2. Edición y aprobación del borrador de la estructura.
3. Reparto, preguntas, aspectos, bases de síntesis.
4. Respuestas a preguntas y ediciones del YAML, incluido el traslado de una entrada (impugnar el reparto).
5. Un pensamiento nuevo que revisa uno antiguo: obsolescencia de un aspecto.
6. Fase 2: documentos y versiones.
7. Edición manual de un documento → entrada nueva → reconstrucción.
8. Edición del texto de una entrada procesada, un brote olvidado, un fallo a mitad de la ejecución y la continuación.
9. Cambio del modelo de embeddings: recálculo de los vectores.
10. Modo manual a través de un chat web.
11. Una ejecución repetida sin nada nuevo: sin llamadas al modelo.
12. Otros comandos.
13. Ediciones manuales: el tipo escrito en ruso, contenedores creados a mano.
14. Comandos para el plugin: la instantánea, las respuestas, los ajustes, los umbrales propios de un contenedor, el consejo sobre umbrales, "Detener", la instalación del plugin.
15. Conversión de ajustes del formato anterior, diario por fechas, estimación de la ejecución, preguntas por la entrada estándar (iniciar, cancelar, ventana cerrada), líneas en vivo del avance, registro de llamadas y resumen.
16. Instalación "todo en uno": búsqueda y elección de la bóveda, `setup` completo, eliminación de los `.bat` de versiones anteriores.
17. El modelo de embeddings propio: descarga desde las simulaciones, inicio, arranque automático, parada, parámetros incorrectos; actualización cuando el enlace al repositorio no está escrito en el programa.

### 22.2 El plugin (`plugin-src/tests/`)

**Prueba con una simulación de Obsidian**: `run_e2e.py`. El plugin compilado se ejecuta en Chromium sobre una simulación de la API de Obsidian (`obsidian-mock.js`, `harness.html`: área de trabajo, bóveda, YAML, ventanas, ajustes, lanzamiento de procesos) junto con el programa real y el modelo de prueba, y recorre todo el camino del usuario: el asistente de la primera carga, la espera de la respuesta del modelo, la aprobación de la estructura, las preguntas, los umbrales (control deslizante, ↺) y el consejo sobre umbrales, el estilo, la Fase 2, "Nuevo pensamiento", los ajustes (pestañas, búsqueda, perfiles, modelos de los pasos), el avance de la ejecución "N de M", "Detener", "Costes" (precios, recálculo, presupuesto), las preguntas sobre el presupuesto y sobre una ejecución grande, las notificaciones, el registro, el tema oscuro, la instalación del plugin desde la carpeta del programa, la actualización desde una simulación de GitHub y el modelo de embeddings propio (la ventana de parámetros, la descarga desde las simulaciones, el inicio del `llama-server` falso, la dirección en los ajustes, "Parar"). Las capturas de pantalla quedan en `<carpeta>/shots`.

```
pip install pyyaml requests numpy dulwich playwright
playwright install chromium
python plugin-src/tests/run_e2e.py /tmp/e2e
```

**Prueba en un Obsidian real**: `run_real.py`. La simulación solo sabe de Obsidian lo que se ha escrito en ella, así que el mismo plugin se prueba también en un Obsidian real para Linux (el archivo descomprimido de github.com/obsidianmd/obsidian-releases) en una pantalla virtual Xvfb; se controla mediante el protocolo de depuración de Chromium. El recorrido: instalación con el comando `setup`, la opción de confiar en el autor y activar los plugins («Довериться автору и включить плагины»: la prueba ejecuta Obsidian en ruso), el asistente, la Fase 1 y la aprobación de la estructura, las pestañas del panel, los ajustes en una ventana aparte y en una ventana modal (todas las pestañas, la búsqueda, los umbrales, un perfil con confirmación de borrado, la comprobación de conexión), "Nuevo pensamiento", la elección de contenedor, un error en el plugin (el marco, el portapapeles, `плагин.log`), el informe para el desarrollador y los errores de consola en todas las ventanas.

El último paso comprueba los nombres en las clases (sección 21.2): los nombres de los campos y métodos de cada clase del plugin se comparan con los nombres del Obsidian en ejecución (la cadena de prototipos de la clase base y los campos de una instancia vacía de ella), descontando la API pública y los métodos que Obsidian espera de un plugin. Una coincidencia es un fallo de la prueba. Los nombres de Obsidian se guardan en `obsidian-names.json`; con ellos es fácil comparar la siguiente versión de Obsidian.

```
python plugin-src/tests/run_real.py /ruta/a/obsidian-<versión> /tmp/real
```

`run_e2e.py` está pensado para Linux o macOS (prepara una copia de prueba del programa con `.venv/bin/python`), y `run_real.py`, para Linux con Xvfb; `REAL_KEEP=1`: no cerrar Obsidian después de la prueba.

### 22.3 Variables de entorno para las pruebas

| Variable | Qué sustituye |
| --- | --- |
| `BRAIN_SETTINGS` | La ruta al archivo de ajustes en lugar de `settings.yaml` junto al programa. |
| `BRAIN_UPDATE_REPO`, `BRAIN_GITHUB_API` | El enlace al repositorio (como si estuviera escrito en `UPDATE_REPO`) y la dirección de la API de GitHub, para actualizar desde una simulación. |
| `BRAIN_HF_BASE`, `BRAIN_LLAMA_API` | Las direcciones de Hugging Face y de las releases de llama.cpp, para descargar desde simulaciones. |
| `BRAIN_LLAMA_NO_SYSTEM` | No buscar un `llama-server` instalado en el ordenador. |
| `BRAIN_TEST_HW` | El hardware del ordenador (memoria, tarjetas gráficas): un JSON que se superpone a lo detectado. |
| `BRAIN_OBSIDIAN_CONFIG`, `BRAIN_OBSIDIAN_RUNNING`, `BRAIN_NO_OPEN` | La carpeta con la lista de bóvedas de Obsidian, "si Obsidian está abierto" y la prohibición de abrirlo, para probar la instalación. |
| `BRAIN_APP` | La carpeta del programa para las pruebas del plugin. |
