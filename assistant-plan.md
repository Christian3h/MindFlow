# Asistente Personal — MindFlow

## Overview

Asistente conversacional vía Telegram que funciona como "segundo cerebro". Se comunica con el usuario a lo largo del día, registra datos (sueño, finanzas, rutina), y lo motiva como un coach personal.

## Stack

| Componente | Tecnología |
|------------|------------|
| Canal | Telegram Bot |
| IA | MiniMax-M2.7 |
| DB local | `assistant.db` (SQLite) — preparado para Supabase |
| Listener | Telegram Webhook |
| API Docs | https://platform.minimax.io/docs/api-reference |

## Arquitectura

```
Usuario (Telegram)
    ↓ mensaje
┌─────────────────────────┐
│   Telegram Webhook      │ ← recibe mensajes
│   /webhook/telegram     │
└────────────┬────────────┘
             ↓
┌─────────────────────────┐
│   Intent Router         │ ← clasifica intención
│   + Session Manager     │ ← mantiene contexto
└────────────┬────────────┘
             ↓
┌─────────────────────────┐
│   Flow Engine           │ ← ejecuta flows
│   + Assistant DB        │ ← almacena datos
└────────────┬────────────┘
             ↓
       MiniMax M2.7
             ↓
┌─────────────────────────┐
│   Telegram API           │ ← envía respuesta
└─────────────────────────┘
```

## Nodos MiniMax Disponibles

| Nodo | Función | Modelo default |
|------|---------|---------------|
| `minimax.chat` | Texto/conversación | MiniMax-M2.7 |
| `minimax.tts` | Texto → Audio | speech-2.8-hd |
| `minimax.music` | Generación de música | music-2.6 |
| `minimax.image` | Generación de imágenes | image-01 |
| `minimax.vision` | Análisis de imágenes | MiniMax-M2.7 |
| `minimax.usage` | Consulta quota | - |

---

## Base de Datos — assistant.db

Diseñado para migrar a Supabase sin reescribir código. Mismo schema, mismo nombre de tablas.

### Tablas

#### users
```sql
id          VARCHAR PRIMARY KEY
nombre      VARCHAR
zona_horaria VARCHAR DEFAULT 'America/Bogota'
tono_coach  VARCHAR DEFAULT 'amable'  -- estricto / amable / sarcástico / neutral
fecha_creacion VARCHAR
```

#### conversations
```sql
id              VARCHAR PRIMARY KEY
user_id         VARCHAR FK → users.id
timestamp       VARCHAR
mensaje_usuario TEXT
respuesta_bot   TEXT
intencion       VARCHAR  -- saludo / gasto / sueño / checkin / pregunta / etc
contexto_json   TEXT     -- datos extraídos en formato JSON
```

#### sleep_logs
```sql
id                  VARCHAR PRIMARY KEY
user_id             VARCHAR FK → users.id
fecha               VARCHAR
hora_acostado       VARCHAR
hora_levantado      VARCHAR
duracion_horas       REAL
calidad             INTEGER  -- 1-10
energia_al_despertar INTEGER  -- 1-10
notas               TEXT
```

#### routines
```sql
id          VARCHAR PRIMARY KEY
user_id     VARCHAR FK → users.id
nombre      VARCHAR
activa      INTEGER DEFAULT 1
dias_semana VARCHAR  -- JSON array: [1,2,3,4,5]
```

#### routine_blocks
```sql
id              VARCHAR PRIMARY KEY
routine_id      VARCHAR FK → routines.id
nombre          VARCHAR
hora_inicio     VARCHAR  -- "08:00"
hora_fin        VARCHAR  -- "10:00"
categoria       VARCHAR  -- estudio / ejercicio / trabajo / descanso
prioridad       VARCHAR  -- alta / media / baja
```

#### daily_checkins
```sql
id                  VARCHAR PRIMARY KEY
user_id             VARCHAR FK → users.id
fecha               VARCHAR
hora                VARCHAR
bloque_esperado     VARCHAR  -- FK a routine_blocks.id
estaba_haciendo     TEXT     -- "estaba en redes"
estaba_en_rutina    INTEGER  -- 0 / 1
energia_momento     INTEGER  -- 1-10
notas               TEXT
```

#### transactions
```sql
id              VARCHAR PRIMARY KEY
user_id         VARCHAR FK → users.id
fecha           VARCHAR
monto           REAL
tipo            VARCHAR  -- gasto / ingreso
categoria       VARCHAR  -- alimentación / transporte / ocio / salud / servicios / entretenimiento
subcategoria    VARCHAR  -- almuerzo / taxi / cine / etc
descripcion     TEXT
fue_impulsivo   INTEGER  -- 0 / 1 / null
metodo_pago     VARCHAR  -- efectivo / tarjeta / transferencia / nequi
```

