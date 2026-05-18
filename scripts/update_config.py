"""Inyectar dinámicamente URIs de imágenes Docker en config.json."""

import argparse
import json
from pathlib import Path


def update_config(config_path: Path, env: str, sha: str, registry: str) -> None:
    """
    Modifica in-place las URIs de imágenes Docker en el archivo config.json.

    Args:
        config_path: Ruta al archivo config.json.
        env: Ambiente (dev, qa, prod) - reservado para futura extensibilidad.
        sha: SHA del commit para taguear la imagen.
        registry: URL del registry Docker.
    """
    if not config_path.exists():
        msg = f"No se encontró el archivo: {config_path}"
        raise FileNotFoundError(msg)

    with config_path.open("r", encoding="utf-8") as f:
        config = json.load(f)

    name_model = config.get("name_model")
    if not name_model:
        msg = "El campo 'name_model' no está definido en config.json"
        raise ValueError(msg)

    # Formato: {registry}/{name_model}/{step}:sha-{sha}
    # Nota: env se recibe por compatibilidad futura pero no se usa en la URI local
    steps = ["preprocessing", "training", "validation"]
    for step in steps:
        field = f"image_uri_{step}"
        uri = f"{registry}/{name_model}/{step}:sha-{sha}"
        config[field] = uri
        print(f"{field}: {uri}")

    with config_path.open("w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)
    
    print(f"Configuración actualizada exitosamente en {config_path} (env: {env})")


def main() -> None:
    """Punto de entrada principal para el CLI."""
    parser = argparse.ArgumentParser(
        description="Actualiza las URIs de imágenes en config.json para el CI/CD."
    )
    parser.add_argument(
        "--env",
        choices=["dev", "qa", "prod"],
        required=True,
        help="Ambiente de despliegue",
    )
    parser.add_argument(
        "--sha",
        required=True,
        help="SHA del commit para la versión de la imagen",
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Ruta al archivo config.json",
    )
    parser.add_argument(
        "--registry",
        default="localhost:5001",
        help="URL del registry Docker (default: localhost:5001)",
    )

    args = parser.parse_args()

    config_path = Path(args.config)
    update_config(
        config_path=config_path,
        env=args.env,
        sha=args.sha,
        registry=args.registry,
    )


if __name__ == "__main__":
    main()
