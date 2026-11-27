# D039 — AWS como diseño documentado: ECS Fargate + RDS, sin provisionar (M12.2)

## Estado

Aceptada por el encargo de M12 (#71). El encargo prohíbe crear recursos, usar
credenciales o ejecutar comandos contra AWS. Diseño en
[arquitectura objetivo](../design/aws-target-architecture.md).

## Problema

El roadmap contempla una práctica temporal en AWS, siempre que pueda garantizarse
coste cero. Si no puede garantizarse, pide documentar el diseño y el límite sin
provisionar. Falta decidir qué arquitectura se desplegaría y cómo se traslada la
semántica operativa ya construida (probes de D037, cola de D036, secretos de D038).

## Alternativas

| Opción de compute | A favor | En contra |
| --- | --- | --- |
| **ECS on Fargate** | Sin nodos; reutiliza imagen y comandos; IAM por tarea; servicios para API/worker y RunTask para migraciones | Health check único (sin readiness); coste por tarea siempre encendida |
| EKS | Reutiliza los manifiestos de M12.1 casi tal cual | ≈73 USD/mes solo de plano de control, más nodos; sobredimensionado para un servicio |
| EC2 + k3s en una instancia | Lo más barato; reutiliza manifiestos | Parches, backups y seguridad del host a cargo propio; un único punto de fallo |
| Lambda | Coste por uso | Worker de larga duración, pool de conexiones y torch/MedCPT encajan mal |

Para la base de datos: **RDS PostgreSQL single-AZ** (pgvector soportado) frente a
Aurora Serverless v2 (mínimo de capacidad facturable siempre encendido y más caro
para esta carga) y frente a PostgreSQL en contenedor (sin backups gestionados).
Para los secretos: **SSM Parameter Store** estándar (sin coste) frente a Secrets
Manager (rotación de pago e innecesaria aquí).

## Decisión

- ECS Fargate (api ×2, worker ×1 y tarea `migrate` previa al despliegue), ALB con
  ACM, RDS `db.t4g.micro`, VPC con dos AZ, subredes privadas y security groups
  encadenados, ECR, SSM SecureString, CloudWatch Logs y alarmas nativas.
- IAM: rol de ejecución limitado a un repositorio ECR, los log groups y los
  parámetros del proyecto. Roles de tarea sin permisos. Despliegue con OIDC de
  GitHub, sin claves de larga duración.
- **El health check del ALB/ECS apunta a `/health`, no a `/ready`.** ECS
  reemplaza los targets no sanos: usar la readiness reintroduciría la tormenta de
  reinicios ante una caída de RDS que D037 evita.
- No provisionar. El coste estimado es de ≈110–125 USD/mes, o ≈75–85 USD/mes sin
  NAT. No hay ninguna configuración útil de coste cero permanente, y los créditos
  o el free tier son temporales.

## Consecuencias

- M12 no deja infraestructura cloud ni gasto, y su cierre cumple la condición de
  la milestone («sin infraestructura cloud activa»).
- No hay evidencia empírica de AWS: los costes son estimaciones de lista que se
  verificarían con la calculadora, y la red y el IAM no se han probado. No debe
  presentarse como experiencia operativa en AWS.
- El diseño expone dos huecos del despliegue cloud frente al local: el ALB no
  limita el tamaño del cuerpo (habría que hacerlo en la app o con WAF) y no
  distingue readiness. Ambos quedan documentados, no implementados.
- El procedimiento de retirada presupone IaC etiquetada. Si alguna vez se
  despliega, se escribe y se revisa la IaC antes de crear nada.
