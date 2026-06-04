#!/bin/bash
# M1 - User Access Management Start
# Runs the one-time first-admin bootstrap command for Azure Container Apps Jobs.

set -e

cd /app/modules/identity-access-module
exec /opt/stats/runtime/bin/python -m app.scripts.create_admin

# M1 End
