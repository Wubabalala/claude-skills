# doc-garden Hooks Installation

These hooks provide real-time documentation health monitoring. Installation is **manual** — edit your `~/.claude/settings.json` directly.

## Before you start

1. **Back up** your settings:
   ```bash
   cp ~/.claude/settings.json ~/.claude/settings.json.bak
   ```

2. **Copy hook scripts** to your hooks directory:
   ```bash
   cp skills/doc-garden/hooks/session_start_check.py ~/.claude/hooks/
   cp skills/doc-garden/hooks/stop_staleness_check.py ~/.claude/hooks/
   cp skills/doc-garden/hooks/post_edit_memory_index.py ~/.claude/hooks/
   ```

3. Copy the core module (hooks depend on it). **The directory must be named `doc-garden-core`**:
   ```bash
   mkdir -p ~/.claude/hooks/doc-garden-core
   cp skills/doc-garden/core/doc_garden_core.py ~/.claude/hooks/doc-garden-core/
   ```

## Edit settings.json

Open `~/.claude/settings.json` and add hook entries to the `hooks` object. **Merge with existing hooks — don't replace them.**

### Add SessionStart entry

Find the `"SessionStart"` array and add a new entry:

```json
"SessionStart": [
  {
    "hooks": [
      {"type": "command", "command": "bash ~/.claude/hooks/memory_health_check.sh"}
    ]
  },
  {
    "hooks": [
      {"type": "command", "command": "python ~/.claude/hooks/session_start_check.py", "timeout": 5}
    ]
  }
]
```

### Add Stop entry (new section)

```json
"Stop": [
  {
    "matcher": "*",
    "hooks": [
      {"type": "command", "command": "python ~/.claude/hooks/stop_staleness_check.py", "timeout": 5}
    ]
  }
]
```

### Add PostToolUse entry

Find the `"PostToolUse"` array (create if missing) and add:

```json
"PostToolUse": [
  {
    "matcher": "Write|Edit",
    "hooks": [
      {"type": "command", "command": "python ~/.claude/hooks/post_edit_memory_index.py"}
    ]
  }
]
```

## Verify

1. Restart Claude Code (hooks load on startup)
2. In a new session, type `/hooks` to see loaded hooks
3. All three should appear in the list

## What each hook does

| Hook | Event | Action | Blocks? |
|------|-------|--------|---------|
| session_start_check.py | SessionStart | Warns about unindexed memory files | No |
| stop_staleness_check.py | Stop | Warns if code changed but CLAUDE.md didn't | No |
| post_edit_memory_index.py | PostToolUse | Reminds to index new memory files | No |

None of these hooks block operations. They only provide informational messages.

## Uninstall

Remove the hook entries from `settings.json` and delete the scripts:
```bash
rm ~/.claude/hooks/session_start_check.py
rm ~/.claude/hooks/stop_staleness_check.py
rm ~/.claude/hooks/post_edit_memory_index.py
rm -r ~/.claude/hooks/doc-garden-core/
```
