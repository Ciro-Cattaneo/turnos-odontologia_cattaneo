# Anonimización Ley 25.326 — procedimiento manual admin-only (C-02, D-9)

> Sin UI en v1 (AC `paciente-privacidad/Sin-UI-v1`). Solo un admin ejecuta este
> procedimiento ante un pedido del titular (derecho de supresión / Ley 25.326).
> Usar ÚNICAMENTE datos ficticios en pruebas (regla dura 12).

## Cuándo aplica

El titular pide eliminar sus datos personales pero los turnos deben conservarse
como estadística (reportes/ausentismo, Excepciones globales KB-05). NO es un
borrado físico: el `DELETE` con turnos está prohibido (FK `RESTRICT` + PB-04).

## Pasos (admin)

1. Respaldar el pedido (canal, fecha, identidad verificada) fuera del sistema.
2. Obtener el UUID del paciente (ficha de recepción, C-10).
3. Ejecutar (host con acceso a la DB, `DATABASE_URL` en el entorno):
   `python backend/scripts/anonimizar_paciente.py --paciente-id <uuid>`
4. Verificar: el paciente queda `nombre = "Eliminado #<uuid>"`,
   `dni/telefono/email = NULL`, `obra_social = "(eliminado)"`; sus turnos
   siguen legibles; existe una fila `AuditoriaTurno(accion='anonimizar')`
   por cada turno (actor NULL = acto admin manual, ver `detalle`).
5. Registrar el acto en el libro de solicitudes (fuera del sistema).

## Qué NO hace

- No toca otros pacientes ni rompe FK (los turnos conservan `paciente_id`).
- No desactiva (`activo` queda como estaba; desactivar es un paso aparte).
- No hay endpoint ni botón: si la UI mostrara "anonimizar", fallaría el test
  `test_sin_ui_v1_para_anonimizar`.
- Paciente SIN turnos: preferir `DELETE` físico directo (PB-04 lo permite).

## Reversibilidad

Irreversible por diseño (los datos personales se descartan). Solo un restore
desde backup (C-12, retención 7 días) podría revertirlo dentro de la ventana.
