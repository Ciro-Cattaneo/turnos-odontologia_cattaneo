# Ficha de investigación — Skill propia + MCP

Proyecto `turnos-odontologia_cattaneo`. Fuentes consultadas el 2026-11-02. Solo datos ficticios.

## 1. Necesidad detectada

C-05 `reserva-online-backend` concentra las reglas más delicadas del sistema. Una spec ambigua allí se propaga a código, tests y auditoría: el anti-solape bajo concurrencia (RN-TU-03) debe quedar como exclusión en base de datos; los cinco campos obligatorios con mail obligatorio (RN-TU-01, gate PB-02) deben traducirse a un 400 por campo; y bordes como dos reservas simultáneas al mismo slot, mail inválido, duración fuera de granularidad o fallo SMTP que nunca bloquea no aparecen solos en un borrador. Hoy la revisión es manual y depende de la memoria de quien la hace; falta un procedimiento estable que recorra las reglas, exija escenarios verificables y registre cada omisión.

## 2. Change elegido

**C-05 `reserva-online-backend`** (`CHANGES.md`, línea 163): sus dependencias C-02 y C-04 ya están archivadas, no depende de funcionalidad inexistente, es el próximo del camino crítico y su governance es ALTO, así que el costo de una spec incompleta es mayor. Al momento de la investigación, `openspec list --json` devolvía lista vacía (no había change activo); C-05 se creó después, en el paso 7.

## 3. Skill creadora

**`skill-creator`**, del repositorio oficial de Anthropic `https://github.com/anthropics/skills` (ruta `skills/skill-creator`; SKILL.md, LICENSE.txt, `agents/`, `assets/`, `eval-viewer/`, `references/`, `scripts/`). Es una skill estándar (frontmatter `name` + `description` y Markdown); opencode descubre skills en `~/.config/opencode/skills/` y en `.opencode/skills/`. Ya está instalada en `C:\Users\ciroc\.config\opencode\skills\skill-creator\`; para reproducirla, copiar esa carpeta del repo oficial y reiniciar el agente. El `SKILL.md` local no declara autor, pero su contenido y árbol de archivos coinciden con la carpeta oficial consultada el 2026-11-02. No se verificó la ejecución de sus scripts de evaluación (ver §9).

## 4. Diseño de la skill propia

| Atributo | Detalle |
|---|---|
| Nombre | `turno-spec-review` (kebab-case; acota el disparador al dominio y evita solaparse con `test-guard`) |
| Propósito | Revisar artefactos de spec/design/tasks de un change de turnos y emitir hallazgos clasificados con trazabilidad a las reglas de negocio |
| Cuándo se activa | Al preparar o revisar `proposal.md`, `design.md`, specs y `tasks.md` de un change de turnos (C-05 a C-07, C-09), antes de proponer o implementar. No aplica a código ni tests ya escritos |
| Entradas | Carpeta del change en `openspec/changes/<id>/`; KB 04, 05, 07 y 10; scope del change en `CHANGES.md`; las 12 reglas duras de `AGENTS.md` |
| Procedimiento | (1) Extraer las RN-* y reglas duras aplicables. (2) Mapear cada requisito a una RN-*; lo que no mapea es regla no trazable. (3) Clasificar hallazgos en ambigüedad, borde faltante, regla no trazable o escenario no verificable. (4) Exigir tres escenarios (feliz, error, borde) con resultado observable. (5) Recorrer el checklist de bordes (concurrencia, mail inválido, faltantes, duración, SMTP, token). (6) Emitir el informe sin reescribir la spec salvo pedido |
| Salida | Tabla Markdown: ID, tipo, ubicación, RN-* o regla dura, hallazgo, corrección y severidad (bloqueante/mayor/menor); cierra con conteo de escenarios y veredicto `LISTO`/`NO LISTO` |
| Criterios de revisión | Todo hallazgo cita una regla; no se inventan umbrales; cada requisito tiene tres escenarios verificables; la skill no modifica archivos |
| Ubicación | `.opencode/skills/turno-spec-review/SKILL.md`, versionado en el repositorio |

## 5. Comparación de servidores MCP

| Criterio | Context7 (Upstash) | Engram (Gentleman Programming) |
|---|---|---|
| Propósito | Documentación actualizada por versión de librerías | Memoria persistente entre sesiones |
| Capacidades | `resolve-library-id` y `query-docs` | Guardar, buscar, contexto y resumen de sesión, línea de tiempo, diagnóstico |
| Compatibilidad con opencode | Remoto HTTP; opencode lo documenta como ejemplo | Local stdio; `engram setup opencode` |
| Instalación | Ninguna: URL `https://mcp.context7.com/mcp` | Binario `engram` en PATH; SQLite en `~/.engram` |
| Permisos | Solo lectura de documentación | Lectura y escritura de memoria local |
| Credenciales | Ninguna obligatoria; API key gratuita opcional para más límite | Ninguna por defecto |
| Costos | Gratuito, MIT | Gratuito, MIT; cloud opcional |
| Aporte a C-05 | Documentación vigente de FastAPI, Pydantic, SQLAlchemy y Alembic | Ninguno documental; ya está en uso |

