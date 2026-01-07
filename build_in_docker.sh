#!/usr/bin/env bash
set -euo pipefail

docker build -t morph-builder -f linux_builds.Dockerfile .
docker run --rm -v "$(pwd)":/build morph-builder
