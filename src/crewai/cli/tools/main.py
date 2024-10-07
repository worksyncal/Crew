import base64
import os
import subprocess
import tempfile
from pathlib import Path

import click
from rich.console import Console

from crewai.cli import git
from crewai.cli.command import BaseCommand, PlusAPIMixin
from crewai.cli.utils import (
    get_project_description,
    get_project_name,
    get_project_version,
    tree_copy,
    tree_find_and_replace,
)

console = Console()


class ToolCommand(BaseCommand, PlusAPIMixin):
    """
    A class to handle tool repository related operations for CrewAI projects.
    """

    def __init__(self):
        BaseCommand.__init__(self)
        PlusAPIMixin.__init__(self, telemetry=self._telemetry)

    def create(self, handle: str):
        self._ensure_not_in_project()

        folder_name = handle.replace(" ", "_").replace("-", "_").lower()
        class_name = handle.replace("_", " ").replace("-", " ").title().replace(" ", "")

        project_root = Path(folder_name)
        if project_root.exists():
            click.secho(f"Folder {folder_name} already exists.", fg="red")
            raise SystemExit
        else:
            os.makedirs(project_root)

        click.secho(f"Creating custom tool {folder_name}...", fg="green", bold=True)

        template_dir = Path(__file__).parent.parent / "templates" / "tool"
        tree_copy(template_dir, project_root)
        tree_find_and_replace(project_root, "{{folder_name}}", folder_name)
        tree_find_and_replace(project_root, "{{class_name}}", class_name)

        old_directory = os.getcwd()
        os.chdir(project_root)
        try:
            self.login()
            subprocess.run(["git", "init"], check=True)
            console.print(
                f"[green]Created custom tool [bold]{folder_name}[/bold]. Run [bold]cd {project_root}[/bold] to start working.[/green]"
            )
        finally:
            os.chdir(old_directory)

    def publish(self, is_public: bool):
        if not git.Repository().is_synced():
            console.print(
                "[bold red]Failed to publish tool.[/bold red]\n"
                "Local changes need to be resolved before publishing. Please do the following:\n"
                "* [bold]Commit[/bold] your changes.\n"
                "* [bold]Push[/bold] to sync with the remote.\n"
                "* [bold]Pull[/bold] the latest changes from the remote.\n"
                "\nOnce your repository is up-to-date, retry publishing the tool."
            )
            raise SystemExit()

        project_name = get_project_name(require=True)
        assert isinstance(project_name, str)

        project_version = get_project_version(require=True)
        assert isinstance(project_version, str)

        project_description = get_project_description(require=False)
        encoded_tarball = None

        with tempfile.TemporaryDirectory() as temp_build_dir:
            subprocess.run(
                ["uv", "build", "-f", "sdist", "--output", temp_build_dir],
                check=True,
                capture_output=False,
            )

            tarball_filename = next(
                (f for f in os.listdir(temp_build_dir) if f.endswith(".tar.gz")), None
            )
            if not tarball_filename:
                console.print(
                    "Project build failed. Please ensure that the command `poetry build -f sdist` completes successfully.",
                    style="bold red",
                )
                raise SystemExit

            tarball_path = os.path.join(temp_build_dir, tarball_filename)
            with open(tarball_path, "rb") as file:
                tarball_contents = file.read()

            encoded_tarball = base64.b64encode(tarball_contents).decode("utf-8")

        publish_response = self.plus_api_client.publish_tool(
            handle=project_name,
            is_public=is_public,
            version=project_version,
            description=project_description,
            encoded_file=f"data:application/x-gzip;base64,{encoded_tarball}",
        )

        self._validate_response(publish_response)

        published_handle = publish_response.json()["handle"]
        console.print(
            f"Succesfully published {published_handle} ({project_version}).\nInstall it in other projects with crewai tool install {published_handle}",
            style="bold green",
        )

    def install(self, handle: str):
        get_response = self.plus_api_client.get_tool(handle)

        if get_response.status_code == 404:
            console.print(
                "No tool found with this name. Please ensure the tool was published and you have access to it.",
                style="bold red",
            )
            raise SystemExit
        elif get_response.status_code != 200:
            console.print(
                "Failed to get tool details. Please try again later.", style="bold red"
            )
            raise SystemExit

        self._add_package(get_response.json())

        console.print(f"Succesfully installed {handle}", style="bold green")

    def login(self):
        login_response = self.plus_api_client.login_to_tool_repository()

        if login_response.status_code != 200:
            console.print(
                "Failed to authenticate to the tool repository. Make sure you have the access to tools.",
                style="bold red",
            )
            raise SystemExit

        login_response_json = login_response.json()
        for repository in login_response_json["repositories"]:
            self._add_repository_to_poetry(
                repository, login_response_json["credential"]
            )

        console.print(
            "Succesfully authenticated to the tool repository.", style="bold green"
        )

    def _add_repository_to_poetry(self, repository, credentials):
        repository_handle = f"crewai-{repository['handle']}"

        add_repository_command = [
            "uv",
            "source",
            "add",
            "--priority=explicit",
            repository_handle,
            repository["url"],
        ]
        add_repository_result = subprocess.run(
            add_repository_command, text=True, check=True
        )

        if add_repository_result.stderr:
            click.echo(add_repository_result.stderr, err=True)
            raise SystemExit

        add_repository_credentials_command = [
            "uv",
            "config",
            f"http-basic.{repository_handle}",
            credentials["username"],
            credentials["password"],
        ]
        add_repository_credentials_result = subprocess.run(
            add_repository_credentials_command,
            capture_output=False,
            text=True,
            check=True,
        )

        if add_repository_credentials_result.stderr:
            click.echo(add_repository_credentials_result.stderr, err=True)
            raise SystemExit

    def _add_package(self, tool_details):
        tool_handle = tool_details["handle"]
        repository_handle = tool_details["repository"]["handle"]
        pypi_index_handle = f"crewai-{repository_handle}"

        add_package_command = [
            "uv",
            "add",
            "--source",
            pypi_index_handle,
            tool_handle,
        ]
        add_package_result = subprocess.run(
            add_package_command, capture_output=False, text=True, check=True
        )

        if add_package_result.stderr:
            click.echo(add_package_result.stderr, err=True)
            raise SystemExit

    def _ensure_not_in_project(self):
        if os.path.isfile("./pyproject.toml"):
            console.print(
                "[bold red]Oops! It looks like you're inside a project.[/bold red]"
            )
            console.print(
                "You can't create a new tool while inside an existing project."
            )
            console.print(
                "[bold yellow]Tip:[/bold yellow] Navigate to a different directory and try again."
            )
            raise SystemExit
