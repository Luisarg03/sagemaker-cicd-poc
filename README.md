# SageMaker CICD PoC with Ministack

Este repositorio contiene una Prueba de Concepto (PoC) para un pipeline de CI/CD de SageMaker diseñado para funcionar localmente utilizando `ministack` (LocalStack + Moto + Containers).

## Requisitos

- Docker y Docker Compose
- Python 3.12+
- `uv` (recomendado) o `pip`

## Estructura del Proyecto

- `model-poc/`: Contiene el código del modelo y el script del pipeline.
  - `training/pipeline.py`: Definición del SageMaker Pipeline.
  - `config.json`: Configuración local del PoC.
- `scripts/`: Utilidades para el despliegue.
  - `deploy_s3.py`: Sube el código y artefactos a S3.
- `docker/`: Dockerfiles para las imágenes de procesamiento y entrenamiento.
- `.github/workflows/`: Definición del flujo de CI/CD.

## Guía de Inicio Rápido

### 1. Levantar el Entorno Local (Ministack)

```bash
docker-compose up -d
```

Esto levantará los servicios necesarios para simular AWS localmente (S3, SageMaker API).

### 2. Configurar el Entorno de Python

```bash
# Crear venv e instalar dependencias
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

O usando `uv`:
```bash
uv sync
```

### 3. Ejecutar el Despliegue Manualmente

Para simular lo que hace el CI/CD:

**A. Subir código a S3:**
```bash
python scripts/deploy_s3.py --endpoint-url http://localhost:4566 --config model-poc/config.json --root model-poc
```

**B. Crear/Actualizar el Pipeline en SageMaker:**
```bash
python model-poc/training/pipeline.py --local --s3-endpoint-url http://localhost:4566 --config model-poc/config.json
```

## Flujo de CI/CD

El archivo `.github/workflows/cicd.yml` define los siguientes jobs:
1. **Quality**: Linting con Ruff.
2. **Build/Push**: Construcción de imágenes Docker (simulado).
3. **Upload S3**: Empaquetado y subida de código a S3 usando `deploy_s3.py`.
4. **Deploy**: Registro (upsert) del pipeline en SageMaker.

---
*Nota: Este proyecto es una PoC y utiliza configuraciones simplificadas para ejecución local.*
