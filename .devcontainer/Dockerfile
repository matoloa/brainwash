FROM mcr.microsoft.com/devcontainers/python:3.12-bookworm
RUN apt-get update && apt-get install -y patchelf squashfs-tools wget
RUN wget https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage -O /usr/local/bin/appimagetool \
    && chmod +x /usr/local/bin/appimagetool
USER vscode
WORKDIR /workspaces