#### events
```sql
id                  VARCHAR PRIMARY KEY
user_id             VARCHAR FK → users.id
titulo              VARCHAR
fecha               VARCHAR
hora                VARCHAR
tipo                VARCHAR  -- cumpleaños / cita / deadline / recordatorio
recurrente          INTEGER DEFAULT 0
frecuencia_recurrencia VARCHAR  -- anual / mensual / semanal
anticipacion_aviso_horas INTEGER DEFAULT 24
completado          INTEGER DEFAULT 0
```

#### daily_summary
```sql
id                  VARCHAR PRIMARY KEY
user_id             VARCHAR FK → users.id
fecha               VARCHAR
horas_dormido       REAL
energia_promedio    REAL
bloques_cumplidos   INTEGER
bloques_totales     INTEGER
porcentaje_cumplimiento REAL
gasto_total_dia     REAL
estado_animo        VARCHAR
notas_bot           TEXT
```

---

## Módulos del Asistente

### 1. Registro de Sueño
El bot pregunta al despertar:
```
7:00am → Bot: "¿Cómo dormiste? Dime hora acostado, levantaste y energía 1-10"
7:02am → Vos: "acosté 11pm, levanté 7am, energía 7"
7:03am → Bot: "Listo ✓. Dormiste 8h, energía 7/10. Hoy: bloque estudio 8-10am, gym 12pm."
```

### 2. Rutina + Check-ins
```
9:45am → Bot: "¿Cómo va el bloque de estudio? Faltan 15 min"
9:47am → Vos: "la verdad estuve en redes"
9:48am → Bot: "Ok, registrado como distracción. Quedan 13 min. ¿Los aprovechás?"
```

### 3. Finanzas (Registro Conversacional)
```
Vos: "gasté 15mil en almuerzo y 8mil en transporte"
Bot: "Listo ✓
     - Almuerzo: $15.000 (Alimentación)
     - Transporte: $8.000 (Movilidad)
     Total hoy: $23.000
     ¿Algo más?"
```

### 4. Calendario + Recordatorios
```
10:00am → Bot: "Mañana tienes: cita con doctor 3pm"
```

### 5. Resumen Diario
```
10:00pm → Bot: "Resumen del día:
           - Dormiste: 7h (meta: 7.5h)
           - Energía promedio: 7/10
           - Bloques: 6/8 (75%)
           - Gastos: $45k
           ¿Querés agregar algo?"
```

### 6. Coach / Motivación
Motivación proactiva según datos:
- Celebra cuando cumplís bloques
- Redirige cuando te dispersás
- Detecta patterns ("los martes siempre rendís bien")
- Empujones cuando estás decaído

Tonos configurables:
- `estricto`: "No cumpliste la meta. Otra vez. ¿Qué vas a hacer diferente mañana?"
- `amable`: "Bue, no llegó. No pasa nada, mañana es otro día."
- `sarcástico`: "Otro día que la noche te ganó."
- `neutral`: "Cumpliste 5/7 bloques. Está piola."

### 7. Memoria Contextual
El bot mantiene contexto entre conversaciones:
- Si hablás a las 6am de un tema y a las 11am volvés sobre lo mismo, el bot lo recuerda
- Session Manager mantiene contexto de la conversación activa
- `conversations` table guarda historial para contexto a largo plazo

---

## Fases de Desarrollo

### Fase 1 — Infraestructura Base
**Objetivo:** Bot conecta a Telegram, recibe mensajes, responde con MiniMax

**Entregables:**
- [ ] `assistant.db` creada con tablas `users`, `conversations`
- [ ] Webhook Telegram `/webhook/telegram` funcionando
- [ ] Intent Router simple (clasifica: saludo / gasto / sueño / pregunta)
- [ ] Session Manager (mantiene contexto entre mensajes)
- [ ] MiniMax responde (usuario → Telegram → MiniMax → Telegram)
- [ ] Flow engine conecta a `assistant.db`

**Test:** Mandar "hola" al bot → responde algo coherente.

**Métricas:**
- Latencia < 5s
- 0 errores 500 en conversación simple
- Webhook responde < 1s

### Fase 2 — Registro de Sueño
**Objetivo:** Bot pregunta al despertar, usuario responde, se guarda en DB

**Entregables:**
- [ ] Tabla `sleep_logs` con schema completo
- [ ] Flujo "buenos días" a las 7am
- [ ] Parseo de respuesta (hora acostado, levantaste, energía)
- [ ] Resumen mañana con datos de sueño
- [ ] Scheduler activa recordatorios diarios

**Test:** A las 7am bot pregunta → usuario responde → verificar en DB.

**Métricas:**
- 100% de sleeps registrados cuando usuario responde
- Parseo correcto > 95%
- Scheduler dispara 100%

### Fase 3 — Rutina + Check-ins
**Objetivo:** Bot gestiona bloques de tiempo y redirige

**Entregables:**
- [ ] Tablas `routines`, `routine_blocks` con schema
- [ ] Crear rutina por chat ("creá rutina: estudio 8-10am lunes a viernes")
- [ ] Check-in en inicio de cada bloque (±5 min)
- [ ] Registro de distracción (`estaba_en_rutina: false`)
- [ ] Redirección sin juzgar
- [ ] Resumen de rutina al final del día

