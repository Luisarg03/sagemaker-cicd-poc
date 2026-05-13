# SageMaker CI/CD — PoC con Ministack

> **Fase:** Prueba de concepto — validación local del flujo CI/CD completo  
> **Stack:** GitHub Actions · Python 3.12 · Docker · Ministack · SageMaker SDK  
> **Propósito:** Demostrar que el pipeline de CI/CD funciona de punta a punta sin necesidad de una cuenta AWS real

---

## ¿Qué hace este repositorio?

Implementa un flujo CI/CD para modelos ML sobre SageMaker con la convención **una branch por modelo**. Cuando se hace push a una rama `model-*`, GitHub Actions ejecuta automáticamente:

1. **Lint** del código Python con `ruff`
2. **Build** de las 3 imágenes Docker (preprocessing, training, validation)
3. **Upload** de artefactos y código a S3 (Ministack local)
4. **Registro** del pipeline en SageMaker (`pipeline.upsert()`)

Todo corre en GitHub Actions sin necesidad de cuenta AWS real — Ministack simula S3 y SageMaker en el runner.

| Documento | Descripción |
|-----------|-------------|
| [`docs/cicd-design.md`](docs/cicd-design.md) | Diseño objetivo para producción — AWS real, OIDC, ECR, seguridad |
| [`docs/cicd-poc.md`](docs/cicd-poc.md) | Esta PoC — Ministack local, sin cuenta AWS |
| [`docs/cicd-tools-reference.md`](docs/cicd-tools-reference.md) | Referencia de todas las herramientas del stack |

---

## Estructura del repositorio

```
sagemaker-cicd-poc/
├── .github/
│   └── workflows/
│       └── cicd.yml                  ← workflow único, se dispara en cualquier rama model-*
├── docs/                             ← documentación y diagramas
├── scripts/
│   └── deploy_s3.py                  ← sube los artefactos del modelo a S3
├── {model-name}/                     ← template — copiar para crear un nuevo modelo
│   ├── config.json                   ← ⚠️ completar antes del primer push
│   └── training/
│       ├── pipeline.py               ← define el grafo del SageMaker Pipeline
│       └── artifacts/
│           ├── preprocessing/        ← Dockerfile + main.py + entrypoint.sh
│           ├── training/
│           └── validation/
├── model-1/                          ← ejemplo funcional
├── docker-compose.yml                ← levanta Ministack localmente (opcional)
└── pyproject.toml
```

---

## Flujo CI/CD

Cada push a una rama `model-*` dispara estos jobs en secuencia:

```
push → model-X
    └─→ Job 1 · quality        ruff check .
            └─→ Job 2 · build-push   docker build ×3 (preprocessing, training, validation)
                    └─→ Job 3 · upload-s3   deploy_s3.py → Ministack S3
                            └─→ Job 4 · deploy-pipeline   pipeline.upsert() → Ministack SageMaker
```

---

## Agregar un nuevo modelo (paso a paso)

### 1 · Crear la branch

```bash
git checkout template
git checkout -b model-N
```

> Partir siempre desde `template`, no desde `main` ni otra rama de modelo.

### 2 · Copiar el directorio template

```bash
cp -r '{model-name}' model-N
git add model-N/
```

> El directorio se llama literalmente `{model-name}` con llaves — es el template base.

### 3 · Completar `config.json`

Editar `model-N/config.json` reemplazando **todos** los placeholders:

```json
{
    "account_id": "000000000000",
    "region": "us-east-1",
    "name_model": "model-N",
    "team": "nombre-del-equipo",
    "cc": "centro-de-costo",
    "s3_bucket": "interbank-sagemaker-poc-bucket",
    "s3_prefix": "model_pipelines/model-N",
    "image_uri_preprocessing": "000000000000.dkr.ecr.us-east-1.amazonaws.com/model-N:preprocessing",
    "image_uri_training":       "000000000000.dkr.ecr.us-east-1.amazonaws.com/model-N:training",
    "image_uri_validation":     "000000000000.dkr.ecr.us-east-1.amazonaws.com/model-N:validation",
    "role_arn": "arn:aws:iam::000000000000:role/SageMakerExecutionRole"
}
```

> ⚠️ `s3_bucket` **debe ser** `interbank-sagemaker-poc-bucket`. Cualquier otro valor rompe el job `upload-s3`.

### 4 · Implementar la lógica de cada step

Editar los tres `main.py` con la lógica real del modelo:

```
model-N/training/artifacts/preprocessing/main.py   ← carga datos, genera train.csv / val.csv
model-N/training/artifacts/training/main.py         ← entrena el modelo
model-N/training/artifacts/validation/main.py       ← evalúa métricas
```

Los `Dockerfile` y `entrypoint.sh` ya están listos — solo modificar `main.py`.

### 5 · Push

```bash
git add .
git commit -m "feat: add model-N"
git push origin model-N
```

El CI/CD se dispara automáticamente. Verificar en la pestaña **Actions** de GitHub que los 4 jobs pasen en verde.

---

## Ejecución local (opcional)

Para probar sin hacer push:

```bash
# 1. Levantar Ministack
docker compose up -d

# 2. Instalar dependencias
uv sync
# o: python -m venv .venv && source .venv/bin/activate && pip install -e .

# 3. Crear el bucket
aws s3 mb s3://interbank-sagemaker-poc-bucket --endpoint-url http://localhost:4566

# 4. Subir artefactos a S3
python scripts/deploy_s3.py \
  --config model-N/config.json \
  --root model-N \
  --endpoint-url http://localhost:4566

# 5. Registrar el pipeline
python model-N/training/pipeline.py \
  --local \
  --config model-N/config.json \
  --s3-endpoint-url http://localhost:4566 \
  --upsert-only
```

---

## Troubleshooting

| Error | Causa | Solución |
|-------|-------|----------|
| `Invalid bucket name "{s3-bucket}"` | `config.json` tiene el placeholder sin reemplazar | Poner `"s3_bucket": "interbank-sagemaker-poc-bucket"` |
| `No such file or directory: model-N/...` | El directorio del modelo no existe en la branch | Verificar que se copió el template y se hizo `git add` |
| `ruff check` falla (Job 1) | Errores de lint en el código Python | Correr `ruff check .` localmente antes del push |
| `docker build` falla (Job 2) | Error en algún `Dockerfile` | Correr `docker build` localmente para ver el error completo |

---

## Documentación

- [Diseño objetivo — producción](docs/cicd-design.md)
- [PoC local — esta implementación](docs/cicd-poc.md)
- [Referencia de herramientas CI/CD](docs/cicd-tools-reference.md)
