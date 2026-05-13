# Referencia de Herramientas CI/CD

> Descripción de cada herramienta mencionada en `cicd-design.md`.

---

## Plataforma CI/CD

### GitHub Actions
Plataforma de automatización nativa de GitHub. Los workflows se definen en YAML dentro de `.github/workflows/` y se disparan por eventos (push, PR, cron, manual). Provee runners administrados (Linux/Windows/macOS) y un marketplace de actions reutilizables. En este proyecto orquesta los 4 jobs: quality → build → upload → deploy.

---

## Auth AWS

### `aws-actions/configure-aws-credentials@v6`
Action oficial de AWS para autenticar el runner con la cuenta AWS. Soporta OIDC (recomendado): GitHub emite un JWT de corta duración que AWS valida vía `AssumeRoleWithWebIdentity`, eliminando la necesidad de guardar Access Keys como secrets. Exporta `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` y `AWS_SESSION_TOKEN` al entorno del job.

**Requisitos:** permiso `id-token: write` en el job + IAM Identity Provider configurado en la cuenta AWS con trust a `token.actions.githubusercontent.com`.

---

## Docker

### `docker/setup-buildx-action@v4`
Inicializa un builder Docker Buildx (basado en BuildKit) en el runner. Prerequisito obligatorio para usar caché avanzada de capas y builds multi-arquitectura. Sin este paso, `build-push-action` cae al builder legacy sin soporte de cache exports.

### `docker/build-push-action@v7`
Construye imágenes Docker y las pushea a un registry (ECR en este caso). Soporta:
- **Matrix builds**: construir preprocessing/training/validation en paralelo.
- **Cache por registry**: `cache-from`/`cache-to` apuntan a tags en ECR para reutilizar capas entre runs.
- **Doble tag**: `:step-SHA` (inmutable, trazabilidad) + `:step` (mutable, referenciado por `pipeline.py`).

> `image-manifest=true` y `oci-mediatypes=true` son requeridos para cache en ECR.

### `actions/checkout@v4`
Clona el repositorio en `$GITHUB_WORKSPACE` al inicio de cada job. Por defecto hace shallow clone (depth=1). Usar `fetch-depth: 0` cuando se necesita historial completo (ej: SonarCloud).

---

## Infraestructura AWS

### AWS ECR (Elastic Container Registry)
Registry de imágenes Docker administrado por AWS. Integrado nativamente con IAM y SageMaker. Puntos clave:
- **Tag mutability**: configurable por repo (`MUTABLE` / `IMMUTABLE`). Para convivir tags inmutables (`:step-SHA`) con mutables (`:step`) usar `IMMUTABLE_WITH_EXCLUSION` + filtro de exclusión.
- **Lifecycle policies**: reglas para expirar imágenes viejas automáticamente (ej: borrar tags no referenciados >30 días).
- **`CreateRepository` no es idempotente**: lanza `RepositoryAlreadyExistsException` si el repo ya existe — manejar con `try/except`.

### AWS S3
Almacenamiento de objetos para artefactos del pipeline (código, datasets, modelos). El CI/CD sube `pipeline.py` y los `artifacts/` a una ruta estática que `pipeline.py` referencia en tiempo de ejecución. Usar prefijos bien definidos por modelo y step para evitar colisiones entre branches.

### AWS OIDC (para GitHub Actions)
Mecanismo de identidad federada entre GitHub y AWS IAM. Evita credenciales de larga duración. El IAM Role puede configurar la trust policy para restringir qué repo/branch puede asumir el rol. **Gotcha**: si el job dura más de 1h (ej: esperar un Training Job), hay que aumentar `role-duration-seconds`.

---

## SageMaker

### AWS SageMaker Pipelines
Servicio de orquestación de workflows ML. El CI/CD registra (o actualiza) el pipeline via `pipeline.upsert(role_arn)` — operación idempotente: crea si no existe, actualiza si ya existe. El equipo lo ejecuta manualmente desde SageMaker Studio. Steps disponibles: `ProcessingStep`, `TrainingStep`, `ConditionStep`, `ModelStep`.

---

## Calidad de código

### SonarCloud (`SonarSource/sonarqube-scan-action@v7`)
Análisis estático de calidad de código en la nube. Detecta code smells, duplicación, deuda técnica y vulnerabilidades comunes (OWASP Top 10) en 30+ lenguajes. Reporta en dashboard y como comentarios en PR. **No bloquea el pipeline por defecto** — es informativo. Requiere `fetch-depth: 0` en checkout para análisis de blame.

> `sonarcloud-github-action` está deprecada — usar `sonarqube-scan-action@v7`.

---

## Seguridad (SAST: Static Application Security Testing)

### Fluid Attacks (`fluidattacks/sast-action@v1`)
SAST de la empresa Fluid Attacks. Genera output en formato SARIF. Configurado con `strict: true` en `.sast.yaml` **bloquea el pipeline** en hallazgos HIGH/CRITICAL. Mapea a estándares OWASP, HIPAA, PCI. Es el único gate de seguridad que bloquea en este diseño.

### Semgrep (container `semgrep/semgrep` + `semgrep ci`)
SAST liviano y rápido basado en patrones. Corre offline vía container Docker. Usa regla packs de la comunidad: `p/security-audit` (vulnerabilidades genéricas), `p/python`, `p/owasp-top-ten`. Output en SARIF. Modo informativo en este diseño.

> `semgrep/semgrep-action` está deprecada — usar el container directamente.

### Bandit (`PyCQA/bandit-action@v1`)
Linter de seguridad **específico para Python**. Analiza el AST del código buscando patrones inseguros: `subprocess` con `shell=True`, criptografía débil (MD5), passwords hardcodeados, `yaml.load()` sin `Loader`. Rápido y liviano. Output en SARIF. Modo informativo en este diseño.

---

## Scan de imágenes Docker

### ECR Enhanced Scanning (Amazon Inspector v2)
Escaneo continuo y automático de vulnerabilidades en imágenes almacenadas en ECR. Analiza paquetes OS y dependencias de lenguaje. Los hallazgos se envían a AWS Security Hub y pueden disparar eventos en EventBridge. **Opción nativa AWS** — sin costo adicional de licencia.

### JFrog Xray
Herramienta comercial de SCA (Software Composition Analysis) integrada con JFrog Artifactory. Escanea imágenes, paquetes npm/PyPI/Maven. A diferencia de Inspector, puede **bloquear activamente el pull** de artefactos vulnerables. Relevante si la organización ya usa Artifactory como registry central.

---

## Formato de reporte

### SARIF (Static Analysis Results Interchange Format)
Estándar JSON (OASIS) para output de herramientas de análisis estático. GitHub lo ingiere nativamente para poblar la pestaña **Security → Code scanning alerts** y agregar anotaciones inline en PRs. Fluid Attacks, Semgrep y Bandit generan SARIF. Se sube con `github/codeql-action/upload-sarif@v3`.

> En repos **privados** requiere GitHub Advanced Security (GHAS). En repos públicos es gratuito.
