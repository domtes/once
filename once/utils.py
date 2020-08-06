import os
import sys

import hashlib
import logging
import shutil
import subprocess
import zipfile

from typing import Dict, List, Union
from aws_cdk import aws_lambda as _lambda


class MissingPrerequisiteCommand(Exception):
    '''A required system command is missing'''


def add_folder_to_zip(zip_obj: zipfile.ZipFile, folder: str, ignore_names: List[str] = [], ignore_dotfiles: bool = True):
    for root, dirs, files in os.walk(folder):
        if ignore_dotfiles:
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            files[:] = [f for f in files if not f.startswith('.')]

        dirs[:] = [d for d in dirs if d not in ignore_names]
        files[:] = [f for f in files if f not in ignore_names]

        logging.debug(f'FILES: {files}, DIRS: {dirs}')

        if root == folder:
            archive_folder_name = ''
        else:
            archive_folder_name = os.path.relpath(root, folder)
            zip_obj.write(root, arcname=archive_folder_name)

        for filename in files:
            f = os.path.join(root, filename)
            d = os.path.join(archive_folder_name, filename)
            zip_obj.write(f, arcname=d)


def execute_shell_command(command: Union[str, List[str]],
                          env: Union[Dict, None] = None) -> str:
    if isinstance(command, list):
        command = ' '.join(command)

    logging.debug(f'Executing command: {command}')

    completed_process = subprocess.run(command,
        env=env,
        shell=True,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)

    logging.debug(completed_process)
    return completed_process.stdout.strip().decode('utf-8')


def locate_command(command: str) -> str:
    path = execute_shell_command(['which', command])
    if path is None:
        raise MissingPrerequisiteCommand(f'Unable to find "{command}"')
    return path


def make_python_zip_bundle(input_path: str,
    python_version: str = '3.7',
    build_folder: str = '.build',
    requirements_file: str = 'requirements.txt',
    output_bundle_name: str = 'bundle.zip') -> _lambda.AssetCode:
    '''
    Builds an lambda AssetCode bundling python dependencies along with the code.
    The bundle is built using docker and the target lambda runtime image.
    '''

    build_path = os.path.abspath(os.path.join(input_path, build_folder))
    asset_path = os.path.join(build_path, output_bundle_name)

    # checks if it's required to build a new zip file
    if not os.path.exists(asset_path) or os.path.getmtime(asset_path) < get_folder_latest_mtime(input_path):
        docker = locate_command('docker')
        lambda_runtime_docker_image = f'lambci/lambda:build-python{python_version}'

        # cleans the target folder
        logging.debug(f'Cleaning folder: {build_path}')
        shutil.rmtree(build_path, ignore_errors=True)

        # builds requirements using target runtime
        build_log = execute_shell_command(command=[
            docker, 'run', '--rm',
            '-v', f'{input_path}:/app',
            '-w', '/app',
            '-u', '$(id -u):$(id -g)',
            lambda_runtime_docker_image,
                'pip', 'install',
                '-r', requirements_file,
                '-t', build_folder])

        logging.info(build_log)

        # creates the zip archive
        logging.debug(f'Deleting file: {asset_path}')
        shutil.rmtree(asset_path, ignore_errors=True)

        logging.debug(f'Creating bundle: {asset_path}')
        with zipfile.ZipFile(asset_path, 'w', zipfile.ZIP_DEFLATED) as zip_obj:
            add_folder_to_zip(zip_obj, input_path, ignore_names=[output_bundle_name, '__pycache__'])
            add_folder_to_zip(zip_obj, build_path, ignore_names=[output_bundle_name, '__pycache__'], ignore_dotfiles=False)

        logging.info(f'Lambda bundle created at {asset_path}')

    source_hash = get_folder_checksum(input_path)
    logging.debug(f'Source folder hash {input_path} -> {source_hash}')
    return _lambda.AssetCode.from_asset(asset_path, source_hash=source_hash)


def get_folder_checksum(path: str, ignore_dotfiles: bool = True,
    chunk_size: int = 4096,
    digest_method: hashlib._hashlib.HASH = hashlib.md5) -> str:
    def _hash_file(filename: str) -> bytes:
        with open(filename, mode='rb', buffering=0) as fp:
            hash_func = digest_method()
            buffer = fp.read(chunk_size)
            while len(buffer) > 0:
                hash_func.update(buffer)
                buffer = fp.read(chunk_size)
        return hash_func.digest()

    folder_hash = b''
    for root, dirs, files in os.walk(path):
        files = [f for f in files if not f.startswith('.')]
        dirs[:] = [d for d in dirs if not d.startswith('.')]

        for file_name in sorted(files):
            file_path = os.path.join(root, file_name)
            file_hash = _hash_file(file_path)
            folder_hash += file_hash

    return digest_method(folder_hash).hexdigest()


def get_folder_latest_mtime(path: str, ignore_dotfiles: bool = True) -> float:
    latest_mtime = None
    for root, dirs, files in os.walk(path):
        if ignore_dotfiles:
            files = [f for f in files if not f.startswith('.')]
            dirs[:] = [d for d in dirs if not d.startswith('.')]

        for file_name in files:
            file_path = os.path.join(root, file_name)
            file_mtime = os.path.getmtime(file_path)
            if latest_mtime is None or file_mtime > latest_mtime:
                latest_mtime = file_mtime

    return latest_mtime
