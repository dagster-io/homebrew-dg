#!/usr/bin/env python3
import os
import shutil
import subprocess
import sys
from typing import Optional

import typer
from rich.console import Console

console = Console()

app = typer.Typer()


DAGSTER_OSS_BRANCH_OPTION = typer.Option(
    None,
    envvar="DAGSTER_OSS_BRANCH",
    help="The OSS git branch that is used to build dagster and other packages.",
)
DG_VERSION_OPTION = typer.Option(
    ...,
    envvar="DG_RELEASE_VERSION",
    help="The version of the dg package to release.",
)


def info(msg):
    console.print(msg, style="blue")


def error(msg):
    console.print(msg, style="red")


@app.command(help="Build dg.pex - invoked by the dg-pex-builder image")
def build_dg_pex(
    dagster_oss_branch: Optional[str] = DAGSTER_OSS_BRANCH_OPTION,
    dg_version: str = DG_VERSION_OPTION,
):
    if dagster_oss_branch:
        info(f"Using dagster@{dagster_oss_branch} for dagster packages")
        dagster_pkg = f"git+https://github.com/dagster-io/dagster.git@{dagster_oss_branch}#egg=dagster&subdirectory=python_modules/dagster"
        dagster_cloud_cli_pkg = f"git+https://github.com/dagster-io/dagster.git@{dagster_oss_branch}#egg=dagster-cloud-cli&subdirectory=python_modules/libraries/dagster-cloud-cli"
        dagster_dg_pkg = f"git+https://github.com/dagster-io/dagster.git@{dagster_oss_branch}#egg=dagster-dg&subdirectory=python_modules/libraries/dagster-dg"
        dagster_pipes_pkg = f"git+https://github.com/dagster-io/dagster.git@{dagster_oss_branch}#egg=dagster-pipes&subdirectory=python_modules/dagster-pipes"
        dagster_shared_pkg = f"git+https://github.com/dagster-io/dagster.git@{dagster_oss_branch}#egg=dagster-shared&subdirectory=python_modules/libraries/dagster-shared"
    else:
        pin_str = f"=={dg_version}" if dg_version else ""
        info("Using PyPI for dagster package")
        dagster_pkg = "dagster"
        dagster_cloud_cli_pkg = "dagster-cloud-cli"
        dagster_dg_pkg = f"dagster-dg{pin_str}"
        dagster_pipes_pkg = "dagster-pipes"
        dagster_shared_pkg = "dagster-shared"

    info("Building generated/dg")
    args = [
        "pex",
        dagster_cloud_cli_pkg,
        dagster_pkg,
        dagster_dg_pkg,
        dagster_pipes_pkg,
        dagster_shared_pkg,
        "--resolver-version=pip-2020-resolver",
        "-c",
        "dg",
        "--venv",
        "--scie",
        "eager",
        "--platform",
        "macosx_11_0_arm64-cp-312-cp312",
        "--platform",
        "macosx_11_0_x86_64-cp-312-cp312",
        "--platform",
        "manylinux2014_x86_64-cp-312-cp312",
        "--scie-name-style",
        "platform-file-suffix",
        "-v",
        "-o",
        "dg",
    ]
    print(f"Running {args}")
    output = subprocess.check_output(
        args,
        shell=False,
        encoding="utf-8",
    )
    print(output)
    shutil.move("dg-macos-aarch64", "generated/dg-macos-aarch64")
    shutil.move("dg-macos-x86_64", "generated/dg-macos-x86_64")
    shutil.move("dg-linux-x86_64", "generated/dg-linux-x86_64")

    info("Built generated dg executables")


