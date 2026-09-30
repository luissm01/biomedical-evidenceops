# D007 — PostgreSQL local para la primera persistencia duradera

## Status

Accepted.

## Problem

El diccionario por proceso pierde las preguntas al reiniciar y no representa
una dependencia de datos compartida por varias instancias de la aplicación.
Necesitamos persistencia duradera sin depender de servicios de pago.

## Options and decision

SQLite ofrece persistencia transaccional con una puesta en marcha mínima, pero
su ejecución embebida no permite trabajar varios aspectos relevantes de una
base de datos de producción. PostgreSQL introduce un servicio independiente,
conexiones, configuración y una estrategia de testing más exigente.

Se elige PostgreSQL ejecutado localmente. No se utilizará una base de datos
gestionada, una tarjeta de crédito ni un free tier temporal. El desarrollador
prefiere asumir la complejidad local para aprender una arquitectura más
representativa de producción.

## Trade-offs

La aplicación necesitará una instancia local de PostgreSQL y más configuración
que con SQLite. A cambio, trabajaremos límites reales entre procesos,
concurrencia, conexiones y transacciones. Esta decisión también evita una
migración inmediata desde una base embebida, sin autorizar todavía `pgvector`
ni componentes de retrieval de milestones futuros.
