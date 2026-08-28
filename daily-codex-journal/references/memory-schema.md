# Hierarchical memory schema

## Daily manifest

`memory/YYYY/MM/YYYY-MM-DD.json` 使用 UTF-8 JSON：

```json
{
  "schema_version": 1,
  "date": "YYYY-MM-DD",
  "timezone": "Asia/Taipei",
  "generated_at": "ISO-8601 timestamp",
  "source_scope": {
    "accessible_sessions": 0,
    "included_sessions": 0,
    "excluded_sessions": 0,
    "exclusion_reason_counts": {"low_memory_value": 0, "uncertain_value": 0},
    "limitations": []
  },
  "statistics": {"total": 0, "success": 0, "failure": 0, "partial": 0, "cancelled": 0, "incomplete": 0},
  "sessions": [
    {
      "session_ref": "S-YYYYMMDD-deadbeef",
      "source_thread_id_hash": "sha256:<64 lowercase hex characters>",
      "identity_confidence": "confirmed",
      "title": "Session title",
      "started_at": "ISO-8601 timestamp or null",
      "updated_at": "ISO-8601 timestamp or null",
      "status": "success",
      "project": "project or topic name or null",
      "tags": [],
      "original_goal": "",
      "actions_summary": [],
      "outcome": "",
      "artifacts": [{"label": "", "path_or_url": "", "kind": "file"}],
      "problems": [],
      "lessons": [],
      "next_actions": [],
      "continuation_of": null,
      "parent_session_ref": null,
      "related_sessions": [],
      "journal_anchor": "#S-YYYYMMDD-deadbeef"
    }
  ],
  "daily_summary": {"achievements": [], "problems": [], "lessons": [], "tomorrow": []}
}
```

Allowed JSON status values are `success`, `failure`, `partial`, `cancelled`, and `incomplete`. `source_thread_id_hash` is `null` and `identity_confidence` is `unconfirmed` when the raw identifier is unavailable.

## Global index

`memory/index.json` is a compact lookup layer, not a duplicate of every session narrative:

```json
{
  "schema_version": 1,
  "updated_at": "ISO-8601 timestamp",
  "days": {
    "YYYY-MM-DD": {
      "journal": "journals/YYYY/MM/codex-journal-YYYY-MM-DD.html",
      "manifest": "memory/YYYY/MM/YYYY-MM-DD.json",
      "session_refs": [],
      "statistics": {}
    }
  },
  "sessions": {
    "S-YYYYMMDD-deadbeef": {
      "title": "",
      "first_seen": "YYYY-MM-DD",
      "last_seen": "YYYY-MM-DD",
      "dates": [],
      "status": "success",
      "project": null,
      "tags": [],
      "continuation_of": null,
      "parent_session_ref": null,
      "related_sessions": []
    }
  },
  "projects": {
    "project-name": {"session_refs": [], "dates": []}
  }
}
```

## Merge invariants

- A `session_ref` identifies one Codex thread and remains stable across dates.
- `days[date].session_refs` and `sessions[ref].dates` contain unique values sorted ascending.
- `first_seen` and `last_seen` are derived from `dates`.
- The daily statistics equal the number and statuses of daily `sessions`.
- `source_scope.included_sessions` equals the number of daily `sessions`; `accessible_sessions` equals included plus excluded sessions evaluated for that date.
- Exclusion statistics expose only aggregate reason counts. Do not store titles, raw content, identifiers, or narrative summaries for excluded low-value sessions.
- Relationship targets may point to sessions on other dates, but only when supported by source evidence.
- Preserve unknown top-level and session fields when updating a newer schema.
