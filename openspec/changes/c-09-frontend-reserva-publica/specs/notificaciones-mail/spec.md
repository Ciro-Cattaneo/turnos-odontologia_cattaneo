# Spec Delta

## MODIFIED Requirements

### Requirement: Plantillas de mail con datos mínimos y link de cancelación

The system SHALL build each mail with a subject and body per notification type containing the patient name, professional name, local date and time, duration and the cancellation link. It SHALL render times in `America/Argentina/Buenos_Aires` while persisting UTC, and SHALL NOT include DNI, phone or obra social. (RN-NO-01, duro 10, duro 12.)

#### Scenario: Mail de recordatorio incluye link y hora local

- **DADO** una `Notificacion` válida de tipo `recordatorio_24h` con `payload.inicio` en UTC
- **CUANDO** el worker construye y envía el mail
- **ENTONCES** el asunto y el cuerpo están en español, incluyen la hora local de Buenos Aires, el nombre del profesional y `payload.cancel_url` como link `GET /cancelar?token=<token>&id=<id>`, donde `token` es la única credencial y `id` es el localizador opaco del turno (RN-NO-01, PB-01, duro 4)

#### Scenario: Mail no incluye datos sensibles innecesarios

- **DADO** una `Notificacion` válida con `payload` sin DNI, teléfono ni obra social
- **CUANDO** el worker construye el mail
- **ENTONCES** el cuerpo no contiene DNI, teléfono ni obra social, y solo usa los campos declarados del payload (duro 12)
