FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y \
    software-properties-common \
    && add-apt-repository ppa:deadsnakes/ppa \
    && apt-get update \
    && apt-get install -y \
    patchelf squashfs-tools wget xvfb libx11-dev libgl1-mesa-glx libgl1 sudo git \
    xvfb \
    x11-apps \
    libxkbcommon-x11-0 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-randr0 \
    libxcb-render-util0 \
    libxcb-xinerama0 \
    libxcb-xfixes0 \
    libxcb-xkb1 \
    libxcb-cursor0 \
    libxcb-shm0 \
    libxcb-sync1 \
    qtbase5-dev \
    qt5-qmake \
    qtbase5-dev-tools \
    libqt5gui5 \
    libqt5widgets5 \
    libqt5x11extras5 \
    mesa-common-dev \
    libgl1-mesa-dri \
    libglx-mesa0 \
    python3.12 \
    python3.12-dev \
    python3.12-venv \
    python3-distutils \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*
# Set python3.12 as the default python3
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1

# Upgrade pip and install setuptools to provide distutils
RUN python3.12 -m ensurepip --upgrade && \
    python3.12 -m pip install --upgrade pip setuptools

RUN wget https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage -O /usr/local/bin/appimagetool \
    && chmod +x /usr/local/bin/appimagetool
RUN useradd -m -s /bin/bash vscode && \
    mkdir -p /etc/sudoers.d && \
    echo "vscode ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers.d/vscode && \
    chmod 0440 /etc/sudoers.d/vscode

# Set up XDG_RUNTIME_DIR for vscode user with correct permissions
RUN mkdir -p /tmp/runtime-vscode && chown vscode:vscode /tmp/runtime-vscode && chmod 0700 /tmp/runtime-vscode
ENV XDG_RUNTIME_DIR=/tmp/runtime-vscode


ENV QT_QPA_PLATFORM=xcb
# Set PATH to include venv in repo and we dont have to install into devcontainer
ENV PATH="/app/.venv/bin:/home/vscode/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

ENV LD_LIBRARY_PATH="/app/.venv/lib/python3.10/site-packages/PyQt5/Qt5/lib:/usr/lib/x86_64-linux-gnu"

USER vscode
WORKDIR /app
CMD ["sleep", "infinity"]