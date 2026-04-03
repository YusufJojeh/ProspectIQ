#!/bin/sh
set -eu

envsubst '${VITE_API_BASE_URL}' \
  < /usr/share/nginx/html/runtime-config.template.js \
  > /usr/share/nginx/html/runtime-config.js
