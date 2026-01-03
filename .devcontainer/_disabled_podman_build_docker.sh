#!/bin/bash
# disabled, now setting env with the .env file

export BUILDAH_FORMAT=docker
/usr/bin/podman "\$@"

