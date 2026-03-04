#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME=${1:-researchclaw:latest}

docker build -f deploy/Dockerfile -t "$IMAGE_NAME" .

echo "Built image: $IMAGE_NAME"