### Elección y justificación

Se elige **Context7**: aporta lo que el repo no tiene (la forma vigente de validar campos con Pydantic, devolver errores por campo y manejar concurrencia con SQLAlchemy 2.x), es remoto, sin credenciales, de solo lectura y se configura en una sola entrada. Engram no aporta documentación del stack: su valor es memoria y ya está operativo. Límites: solo datos ficticios; no se envían datos de pacientes ni contenido de la base a servicios remotos; no se pegan secretos en los prompts.

## 6. Pasos de instalación y configuración

**Skill creadora.** Ya instalada. Para reproducirla: copiar `skills/skill-creator` del repo oficial en `~/.config/opencode/skills/`, reiniciar y comprobar que el `name` figura entre las skills disponibles.

**MCP elegido.** Se declara en la configuración de opencode (global en `C:\Users\ciroc\.config\opencode\opencode.json`, o por proyecto en `opencode.json`). Ejemplo sin secretos:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "context7": {
      "type": "remote",
      "url": "https://mcp.context7.com/mcp",
      "enabled": true
    }
  }
}
```

Si se usa la API key gratuita: `"headers": { "CONTEXT7_API_KEY": "{env:CONTEXT7_API_KEY}" }`, siempre por variable de entorno.

Verificación ejecutada el 2026-11-02: `opencode mcp list` informó **2 servidores conectados** (`context7` y `engram`). Prueba real: `resolve-library-id` con `FastAPI` y `query-docs` sobre `/websites/fastapi_tiangolo`, que respondió con documentación de `EmailStr` y errores de validación de Pydantic. El MCP queda documentado como integración; **no se registra como skill**.

## 7. Archivos de la fundación que se van a actualizar

| Archivo | Cambio previsto | Motivo |
|---|---|---|
| `.atl/skill-registry.md` | Alta de `turno-spec-review` con propósito, ubicación, usos y compact rules | Índice que resuelven los agentes |
| `AGENTS.md` y `CLAUDE.md` | Fila en la tabla de skills, cuándo usarla, entradas y revisión de la salida (idénticos) | Contrato que lee el agente |
| `README.md` | Sección de MCP: requisitos, config sin secretos, verificación, límites y problemas conocidos | Reproducibilidad pedida por el TP |
| `skills-instaladas.txt` | Alta de `skill-creator` y `turno-spec-review` | Refleja el entorno |
| `CHANGES.md` | Referencia al change C-05 preparado, sin marcarlo implementado | Roadmap como índice canónico |

## 8. Fuentes

| Fuente | Fecha | Qué se verificó |
|---|---|---|
| `https://github.com/anthropics/skills` y `…/tree/main/skills/skill-creator` | 2026-11-02 | Repo oficial, estructura de Agent Skills y coincidencia con la copia local |
| `https://github.com/upstash/context7` | 2026-11-02 | Herramientas, endpoint, key opcional y licencia MIT |
| `https://opencode.ai/docs/mcp-servers/` | 2026-11-02 | Formato `mcp` local/remoto, ejemplo Context7 y `opencode mcp list` |
| `https://github.com/Gentleman-Programming/engram` | 2026-11-02 | Binario Go, SQLite, MCP stdio, `setup opencode`, MIT |
| Consulta de prueba a `/websites/fastapi_tiangolo` | 2026-11-02 | Respuesta correcta de Context7 |

## 9. Pendientes de verificación

- `skill-creator`: no se verificó `scripts/run_loop.py` ni `eval-viewer/generate_review.py` (dependen del CLI `claude` y subagentes). El empaquetado `.skill` requiere `present_files`, no disponible en opencode; la skill se versiona como `SKILL.md`.
- Context7 sin API key: límites de uso no medidos; ante 429 se evaluará la key gratuita.
- Engram local es v1.20.0 y anuncia v3.6.0; no se actualizó. La comparación usa la versión instalada y el README oficial.

