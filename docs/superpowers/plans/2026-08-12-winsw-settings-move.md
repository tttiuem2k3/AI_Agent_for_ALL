# WinSW Settings Move Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move WinSW service wrapper files into `service/settings` and update local service paths.

**Architecture:** Keep the existing WinSW wrapper pair together with the same basename. Update only deployment/config documentation and path values needed for the new checkout location.

**Tech Stack:** Windows service wrapper XML, PowerShell validation, Python FastAPI entrypoint.

## Global Constraints

- Keep `AsoftAiService.exe` and `AsoftAiService.xml` filenames unchanged.
- Use `service/settings` as the new directory.
- Preserve service `id`, `name`, and `description`.
- Do not alter secrets or unrelated service runtime behavior.

---

### Task 1: Move Wrapper Files

**Files:**
- Move: `app/AsoftAiService.exe` to `service/settings/AsoftAiService.exe`
- Move: `app/AsoftAiService.xml` to `service/settings/AsoftAiService.xml`

- [ ] Confirm both source files exist.
- [ ] Create `service/settings` and move both files through Git.
- [ ] Remove the empty `app` directory.

### Task 2: Update Wrapper Configuration

**Files:**
- Modify: `service/settings/AsoftAiService.xml`
- Modify: `service/README.md`

- [ ] Update the XML paths for the current checkout.
- [ ] Document the new Windows service wrapper location and commands.

### Task 3: Verify Move

**Files:**
- Verify: `service/settings/AsoftAiService.xml`
- Verify: repository references

- [ ] Validate the new file locations and old directory removal.
- [ ] Parse the XML and verify configured local paths exist.
- [ ] Search the repository for stale wrapper paths.
