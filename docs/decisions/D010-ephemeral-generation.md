# D010 — Generación efímera vinculada a preguntas en M3

## Status

Accepted para M3; contrato y cliente Gemini implementados en #9 e integración
HTTP implementada en #10.

## Problem and decision

Queremos aprender a integrar un LLM con las preguntas existentes sin introducir
almacenamiento de respuestas. El desarrollador elige generar y devolver:
recuperar una pregunta persistida, llamar a Gemini, validar el resultado y
devolverlo por HTTP. La respuesta no se guarda; repetir la operación puede
producir otra respuesta.

El contrato HTTP acordado es `POST /questions/{question_id}/generate`, sin
cuerpo de petición. Una operación correcta termina con `200 OK`; un UUID
inválido devuelve `422` y una pregunta inexistente, `404`, sin llamar al LLM.
No se crea una tabla `answers` ni una cabecera `Location` para la generación.

El cuerpo correcto incluye `answer: str`, `limitations: list[str]` (que puede
ser vacía) y `external_sources_consulted: false`. Gemini genera `answer` y
`limitations`; EvidenceOps establece el indicador de fuentes externas, ya que
esta operación no consulta ninguna. Pydantic validará el contrato estructural,
sin determinar la veracidad biomédica. El desarrollador acordó exigir que
`answer` contenga texto tras quitar espacios exteriores y que cada elemento
de `limitations` contenga texto; la lista puede estar vacía. Ambos campos son
obligatorios. No se añaden límites arbitrarios de longitud o número de
limitaciones en este primer contrato.

Ejemplo de la operación acordada, con una pregunta ya registrada:

```http
POST /questions/9f4d9b6b-2c4d-4f72-9d24-263412df46aa/generate
```

```json
{
  "answer": "Respuesta generada y validada para la pregunta almacenada.",
  "limitations": ["No se han consultado fuentes biomédicas externas."],
  "external_sources_consulted": false
}
```

El ejemplo muestra el formato, no una respuesta biomédica evaluada. No se
envía cuerpo HTTP: EvidenceOps recupera el texto de la pregunta por ID.

El desarrollador redactó la primera instrucción para el modelo: responder con
claridad y prudencia usando su conocimiento, producir `answer` y limitaciones
relevantes (incluida información clínica faltante cuando proceda), evitar
referencias inventadas y no afirmar que consultó fuentes externas. La pregunta
persistida se enviará separadamente como entrada del usuario. Se pedirá una
salida estructurada con un esquema real de los dos campos generados y se
validará de nuevo en EvidenceOps. El prompt vigente está en `SYSTEM_INSTRUCTION`, en `gemini.py`.

Se acordó concretar la precaución sobre referencias: no proporcionar estudios,
citas, cifras o resultados específicos si no se tiene suficiente certeza y
expresar incertidumbre cuando corresponda. Esta instrucción no permite al
modelo verificar hechos por sí mismo.

## Trade-offs

La operación es pequeña y permite concentrarse en inferencia y validación.
No permite recuperar una respuesta anterior ni comparar automáticamente
generaciones repetidas; esto se decidirá cuando exista una necesidad real.
La dependencia que recupera `question.text` abre una Session corta y la cierra
antes de llamar al generador. Así no retiene conexión ni transacción durante
la espera externa; la generación utiliza el texto recuperado en ese momento.