**Test:** Crear bloque 8-9am → esperar check-in → responder distracción → verificar.

**Métricas:**
- Check-in enviado ±5 min del inicio de bloque
- `estaba_en_rutina` coincide con respuesta 100%

### Fase 4 — Finanzas
**Objetivo:** Registro de gastos en texto plano, auto-categorización

**Entregables:**
- [ ] Tabla `transactions` con schema completo
- [ ] Parsing automático de categorías
- [ ] Múltiples gastos en un solo mensaje
- [ ] Resumen diario de gastos
- [ ] Pregunta "¿fue impulsivo?" si supera umbral

**Test:** "gasté 20mil en cena y 5mil en uber" → verificar 2 registros en DB.

**Métricas:**
- Parseo categorías correcto > 90%
- 0 gastos perdidos
- Resumen coincide con sumatoria real

### Fase 5 — Calendario + Eventos
**Objetivo:** Crear eventos, recordatorios automáticos, marcar completados

**Entregables:**
- [ ] Tabla `events` con schema completo
- [ ] Crear evento por chat ("agregá cita con doctor mañana 3pm")
- [ ] Recordatorio automático según `anticipacion_aviso_horas`
- [ ] Eventos recurrentes (semanal, mensual, anual)
- [ ] Marcar completado ("ya fue", "listo")
- [ ] Ver próximos eventos ("qué tengo mañana?")

**Test:** Crear evento mañana 3pm → esperar recordatorio → marcar completado.

**Métricas:**
- Recordatorio enviado ±15 min de hora configurada
- 0 eventos perdidos
- Completado funciona 100%

### Fase 6 — Resumen Diario + Analytics
**Objetivo:** Resumen automático noche + patterns detectados + coach

**Entregables:**
- [ ] Tabla `daily_summary` con schema completo
- [ ] Resumen noche a las 10pm
- [ ] Trends semanales ("esta semana dormiste promedio 6h vs meta 7.5h")
- [ ] Patterns detectados ("los viernes gastás 40% más en ocio")
- [ ] Insights proactivos ("noté que los martes rendís mejor en estudio")
- [ ] Datos exportables para futura app de finanzas

**Test:** 7 días con datos → pedir "resumen de la semana" → verificar datos.

**Métricas:**
- Resumen generado 100% de las noches
- Datos validan contra otras tablas
- Insights son correctos

---

## Dependencias entre Fases

```
Fase 1 (Infra + Telegram listener)
         ↓
Fase 2 (Sueño) ────┐
         ↓         │
Fase 3 (Rutina) ←──┘
         ↓
Fase 4 (Finanzas)
         ↓
Fase 5 (Calendario)
         ↓
Fase 6 (Analytics)
```

**Fase 1 es bloqueante.** Una vez que ande, las demás pueden desarrollarse en paralelo.

---

## Configuración de Categorías (Finanzas)

```yaml
categorias:
  alimentación:
    - almuerzo
    - cena
    - desayuno
    - snacks
  transporte:
    - taxi
    - uber
    - bus
    - gasolina
  ocio:
    - cine
    - streaming
    - juegos
    - libros
  salud:
    - farmacia
    - doctor
    - gym
  servicios:
    - internet
    - celular
    - suscripciones
  entretenimiento:
    - conciertos
    - eventos
    - salida
```

---

## Tono de Coach — Opciones

| Tono | Descripción |
|------|-------------|
| `estricto` | Directo, sin filtro. "No cumpliste. ¿Qué vas a hacer diferente?" |
| `amable` | Empático. "No llegó, no pasa. ¿Te ayudo con el plan?" |
| `sarcástico` | Irónico pero motivador. "Otro día que la noche te ganó." |
| `neutral` | Informativo sin emocional. "Cumpliste 5/7 bloques. Mañana subimos." |

---

## Checklist de Éxito por Fase

| Fase | Criteria |
|------|----------|
| 1 | ✅ Telegram responde a mensaje<br>✅ DB tiene tablas<br>✅ MiniMax responde |
| 2 | ✅ Sueño se guarda en DB<br>✅ Resumen mañana muestra datos |
| 3 | ✅ Check-in llega en tiempo<br>✅ Registro distracción funciona |
| 4 | ✅ Gastos parseados y guardados<br>✅ Resumen diario de gastos |
| 5 | ✅ Recordatorios disparan<br>✅ Completar eventos funciona |
| 6 | ✅ Resumen noche generado<br>✅ Trends son correctos |

---

## Prróximos Pasos

1. Crear `assistant.db` con todas las tablas
2. Implementar Telegram Webhook listener
3. Implementar Intent Router + Session Manager
4. Conectar Flow Engine a MiniMax-M2.7
5. Test de conversación completa

---

*Plan creado: 2026-04-17*
*Proyecto: MindFlow*
*Stack: Telegram + MiniMax-M2.7 + SQLite (futuro: Supabase)*