# Service Workspace Location Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move runtime workspaces from `data/workspaces` to `service/workspaces` and make the server consistently use the new location.

**Architecture:** Preserve workspace contents while replacing obsolete target data. Configure both WinSW and the standalone host fallback to use the same absolute or repository-relative service workspace root.

**Tech Stack:** Python, WinSW XML, PowerShell filesystem validation.

## Global Constraints

- Reserve `data` for non-workspace storage.
- Preserve migrated workspace identifiers and contents.
- Remove obsolete `service/workspaces` data before migration.

---

### Task 1: Migrate Workspace Data

- [ ] Remove the obsolete `service/workspaces` tree.
- [ ] Move `data/workspaces` to `service/workspaces`.
- [ ] Confirm migrated file counts and contents.

### Task 2: Update Runtime Configuration

- [ ] Change the standalone fallback to `./service/workspaces`.
- [ ] Change WinSW `ASOFT_AI_WORKSPACE_DIR` to `service/workspaces`.
- [ ] Update service documentation.

### Task 3: Verify Behavior

- [ ] Search for stale active `data/workspaces` references.
- [ ] Parse XML and verify the configured directory.
- [ ] Run the test suite.
