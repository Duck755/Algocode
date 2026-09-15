FROM python:3.13-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        cmake \
        g++ \
        make \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
