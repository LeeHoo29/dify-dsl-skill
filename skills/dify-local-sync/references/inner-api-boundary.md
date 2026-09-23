# Inner API Boundary

Dify's `/inner/api` routes are official source code but an internal, trusted surface. They do not carry the compatibility or exposure guarantees of `/openapi/v1`.

This Skill supports only local self-hosted Docker deployments and calls Inner API from inside the API container. It does not configure a public nginx route.

## Authentication

Server-side configuration:

```env
INNER_API=true
INNER_API_KEY=<generated local secret>
```

The request uses `X-Inner-Api-Key`. `INNER_API_KEY_FOR_PLUGIN` is a different credential and must not be reused.

## Create, Overwrite, And Publish

- Create: `POST /inner/api/enterprise/workspaces/<workspace_id>/dsl/import`.
- Draft export: `GET /inner/api/enterprise/apps/<app_id>/dsl`.
- Overwrite: container `AppDslService.import_app(..., app_id=...)`; Dify 1.17.1's Inner API payload is create-only.
- Version confirmation: container `AppDslService.confirm_import()` when an import returns pending.
- Publish: container `WorkflowService.publish_workflow()`; there is no Inner API publish endpoint.
- Verification: Inner API Draft export plus App Workspace/Published Workflow database checks and sync-map SHA checks.

These Service Layer calls are as version-sensitive as Inner API. The scripts are tested against Dify 1.17.1; inspect upstream signatures before extending support to another release.

## Unsupported Targets

- Dify Cloud.
- Remote production hosts.
- Self-hosted instances without Docker/API-container access.
- RAG Pipeline publication.

For Cloud or remote self-hosted synchronization, prefer official `difyctl` OAuth/OpenAPI support. It can import and overwrite Draft apps but currently does not publish Workflow versions.
