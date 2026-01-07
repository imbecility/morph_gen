$ErrorActionPreference = "Stop"

docker build -t morph-builder -f linux_builds.Dockerfile .
docker run --rm -v "${PWD}:/build" morph-builder
