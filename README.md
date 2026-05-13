# SageMaker CI/CD — PoC con Ministack

> **Fase:** Prueba de concepto — validación local del flujo CI/CD completo  
> **Stack:** GitHub Actions · Python 3.12 · Docker · Ministack · SageMaker SDK  
> **Propósito:** Demostrar que el pipeline de CI/CD funciona de punta a punta sin necesidad de una cuenta AWS real

---

## ¿Qué hace este repositorio?

Implementa un flujo CI/CD para modelos ML sobre SageMaker con la siguiente convención: **una branch por modelo**. Cuando un Data Scientist hace push a su rama, GitHub Actions ejecuta automáticamente lint, build de imágenes Docker, upload a S3 y registro del pipeline en SageMaker — todo simulado localmente con Ministack.

El diseño está dividido en dos capas:

| Documento | Descripción |
|-----------|-------------|
| [`docs/cicd-design.md`](docs/cicd-design.md) | Diseño objetivo para producción — AWS real, OIDC, ECR, seguridad |
| [`docs/cicd-poc.md`](docs/cicd-poc.md) | Esta PoC — Ministack local, sin cuenta AWS |

---

## Estructura del repositorio

```
sagemaker-cicd-poc/
├── .github/
│   └── workflows/
│       └── cicd.yml              ← workflow único para todas las ramas model-*
├── docs/
│   ├── cicd-design.md            ← diseño objetivo (producción)
│   ├── cicd-poc.md               ← documentación de esta PoC
│   └── diags/                    ← diagramas D2 + SVG
├── scripts/
│   └── deploy_s3.py              ← sube model-X/ a S3 como tarballs por step
├── {model-name}/                 ← template base para nuevos modelos
│   ├── config.json
│   └── training/
│       ├── pipeline.py
│       └── artifacts/
│           ├── preprocessing/    ← Dockerfile + main.py + entrypoint.sh
│           ├── training/
│           └── validation/
├── model-1/                      ← branch model-1
├── model-2/                      ← branch model-2
├── model-3/                      ← branch model-3
├── docker-compose.yml            ← levanta Ministack localmente
└── pyproject.toml
```

---

## Flujo CI/CD

Cada push a una rama `model-*` dispara cuatro jobs secuenciales:

```
push → model-X
    └─→ Job 1 · quality        ruff check
            └─→ Job 2 · build  docker build ×3 (preprocessing, training, validation)
                    └─→ Job 3 · upload-s3    deploy_s3.py → Ministack :4566
                            └─→ Job 4 · deploy  pipeline.upsert() → LocalPipelineSession
```

> En el diseño objetivo, Job 2 y Job 3 corren **en paralelo**. En la PoC corren secuencialmente para simplificar.

---

## Requisitos

- **Docker** — para Ministack y el build de imágenes
- **Python 3.12+**
- **uv** (recomendado) o pip

---

## Inicio rápido

### 1 · Levantar Ministack

```bash
docker compose up -d
```

Ministack expone una API compatible con AWS S3 y SageMaker en `localhost:4566`. Esperar a que el healthcheck pase antes de continuar.

### 2 · Instalar dependencias Python

```bash
uv sync
```

O con pip:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

### 3 · Simular el CI/CD manualmente

```bash
# Upload de artefactos a S3 local
python scripts/deploy_s3.py \
  --endpoint-url http://localhost:4566 \
  --config model-1/config.json \
  --root model-1

# Registro del pipeline en SageMaker local
python model-1/training/pipeline.py \
  --local \
  --s3-endpoint-url http://localhost:4566 \
  --config model-1/config.json
```

---

## Agregar un nuevo modelo

```bash
# 1. Crear branch desde el template
git checkout -b model-N template

# 2. Renombrar el directorio placeholder
git mv '{model-name}' model-N

# 3. Editar la configuración del modelo
#    → model-N/config.json

# 4. Implementar la lógica de cada step
#    → model-N/training/artifacts/{preprocessing,training,validation}/main.py

# 5. Push — el CI/CD corre automáticamente
git push origin model-N
```

No hay que modificar el workflow ni agregar configuración adicional.

---

## Documentación

- [Diseño objetivo — producción](docs/cicd-design.md)
- [PoC local — esta implementación](docs/cicd-poc.md)
