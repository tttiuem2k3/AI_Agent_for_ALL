# WinSW Settings Move Design

## Goal

Move the Windows service wrapper files from the root-level `app` directory into `service/settings` while keeping the wrapper filenames `AsoftAiService.exe` and `AsoftAiService.xml` unchanged.

## Current State

`app/AsoftAiService.xml` is a WinSW service definition. It configures the Windows service metadata, Python executable, service entrypoint, working directory, environment variables for Redis, SQL/API integration, workspace storage, logging, and restart behavior. The `app` directory currently contains only `AsoftAiService.exe` and `AsoftAiService.xml`.

## Target Structure

The target structure is `service/settings/AsoftAiService.exe` and `service/settings/AsoftAiService.xml`. The root-level `app` directory should be removed when empty.

## Configuration Updates

The XML should use paths for this checkout: `E:\Asoft\ASOFT_AI_SERVICES\.venv\Scripts\python.exe`, `E:\Asoft\ASOFT_AI_SERVICES\service\main.py`, `E:\Asoft\ASOFT_AI_SERVICES` as working directory, `E:\Asoft\ASOFT_AI_SERVICES\src` as `PYTHONPATH`, `E:\Asoft\ASOFT_AI_SERVICES\service\workspaces` as workspace directory, and `E:\Asoft\ASOFT_AI_SERVICES\logs` as log directory.

## Compatibility

The service `id`, `name`, and wrapper basename stay unchanged to preserve WinSW behavior and avoid changing the Windows service identity. Service install/start commands should reference `service/settings/AsoftAiService.exe` after the move.

## Validation

Verify that the old files no longer exist under `app`, the new files exist under `service/settings`, XML parsing succeeds, configured local paths exist, and repository references no longer point to `app/AsoftAiService.xml`.
