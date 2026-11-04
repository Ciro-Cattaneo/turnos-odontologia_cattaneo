# Evidencia — descubrimiento de la skill propia y del MCP en un proceso nuevo

Fecha: 2026-11-02. Comandos ejecutados desde la raíz del repo, en un proceso nuevo de opencode (sin la sesión donde se creó la skill).

## 1. La skill propia aparece en el descubrimiento

```powershell
opencode debug skill
```

Salida (recortada al objeto de la skill propia; el comando devuelve el JSON completo de todas las skills):

```json
{
  "name": "turno-spec-review",
  "description": "Revisa o prepara proposal, design, specs y tasks de un change de turnos y agenda: detecta reglas ambiguas, bordes faltantes, requisitos sin trazar a RN-* y escenarios no verificables, antes de proponer o implementar. Úsala al redactar o auditar artefactos de C-05 a C-07 y C-09; no usar para revisar código ni tests ya escritos.",
  "location": "D:\\Sistema\\Documents\\GitHub\\turnos-odontologia_cattaneo\\.opencode\\skills\\turno-spec-review\\SKILL.md",
  "content": "\n# turno-spec-review\n\nRevisa artefactos de spec de un change de turnos/agenda..."
}
```

Verificación: `name`, `description`, `location` y `content` coinciden con `.opencode/skills/turno-spec-review/SKILL.md`. La skill se descubre desde el proyecto, sin instalación global.

## 2. El MCP está conectado

```powershell
opencode mcp list
```

```
MCP Servers
  ✓ context7  connected   https://mcp.context7.com/mcp
  ✓ engram    connected   engram mcp
2 server(s)
```

Verificación: `context7` es el MCP elegido para el TP y figura `connected`; las consultas reales quedaron registradas en `01-context7-consultas.md`.

## 3. Reproducibilidad

- Config del MCP (global, fuera del repo): `C:\Users\ciroc\.config\opencode\opencode.json`, sección `mcp.context7` (`type: remote`, `url: https://mcp.context7.com/mcp`). Sin API key ni secretos.
- La skill vive versionada en el repo, por lo que un clon nuevo la descubre sin pasos extra.
- Si `opencode debug skill` no lista la skill: verificar que el archivo sea `.opencode/skills/turno-spec-review/SKILL.md` (nombre de carpeta = `name`) y reiniciar el proceso de opencode.
