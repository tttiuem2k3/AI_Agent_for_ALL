# Service Workspace Location Design

## Goal

Use `service/workspaces` as the only runtime workspace root and reserve the root-level `data` directory for unrelated storage.

## Data Migration

Delete the obsolete runtime data previously under `service/workspaces`, then move the complete `data/workspaces` tree into `service/workspaces` without changing workspace contents or identifiers.

## Runtime Configuration

Set `ASOFT_AI_WORKSPACE_DIR` in the WinSW XML to `E:\Asoft\ASOFT_AI_SERVICES\service\workspaces`. Change the standalone host fallback from `./data/workspaces` to `./service/workspaces` so Windows service and manual startup use the same location.

## Validation

Verify the old `data/workspaces` path is absent, migrated files are present under `service/workspaces`, source and documentation contain no active `data/workspaces` references, XML parsing succeeds, and the test suite passes.
