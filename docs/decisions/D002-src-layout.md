# D002 — Use a src/ project layout

Estado: aceptada.

El paquete vive en `src/evidenceops/` para separar aplicación y archivos del
repositorio, evitando imports accidentales desde la raíz. Cuesta un nivel de
directorio adicional frente al paquete colocado directamente en la raíz.
