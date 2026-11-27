# D038 — Kubernetes local con kind, Traefik sin Helm y una imagen única (M12.1)

## Estado

Implementada y verificada localmente en M12.1 (#70). El encargo de M12 fijó kind
o k3d sin Helm. Las elecciones abiertas se resolvieron con la opción más simple
justificada.

## Problema

EvidenceOps solo se ejecutaba como procesos locales con PostgreSQL en Docker
Compose. M12 pide practicar Kubernetes (Pods, Deployments, Services, ConfigMaps,
Secrets, probes, recursos y escalado) sobre la aplicación real. El despliegue debe
ejercer las semánticas de liveness y readiness de D037 y las caídas de dependencia,
sin clúster cloud, sin alta disponibilidad y sin versionar secretos.

## Alternativas

| Elección | Opciones | Decisión y motivo |
| --- | --- | --- |
| Clúster local | **kind**, k3d, minikube, Kubernetes de Docker Desktop | kind. Invoca la CLI `docker`, que en este WSL funciona con un shim hacia `docker.exe`. k3d usa el socket del daemon, que aquí no existe. El de Docker Desktop no es reproducible desde manifiestos versionados |
| Ingress controller | ingress-nginx, **Traefik v3**, Gateway API (Envoy Gateway) | Traefik con manifiestos planos (RBAC + Deployment). ingress-nginx está retirado desde marzo de 2026 y no recibe parches. Gateway API no es el recurso Ingress pedido y añade CRDs y un controlador mayor |
| Límite de cuerpo | Middleware CRD, **middleware del provider de ficheros**, límite en la app | Middleware `buffering` (`maxRequestBodyBytes: 65536`) definido en un ConfigMap y aplicado a los entry points. Sin CRDs y antes de llegar a uvicorn |
| TLS | Ninguno, **autofirmado**, cert-manager | Autofirmado con `openssl` en `secrets.sh` (trivial). HTTP plano solo redirige (301), para que `X-API-Key` no viaje sin cifrar. cert-manager añade un operador sin necesidad |
| Plantillas | Helm, Kustomize, **YAML plano + scripts** | YAML plano y `bin/*.sh`. Un único entorno no justifica plantillas, y cada recurso se lee tal cual |
| Imagen | Imagen por proceso, **imagen única**, con o sin `medcpt` | Una imagen para API, worker y Job (mismo código y migraciones). Sin `medcpt` (≈1 GB de torch/transformers): el despliegue cubre preguntas, jobs y probes, no RAG |
| Secretos | Manifiesto versionado, SealedSecrets, **script** | `secrets.sh` genera password y API key con `openssl rand` directamente en el clúster y no regenera si existen |
| PostgreSQL | Deployment, **StatefulSet**, operador | StatefulSet de 1 réplica con `volumeClaimTemplates`: identidad y volumen estables. Sin réplicas ni failover |
| Migraciones | initContainer en la API, **Job**, al arrancar la app | Job. Un initContainer migraría N veces en paralelo con N réplicas. La readiness ya impide servir antes de tiempo (`migrations: missing/outdated`) |

## Decisión

- Probes de la API: startup y liveness sobre `/health` (sin dependencias),
  readiness sobre `/ready` (PostgreSQL + head de Alembic) cada 5 s, con 2 fallos
  para salir de rotación. El worker no tiene probes: no expone HTTP y sus fallos
  de BD ya tienen backoff propio (D037). Su caída la resuelve el Deployment.
- Requests/limits a partir de la memoria medida (`memory.peak` del cgroup) y no
  supuesta: la API usa ≈105 MiB en reposo (request 160 Mi, limit 512 Mi).
- Contenedores sin root, sin escalada, sin capacidades y con raíz de solo lectura.
- API con 2 réplicas para observar la rotación. Worker con 1, por el lease sin heartbeat.

## Consecuencias y límites

- Verificado: despliegue desde cero, smoke vía ingress con API key, borrado de
  pod sin pérdida de `/health` y caída de PostgreSQL con readiness 503 y
  recuperación sin reiniciar API ni worker
  ([registro](../subsystems/kubernetes.md#verificación-registrada)).
- Escalar la API multiplica el rate limit efectivo (en memoria por proceso,
  D037) y los pools de conexiones. Escalar workers aumenta el riesgo de
  doble ejecución si un job supera el lease (D036). PostgreSQL no escala.
  Detalle en [Kubernetes local](../subsystems/kubernetes.md#escalado-y-sus-límites).
- `/metrics` de la API queda expuesto a través del ingress, sin autenticación,
  igual que en local. En un entorno compartido se restringiría por ruta o con red.
- La imagen no incluye `medcpt`: RAG e indexación requieren otra imagen o el
  extra, con el coste de tamaño y memoria medido en M9.2.
- Sin HPA: necesitaría metrics-server, que en kind exige desactivar la
  verificación TLS del kubelet.
- El shim de Docker es una adaptación de este entorno WSL, no un requisito.
