# Brainwash is a software for analysing electrophysiological field recordings
Brainwash is developed for field-recordings in CA1, but also works in DG and SLM.
The program attempts to find events, such as fEPSP and fvolley amplitudes and slopes.
It visualises the data, and provides tools for correcting these events.
Output is stored as .csv-files for compatibility.

## Contact
Mats Andersson (mats.olof.andersson@gu.se). We're happy to receive feedback and suggestions, or to discuss collaborations.

# Installation
Provided files in "release"
* Linux - Appimage, tested for ubuntu compatibility
* Windows - installer

## Dev environment
### Suggested
- Podman 4.6.2 (use --format=docker as some sh scipt in setup did not work with podman format)
- Python 3.12
- VS Code with Dev Containers extension

### Setup
- Unmask Podman socket: `systemctl --user unmask podman.socket`.
- Enable socket: `systemctl --user enable --now podman.socket`.
- Set `dev.containers.dockerPath` to `podman`.
- Build Dev Container: `./build-devcontainer.sh`.

### vscode
The chosen container has some shell commands. Therefore, podman has to build the image with format=docker. The only way I got vscode to respect that was to export the env variable BUILDAH_FORMAT=docker. It could be aither in .bashrc, or as I didn't want it global, but only in this project. There is now a .env file setting this in repo.

#### obsolete, remove if .env for podman docker format always works
There is now a podman_build_docker.sh in .devcontainer that wraps the podman command. Project settings to use that wrapper:
.vscode/settings.json:
{
  "dev.containers.dockerPath": "${workspaceFolder}/.devcontainer/podman_build_docker.sh",
  "dev.containers.dockerComposePath": "podman-compose"
}

## Build: github
There is automated workflows to build on github with ubuntu 22.04 and [windows soon]

## Build: manual distribution builds
se also specific build document in docs.
Build from src folder [SIC], this is needed as cxfreeze does not handle our repo structure gracefully. When it does, it should be from repo root.

### Linux AppImage
./build-appimage.sh

### Windows
> python setup.py build_exe --silent-level 2
Then zip the folder and distribute.
