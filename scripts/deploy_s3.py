''' Desplegar codigo del modelo a S3 (compatible con ministack). '''

import io
import os
import json
import tarfile
import subprocess
import argparse
from typing import Any
from pathlib import Path

import boto3

TARBALL_NAME = 'sourcedir.tar.gz'
ARTIFACTS_DIR_NAME = 'artifacts'

def get_included_files(root: Path) -> set[Path] | None:
    '''
    Devuelve el conjunto de archivos bajo root que git no considera ignorados.
    '''
    try:
        completed = subprocess.run(
            ['git', '-C', str(root), 'rev-parse', '--show-toplevel'],
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    repo_root = Path(completed.stdout.strip())

    output = subprocess.check_output(
        [
            'git',
            '-C',
            str(repo_root),
            'ls-files',
            '-z',
            '--cached',
            '--others',
            '--exclude-standard',
        ],
    )

    root_resolved = root.resolve()
    files: set[Path] = set()
    for entry in output.split(b'\x00'):
        if not entry:
            continue
        absolute = (repo_root / entry.decode('utf-8')).resolve()
        try:
            absolute.relative_to(root_resolved)
        except ValueError:
            continue
        files.add(absolute)
    return files

def is_included(path: Path, included: set[Path] | None) -> bool:
    if included is None:
        return True
    return path.resolve() in included

def upload_file(s3_client: Any, local_path: Path, bucket: str, key: str) -> None:
    print(f'Subiendo archivo: s3://{bucket}/{key}')
    s3_client.upload_file(str(local_path), bucket, key)

def upload_directory_as_tarball(s3_client: Any, local_dir: Path, bucket: str, key: str, included: set[Path] | None) -> None:
    local_dir_resolved = local_dir.resolve()

    def tar_filter(tarinfo: tarfile.TarInfo) -> tarfile.TarInfo | None:
        source = local_dir_resolved / tarinfo.name
        if source.is_file() and not is_included(source, included):
            return None
        return tarinfo

    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w:gz') as tar:
        for item in sorted(local_dir.iterdir()):
            tar.add(item, arcname=item.name, filter=tar_filter)
    buffer.seek(0)

    print(f'Subiendo tarball: s3://{bucket}/{key}')
    s3_client.upload_fileobj(buffer, bucket, key)

def deploy(s3_client: Any, root: Path, bucket: str, prefix: str, included: set[Path] | None) -> None:
    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        rel_current = current.relative_to(root)
        dirnames.sort()

        for filename in sorted(filenames):
            local_path = current / filename
            if not is_included(local_path, included):
                continue
            rel_path = rel_current / filename
            key = f'{prefix}/{rel_path.as_posix()}'
            upload_file(s3_client, local_path, bucket, key)

        if current.name == ARTIFACTS_DIR_NAME:
            for subdir in sorted(dirnames):
                rel_tar = rel_current / subdir / TARBALL_NAME
                key = f'{prefix}/{rel_tar.as_posix()}'
                upload_directory_as_tarball(current / subdir, s3_client, bucket, key, included)

def main() -> None:
    parser = argparse.ArgumentParser(description='Deploy model code to S3.')
    parser.add_argument('--endpoint-url', help='S3 endpoint URL (e.g., http://localhost:4566 for ministack)')
    parser.add_argument('--profile', help='AWS profile name')
    parser.add_argument('--config', default='model-poc/config.json', help='Path to config.json')
    parser.add_argument('--root', default='model-poc', help='Root directory to deploy')
    args = parser.parse_args()

    session_kwargs = {}
    if args.profile:
        session_kwargs['profile_name'] = args.profile
    
    session = boto3.Session(**session_kwargs)
    
    client_kwargs = {}
    if args.endpoint_url:
        client_kwargs['endpoint_url'] = args.endpoint_url
    
    s3_client = session.client('s3', **client_kwargs)

    config_path = Path(args.config)
    with config_path.open('r', encoding='utf-8') as file:
        config = json.load(file)

    bucket = config['s3_bucket']
    prefix = f'{config["s3_prefix"]}/{config["name_model"]}/code'
    
    root_dir = Path(args.root).resolve()

    included = get_included_files(root_dir)
    if included is None:
        print('No se detectó repositorio git, se subirán todos los archivos.')
    else:
        print(f'Repositorio git detectado, archivos no ignorados: {len(included)}')

    deploy(s3_client, root_dir, bucket, prefix, included)

if __name__ == '__main__':
    main()
