#!/usr/bin/env bash
##
## Container build for metrics-proxy
##

# Exit script on first error
set -o errexit

FLASK_APP=metrics_proxy
FLASK_ENV=development

# Use UBI python as base container image
container=$(buildah --name metrics-proxy from registry.access.redhat.com/ubi8/python-36)

buildah config --label maintainer="Federico 'tele' Rossi <ferossi@redhat.com>" $container

# Install packages
buildah run $container pip3 install flask requests

buildah config --user 1000:1000 $container
buildah config --env FLASK_APP=/go --env FLASK_ENV=development $container

# Copy metrics_proxy
buildah copy $container . metrics_proxy.py

buildah config --cmd 'flask run --host=0.0.0.0' $container

# Commit to local container storage
buildah commit $container metrics-proxy
