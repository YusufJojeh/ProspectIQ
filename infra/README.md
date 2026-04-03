# Infra

Infrastructure assets for LeadScope AI.

- `docker-compose.yml`: local MariaDB service for backend development.
- `docker-compose.deploy.yml`: full image-based deployment stack for MariaDB, API, and web.
- `deploy.env.example`: deployment environment template for Docker Compose and GitHub Actions deploys.

## Local database only

```powershell
docker compose -f infra/docker-compose.yml up -d
```

## Full stack deployment with published images

1. Copy `infra/deploy.env.example` to a real `deploy.env`.
2. Replace every placeholder secret and credential.
3. Pull and start the stack:

```powershell
docker compose --env-file infra/deploy.env -f infra/docker-compose.deploy.yml pull
docker compose --env-file infra/deploy.env -f infra/docker-compose.deploy.yml up -d
```

The deployment compose file expects published images from GHCR and is designed to be used both manually and through the GitHub Actions deploy workflow.

## Deployment verification

The repo includes a reusable verification script for image-based stacks:

```powershell
sh infra/scripts/verify_deploy_stack.sh infra/deploy.env infra/docker-compose.deploy.yml
```

It waits for MariaDB, API, and web health, runs the idempotent bootstrap seed, verifies API and web health endpoints, and confirms login works with the configured bootstrap admin.
