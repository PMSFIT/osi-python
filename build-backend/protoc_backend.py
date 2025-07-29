import os
import subprocess
import sys
import re
import glob
import pathlib
from typing import Any

from poetry.core.masonry.api import get_requires_for_build_wheel, get_requires_for_build_sdist, prepare_metadata_for_build_wheel, build_wheel as build_wheel_orig, build_sdist as build_sdist_orig, build_editable, get_requires_for_build_editable, prepare_metadata_for_build_editable

import poetry_dynamic_versioning.patch as patch

from protoc import PROTOC_EXE


# Activate Versioning Plugin
patch.activate()


def _generate_python_files(package_name):
    package_path = pathlib.Path(os.getcwd()) / package_name
    try:
        os.mkdir(package_path)
    except Exception:
        pass

    # configure the version number
    VERSION_MAJOR = None
    VERSION_MINOR = None
    VERSION_PATCH = None
    VERSION_SUFFIX = None
    with open(pathlib.Path("open-simulation-interface")/"VERSION", "rt") as versionin:
        for line in versionin:
            if line.startswith("VERSION_MAJOR"):
                VERSION_MAJOR = int(line.split("=")[1].strip())
            if line.startswith("VERSION_MINOR"):
                VERSION_MINOR = int(line.split("=")[1].strip())
            if line.startswith("VERSION_PATCH"):
                VERSION_PATCH = int(line.split("=")[1].strip())
            if line.startswith("VERSION_SUFFIX"):
                VERSION_SUFFIX = line.split("=")[1].strip()

    # Generate osi_version.proto
    with open("open-simulation-interface/osi_version.proto.in", "rt") as fin:
        with open("open-simulation-interface/osi_version.proto", "wt") as fout:
            for line in fin:
                lineConfigured = line.replace("@VERSION_MAJOR@", str(VERSION_MAJOR))
                lineConfigured = lineConfigured.replace(
                    "@VERSION_MINOR@", str(VERSION_MINOR)
                )
                lineConfigured = lineConfigured.replace(
                    "@VERSION_PATCH@", str(VERSION_PATCH)
                )
                fout.write(lineConfigured)

    # Copy and adjust imports
    pattern = re.compile('^import "osi_')
    for source in glob.glob("open-simulation-interface/*.proto"):
        with open(source) as src_file:
            with open(package_path / pathlib.Path(source).name, "w") as dst_file:
                for line in src_file:
                    dst_file.write(
                        pattern.sub('import "' + package_name + "/osi_", line)
                    )

    # Run protoc
    proto_files = glob.glob(package_name + "/*.proto")
    if not proto_files:
        raise RuntimeError("No .proto files found in the package directory. Aborting build.")
    subprocess.check_call(
        [PROTOC_EXE, "--python_out=.", "--pyi_out=."] + proto_files,
    )

    # Write __init__.py
    with open(package_path / "__init__.py", "wt") as init_file:
        init_file.write(
            f"__version__ = '{VERSION_MAJOR}.{VERSION_MINOR}.{VERSION_PATCH}{VERSION_SUFFIX or ''}'\n"
        )

# Override build actions

def build_wheel(
    wheel_directory: str,
    config_settings: dict[str, Any] | None = None,
    metadata_directory: str | None = None,
) -> str:
    """Builds a wheel, places it in wheel_directory"""
    _generate_python_files("osi3")
    return build_wheel_orig(wheel_directory, config_settings, metadata_directory)

def build_sdist(
    sdist_directory: str, config_settings: dict[str, Any] | None = None
) -> str:
    """Builds an sdist, places it in sdist_directory"""
    _generate_python_files("osi3")
    return build_sdist_orig(sdist_directory, config_settings)

