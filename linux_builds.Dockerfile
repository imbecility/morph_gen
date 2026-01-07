# uv-base содержит только бинарник uv
FROM ghcr.io/astral-sh/uv:latest AS uv-base


# сверх старый Debian (для совместимости с любым glibc)
FROM debian:10-slim AS builder-glibc

RUN echo "deb http://archive.debian.org/debian/ buster main" > /etc/apt/sources.list && \
    echo "deb http://archive.debian.org/debian-security/ buster/updates main" >> /etc/apt/sources.list && \
    apt-get -o Acquire::Check-Valid-Until=false update && \
    apt-get install -y --no-install-recommends \
        curl ca-certificates gcc libc6-dev patchelf bash && \
    rm -rf /var/lib/apt/lists/*

COPY --from=uv-base /uv /bin/uv

WORKDIR /build
COPY morph_gen.py .
COPY compile.sh .

RUN chmod +x compile.sh

RUN uv venv .venv --python 3.13
ENV VIRTUAL_ENV=/build/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN uv pip install nuitka pymorphy3 pymorphy3-dicts-ru pyyaml

# сборка glibc бинарника
RUN ./compile.sh /output/morph_gen_linux_x64_glibc

#  старый Alpine (для совместимости со всеми musl)
FROM alpine:3.18 AS builder-musl

RUN apk add --no-cache gcc musl-dev libffi-dev patchelf bash

COPY --from=uv-base /uv /bin/uv

WORKDIR /build
COPY morph_gen.py .
COPY compile.sh .

RUN chmod +x compile.sh

RUN uv venv .venv --python 3.13
ENV VIRTUAL_ENV=/build/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN uv pip install nuitka pymorphy3 pymorphy3-dicts-ru pyyaml

# сборка musl бинарника
RUN ./compile.sh /output/morph_gen_musl_x64


# вывод результатов
FROM scratch AS export

# копирование бинарников из двух стадий
COPY --from=builder-glibc /output/morph_gen_linux_x64_glibc /
COPY --from=builder-musl  /output/morph_gen_musl_x64 /