@app.command(help="Update dg.pex")
def update_dg_pex(
    dagster_oss_branch: Optional[str] = DAGSTER_OSS_BRANCH_OPTION,
    dg_version: str = DG_VERSION_OPTION,
):
    # Map /generated on the docker image to our local generated folder
    map_folders = {"/generated": os.path.join(os.path.dirname(__file__), "generated")}

    env_args = []
    if dagster_oss_branch:
        env_args.extend(["-e", f"DAGSTER_OSS_BRANCH={dagster_oss_branch}"])

    if dg_version:
        env_args.extend(["-e", f"DG_RELEASE_VERSION={dg_version}"])

    mount_args = []
    for target_folder, source_folder in map_folders.items():
        mount_args.extend(["--mount", f"type=bind,source={source_folder},target={target_folder}"])

    cmd = [
        "docker",
        "build",
        "--progress=plain",
        "-t",
        "dg-pex-builder",
        "--platform=linux/amd64",
        "-f",
        os.path.join(os.path.dirname(__file__), "Dockerfile.dg-pex-builder"),
        os.path.dirname(__file__),
    ]

    subprocess.run(cmd, check=True)

    cmd = [
        "docker",
        "run",
        "--platform=linux/amd64",
        *env_args,
        *mount_args,
        "-t",
        "dg-pex-builder",
    ]
    subprocess.run(cmd, check=True)


def _get_sha(filename: str) -> str:
    return subprocess.check_output(["shasum", "-a", "256", filename]).decode("utf-8").split()[0]


@app.command()
def update_formula_template(
    dg_version: str = DG_VERSION_OPTION,
):
    with open("formula-templates/dg.rb.template") as f:
        template = f.read()
    template = template.replace("{{version}}", dg_version)
    template = template.replace("{{dg_arm_sha}}", _get_sha("generated/dg-macos-aarch64"))
    template = template.replace("{{dg_x64_sha}}", _get_sha("generated/dg-macos-x86_64"))
    template = template.replace("{{dg_linux_sha}}", _get_sha("generated/dg-linux-x86_64"))
    with open("Formula/dg.rb", "w") as f:
        f.write(template)


@app.command()
def push_tag(
    dg_version: str = DG_VERSION_OPTION,
):
    subprocess.run(["git", "add", "."], check=True)

    subprocess.run(["git", "commit", "-m", "Rebuild"], check=True)
    # create a tag
    subprocess.run(["git", "tag", "-a", f"v{dg_version}", "-m", f"v{dg_version}"], check=True)

    subprocess.run(["git", "push", "origin", f"v{dg_version}"], check=True)


@app.command()
def create_github_release(
    dg_version: str = DG_VERSION_OPTION,
):
    # create a release on github from the tag
    subprocess.run(
        ["gh", "release", "create", f"v{dg_version}", "--notes", f"Release {dg_version}"],
        check=True,
    )

    subprocess.run(
        ["gh", "release", "upload", f"v{dg_version}", "generated/dg-macos-aarch64", "--clobber"],
        check=True,
    )
    subprocess.run(
        ["gh", "release", "upload", f"v{dg_version}", "generated/dg-macos-x86_64", "--clobber"],
        check=True,
    )
    subprocess.run(
        ["gh", "release", "upload", f"v{dg_version}", "generated/dg-linux-x86_64", "--clobber"],
        check=True,
    )


@app.command()
def create_rc(
    dagster_oss_branch: Optional[str] = DAGSTER_OSS_BRANCH_OPTION,
    dg_version: str = DG_VERSION_OPTION,
):
    ensure_clean_workdir()
    os.makedirs("generated", exist_ok=True)
    update_dg_pex(dagster_oss_branch, dg_version)
    update_formula_template(dg_version)


def ensure_clean_workdir():
    proc = subprocess.run(["git", "status", "--porcelain"], capture_output=True, check=False)
    if proc.stdout or proc.stderr:
        error("ERROR: Git working directory not clean:")
        error((proc.stdout + proc.stderr).decode("utf-8"))
        sys.exit(1)


if __name__ == "__main__":
    try:
        app()
    except subprocess.CalledProcessError as err:
        error("Subprocess failed")
        error(err.args)
        if err.output:
            error(err.output.decode("utf-8"))
        if err.stderr:
            error(err.stderr.decode("utf-8"))
        raise
