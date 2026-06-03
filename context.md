# Code Context — ytsurf Queue / Playlist / Multi-select Audit

## Files Retrieved
1. `ytsurf.sh` (lines 1–1750) — entire script; single-file Bash program
2. `FUTURE_FEATURES.md` (full) — documents multi-select queue as an explicit planned feature
3. `.github/workflows/ci.yml` (full) — CI pipeline constraints
4. `CONTRIBUTING.md` (full) — code style / ShellCheck requirements

---

## Key Code

### Constants (lines 42–47)
```bash
readonly CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/$SCRIPT_NAME"
readonly CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/$SCRIPT_NAME"
readonly PLAYLIST_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/$SCRIPT_NAME/playlists"
readonly QUEUE_FILE="$HOME/.cache/$SCRIPT_NAME/queue.json"   # NOTE: hardcodes $HOME/.cache, NOT $CACHE_DIR
```
`QUEUE_FILE` bypasses `XDG_CACHE_HOME` while `CACHE_DIR` respects it — inconsistency, though functionally equivalent when `XDG_CACHE_HOME` is unset.

### `configuration()` (lines 383–415)
```bash
configuration() {
  mkdir -p "$CACHE_DIR" "$CONFIG_DIR" "$PLAYLIST_DIR"
  [ -f "$SUB_FILE" ] || echo "[]" >"$SUB_FILE"
  rm "$QUEUE_FILE" && echo "[]" >"$QUEUE_FILE"   # BUG — see §1
  ...
}
```

### `add_to_queue()` (lines 951–991)
Merges one video into `QUEUE_FILE`, deduplicates by `.id`, caps at `$max_history_entries` (default 100).  
Stored JSON keys: `title`, `id`, `duration`, `author`, `views`, `published`, **`thumbnail`** (singular), `timestamp`.

### `process_queue()` (lines 993–1035)
Reads `QUEUE_FILE`, plays/downloads all entries in **reverse order** (newest-first, because `add_to_queue` prepends).  
Key bug — line 995: calls `select_format "$video_url"` where `video_url` is a global that holds the **last selected video**, not meaningful for a multi-video queue.  
Key bug — line 1026: reads `.[].thumbnails` (plural) but the stored field is `.[].thumbnail` (singular) → thumbnails always `null` in history when played via queue.

### `handle_selection()` queue branch (lines 1645–1680)
```bash
if [[ "$queue_mode" == true ]]; then
    add_to_queue "$video_id" ...
    # presents fzf/rofi/etc menu with 4 choices:
    items=("Add_To_Queue" "Watch_Or_Download_Queue" "Save_To_Playlist" "Toggle_Queue_Mode")
    ...
    if "Add_To_Queue"        → STATE="SEARCH"; query=""
    if "Watch_Or_Download_Queue" → STATE="PLAY"
    if "Save_To_Playlist"    → save_queue_to_playlist   # exit 0 — terminates session
    if "Toggle_Queue_Mode"   → queue_mode=false         # STATE unchanged (stays "SEARCH")
fi
```

### `save_queue_to_playlist()` (lines 1037–1052)
```bash
cp "$QUEUE_FILE" "$playlist_file"
exit 0    # hard exit — user cannot continue after saving
```

### `handle_playlist()` (lines 1054–1121)
```bash
local playlists=("$PLAYLIST_DIR"/*.json)
if ((${#playlists[@]} == 0)); then    # BUG — see §2
    ...exit 1
fi
...
mapfile -t video_thumbnail_list < <(jq -r '.[].thumbnails' "${playlists[$index]}" 2>/dev/null)  # BUG: plural
...
playlist_mode=false   # cleared after playback
```

### `select_from_menu()` (lines 1529–1574)
```bash
# fzf path — NO --multi flag:
selected_item=$(printf "%s\n" "${menu_items[@]}" | fzf \
  --prompt="$prompt" \
  --preview="bash -c '$preview_script' -- {n}")
# returns single string; no multi-select support in any selector branch
```

### `perform_action()` (lines 1127–1159)
```bash
perform_action() {
  [ "$download_mode" == false ] && [ "$playlist_mode" == false ] && {
    selection="$(select_action)" || { ... return 1 }
    download_mode="$selection"   # "false" or "true"
  }
  if [[ "$format_selection" == true ]]; then
    format_code=$(select_format "$video_url") ...
  fi
  if [[ "$queue_mode" == true ]];   then process_queue
  elif [[ "$playlist_mode" == true ]]; then handle_playlist
  elif [[ "$download_mode" == true ]]; then download_video ...
  else play_video ...
  fi
  [ "$history_mode" == true ] && STATE="HISTORY"
  [ "$history_mode" == true ] || { STATE="SEARCH"; query=""; }
}
```

### `main()` (lines 1726–1745)
```bash
main() {
  STATE="SEARCH"
  [[ ... && "$queue_mode" != true && "$playlist_mode" != true && -z "$query" ]] && select_init
  [ "$history_mode" == true ] && STATE="HISTORY"
  [ "$sub_mode" == true ]     && STATE="SUB"
  [ "$playlist_mode" == true ] && STATE="PLAY"
  while :; do
    case "$STATE" in
    SEARCH)  handle_selection ;;
    SUB)     manage_subscriptions ;;
    PLAY)    perform_action ;;
    HISTORY) handle_history ;;
    EXIT)    break ;;
    *)       break ;;
    esac
  done
}
```

---

## Architecture

```
main()
 ├── select_init() [interactive mode, no flags/query]
 └── while loop:
     SEARCH ──► handle_selection()
     │            ├── fetch_search_results / fetch_feed
     │            ├── select_from_menu()  [single select only]
     │            ├── [non-queue] add_to_history → STATE="PLAY"
     │            └── [queue_mode] add_to_queue → menu → STATE="SEARCH"|"PLAY"
     │
     PLAY ────► perform_action()
     │            ├── select_action()     [watch/download/syncplay]
     │            ├── queue_mode  → process_queue()
     │            ├── playlist_mode → handle_playlist()
     │            ├── download    → download_video()
     │            └── watch       → play_video()
     │            └── → STATE="SEARCH" (or "HISTORY")
     │
     HISTORY ─► handle_history() → STATE="PLAY"
     SUB ─────► manage_subscriptions() → STATE="EXIT"
     EXIT ────► break
```

Data flow for queue:
`handle_selection` → `add_to_queue` writes to `QUEUE_FILE` →
"Watch_Or_Download_Queue" → STATE=PLAY →
`perform_action` → `process_queue` reads `QUEUE_FILE` → plays in reverse order →
returns to `perform_action` → STATE="SEARCH"

---

## Section-by-Section Findings

---

### §1 — Queue System

#### 1a. Is the queue persistent across runs?

**No — and there is a bug in the reset logic.**

Line 388: `rm "$QUEUE_FILE" && echo "[]" >"$QUEUE_FILE"`

The `&&` operator means: if `rm` fails (e.g. first run, file does not exist yet), the `echo "[]"` is **never executed**, leaving `QUEUE_FILE` absent. Any subsequent `jq --slurpfile existing "$QUEUE_FILE"` call inside `add_to_queue` will fail silently.

**Fix**: `rm -f "$QUEUE_FILE"; echo "[]" >"$QUEUE_FILE"` (use `;` not `&&`, `-f` suppresses the no-file error).

Even if the rm succeeded, the queue is always wiped on every startup. This appears intentional (queue is a per-session construct), but there is no config option to make it persistent.

#### 1b. Can the queue grow across multiple search sessions within one run?

**Yes.** The flow within a single process:
- "Add_To_Queue" → `STATE="SEARCH"` + `query=""` → back to search menu → pick another video → adds to same queue file.
- The queue accumulates until "Watch_Or_Download_Queue" or "Save_To_Playlist" is chosen.

#### 1c. Is there a UI to view the current queue?

**No.** The four queue-mode menu items are `Add_To_Queue`, `Watch_Or_Download_Queue`, `Save_To_Playlist`, `Toggle_Queue_Mode`. There is no "View_Queue" / "Show_Queue" option.

#### 1d. Queue not cleared after playback

After `process_queue` finishes, `queue_mode` remains `true` and `QUEUE_FILE` still contains the played videos. On the next SEARCH/add cycle, `add_to_queue` will prepend new entries on top of stale ones. A user who plays the queue and then adds more videos will see old videos replayed.

#### 1e. Queue thumbnail field typo (BUG)

Line 1026: `mapfile -t video_thumbnail_list < <(jq -r '.[].thumbnails' "$QUEUE_FILE")`

The JSON key stored by `add_to_queue` (line 982) is `thumbnail` (singular). `.thumbnails` returns `null` for every entry, so `add_to_history` calls during queue playback pass `null` as the thumbnail. Same bug exists at line 1110 in `handle_playlist`.

#### 1f. process_queue uses stale `$video_url` for format_selection (BUG)

Lines 994–998:
```bash
if [[ "$format_selection" = true ]]; then
  if ! format_code=$(select_format "$video_url"); then   # video_url = LAST selected video
```
`video_url` is a global that was set by the most recent `handle_selection` call. For a multi-video queue, this is meaningless — the user is prompted to pick a resolution for a video they already moved past. Correct behavior would be to either prompt once generically or prompt per-item inside the loop.

---

### §2 — Playlist System

#### 2a. Empty PLAYLIST_DIR — broken guard (BUG)

Lines 1057–1060:
```bash
local playlists=("$PLAYLIST_DIR"/*.json)
if ((${#playlists[@]} == 0)); then
```
Bash glob expansion **without `nullglob`** never produces an empty array when there are no matches; it produces a one-element array containing the literal unmatched pattern string (e.g. `/home/user/.config/ytsurf/playlists/*.json`). So `${#playlists[@]}` is `1`, not `0`, and the guard never fires. The `names` array will contain a string like `*.json`, and `playlists[$index]` will reference a file that does not exist → jq errors / silent empty output.

**Fix**: Add `shopt -s nullglob` before the glob (and `shopt -u nullglob` after), or check `[[ ! -e "${playlists[0]}" ]]`.

#### 2b. No delete playlist

There is no UI element anywhere for deleting a saved playlist. The user must manually `rm` the file from `$PLAYLIST_DIR`.

#### 2c. No append to existing playlist

`save_queue_to_playlist` (line 1050) does `cp "$QUEUE_FILE" "$playlist_file"` — a straight overwrite. Entering an existing playlist name replaces it silently. There is no option to load an existing playlist, extend it, and re-save.

#### 2d. `save_queue_to_playlist` hard-exits (BUG / design gap)

Line 1051: `exit 0`. After saving, the session terminates unconditionally. If the user wanted to keep watching after saving, they cannot. A `return` would allow the session to continue.

#### 2e. Thumbnail typo (same as §1e)

Line 1110: `jq -r '.[].thumbnails'` → `thumbnail` is the correct key.

---

### §3 — fzf Multi-select Gap

#### 3a. `--multi` is never used

A full-text search confirms: no occurrence of `--multi`, `-multi-select`, `nullglob` or any multi-select keyword in the entire script.

`select_from_menu` always returns a **single string** via:
```bash
selected_item=$(printf "%s\n" "${menu_items[@]}" | fzf --prompt="$prompt" --preview=...)
```

`handle_selection` is built entirely around a single `selected_title` variable.

#### 3b. What would need to change to support multi-select enqueue?

Minimum required changes:

| Step | Change needed |
|------|--------------|
| **`select_from_menu`** | Add `--multi` flag to fzf call; change return type to newline-separated string (or array ref) |
| **rofi branch** | Add `-multi-select` flag to rofi call |
| **sentaku/tv branches** | Investigate native multi-select; document behavior |
| **`handle_selection`** | Replace single `selected_title` with an array; loop over each selected title; find its index in `menu_list`; call `add_to_queue` for each |
| **Queue auto-trigger** | When multiple items are selected, the per-item action menu is awkward; probably skip the per-item menu and go straight to "Added N videos to queue" notification, then ask once whether to add more or play |
| **`select_from_menu` signature** | Currently passes prompt/json_data/is_history as positional args smuggled into the same array — this fragile interface needs to be the first thing refactored |

The current `select_from_menu` signature is already a liability:
```bash
select_from_menu() {
  local menu_items=("$@")
  local prompt="${menu_items[-3]}"
  local json_data="${menu_items[-2]}"
  local is_history="${menu_items[-1]:-false}"
  unset 'menu_items[-1]' 'menu_items[-1]' 'menu_items[-1]'
  ...
}
```
It abuses `"$@"` to pack data and metadata together, then uses array tail slicing to unpack. Multi-select output needs a cleaner calling convention (e.g., pass json_data as a named variable / global, use a separate `select_multi_from_menu` function).

---

### §4 — State Machine

#### Valid STATE transitions (full map)

```
start
 │
 ▼
[select_init if no flags/query]
 │  Search_youtube     → STATE="SEARCH" (explicit)
 │  Open_your_feed     → feed_mode=true; falls to SEARCH
 │  View_your_history  → history_mode=true; overridden below
 │  Select_playlist    → playlist_mode=true; overridden below
 │  Manage_subscriptions → sub_mode=true; overridden below
 │
 ├─ history_mode=true  → STATE="HISTORY"
 ├─ sub_mode=true      → STATE="SUB"
 └─ playlist_mode=true → STATE="PLAY"

SEARCH ──────────────────────────────────────────────
  handle_selection()
  [non-queue, normal]:  → STATE="PLAY"
  [queue: Add_To_Queue]: → STATE="SEARCH"; query=""    (loop)
  [queue: Watch_Or_Download_Queue]: → STATE="PLAY"
  [queue: Save_To_Playlist]: → exit 0                  (terminates)
  [queue: Toggle_Queue_Mode]: queue_mode=false; STATE unchanged → SEARCH loop
                              (query NOT cleared — re-searches same term silently)

PLAY ────────────────────────────────────────────────
  perform_action()
  → process_queue (if queue_mode)
  → handle_playlist (if playlist_mode; sets playlist_mode=false inside)
  → download_video / play_video (otherwise)
  always: history_mode=true  → STATE="HISTORY"
          else               → STATE="SEARCH"; query=""

HISTORY ─────────────────────────────────────────────
  handle_history()
  → STATE="PLAY"

SUB ─────────────────────────────────────────────────
  manage_subscriptions()
  → STATE="EXIT"

EXIT → break
```

#### When does `queue_mode` stay true vs get cleared?

| Trigger | Result |
|---------|--------|
| `--queue` CLI flag | `queue_mode=true` for the entire session |
| User picks "Toggle_Queue_Mode" | `queue_mode=false`; stays false for the rest of the session |
| `process_queue` completes | `queue_mode` is **not cleared** — stays `true` |
| `handle_playlist` completes | `playlist_mode=false` cleared; `queue_mode` unaffected |

After `process_queue`, the script returns to SEARCH with `queue_mode=true` and the old entries still in `QUEUE_FILE`. The user is implicitly still in queue-build mode.

#### After `process_queue`, what STATE does control return to?

`process_queue` returns to `perform_action`. `perform_action` unconditionally sets:
```bash
[ "$history_mode" == true ] && STATE="HISTORY"
[ "$history_mode" == true ] || { STATE="SEARCH"; query=""; }
```
→ **STATE = "SEARCH"** (unless `--history` was active, in which case STATE = "HISTORY").

---

### §5 — Selector Consistency

| Selector | Multi-select support | Used in codebase |
|----------|---------------------|-----------------|
| **fzf** | Yes — `--multi` flag, Tab to select, output is newline-separated | ✅ Primary; no `--multi` used |
| **rofi** | Yes — `-multi-select` flag | ✅ Used; no `-multi-select` used |
| **sentaku** | Unknown from codebase; CLI docs not present | ✅ Used; behavior unknown |
| **tv** (television TUI) | Unknown; `--source-command` pattern used | ✅ Used; behavior unknown |

No pattern for handling multi-line selection output exists anywhere in the codebase. Every selector path feeds into a single `selected_item` string variable.

---

### §6 — ShellCheck / CI Constraints

#### CI pipeline (`.github/workflows/ci.yml`)
- **Triggers**: push/PR to `main`
- **Platforms**: `ubuntu-latest`, `macos-latest`
- **Key enforced checks**:
  1. `shellcheck ytsurf.sh` — **must pass with zero warnings** to merge
  2. `./ytsurf.sh -V` — smoke test (version flag)
  3. `! ./ytsurf.sh --limit "not-a-number"` — expected-failure test

#### ShellCheck observations (static, no local binary)
- Script has inline directives: `# shellcheck source=/home/stan/.config/ytsurf/config` and `# shellcheck disable=SC1090`
- **CONTRIBUTING.md says** `set -euo pipefail` is required; **actual script** uses only `set -u` (line 12). This is a style violation but ShellCheck does not enforce it as an error by default.
- The heredoc preview scripts inside `create_preview_script_fzf()` use `$variable` expansions in single-quoted heredocs — intentional (they're scripts-as-strings), and ShellCheck usually handles these correctly when quoted heredoc markers are used.
- `local video_url=...` inside loops in `process_queue` and `handle_playlist` is safe (local scoping).
- Any new code adding `fzf --multi` or glob patterns MUST either pass ShellCheck clean or include `# shellcheck disable=SCxxxx` with justification.

---

### §7 — `--watch` / `action_mode` interaction with queue

`--watch` sets `action_mode=false`. In `select_action()`:
```bash
if [[ "$action_mode" == true ]]; then
  # ...presents fzf menu...
else
  echo false   # returns "false" directly
fi
```

`perform_action` receives `selection="false"` and sets `download_mode="false"`.

The queue branch `if [[ "$queue_mode" == true ]]; then process_queue` is evaluated **after** `download_mode` is set, independently. So:

- `--watch --queue`: `action_mode=false` skips the watch/download/syncplay prompt; queue plays in watch mode. ✅ **Works correctly.**
- The only effect of `--watch` on queue mode is that the pre-play action dialog is bypassed (always watches, never downloads).

---

## Architecture

```
ytsurf.sh
 ├── Constants / globals (lines 14–83)
 ├── Utility: fetch_feed, process_channel, search_channel, send_notification, clip (lines 85–185)
 ├── Desktop entry / preview helpers (lines 186–270)
 ├── configuration() — mkdir, reset queue, source config (lines 383–415)
 ├── setup_cleanup() — mktemp, EXIT trap (lines 416–419)
 ├── check_dependencies() (lines 420–455)
 ├── parse_arguments() (lines 460–545)
 ├── Subscribe management: manage_subscriptions, sync_subs, subscribe, unsubscribe (lines 546–840)
 ├── select_action() (lines 843–876)
 ├── select_format() (lines 877–945)
 ├── Queue: add_to_queue, process_queue, save_queue_to_playlist, handle_playlist (lines 951–1121)
 ├── perform_action, download_video, play_video (lines 1122–1220)
 ├── History: add_to_history, handle_history (lines 1225–1355)
 ├── Search/Selection: get_search_query, fetch_search_results, create_preview_script_fzf,
 │   select_with_rofi_drun, select_from_menu, handle_selection, select_init (lines 1356–1720)
 └── main() (lines 1726–1745)
```

Global state shared across functions:
- `STATE` — drives the main while loop
- `json_data` — last fetched search/feed results (exported for fzf preview subprocess)
- `queue_mode`, `playlist_mode`, `history_mode`, `feed_mode`, `sub_mode`, `download_mode`, `action_mode`
- `video_url`, `selected_title`, `img_path` — set by `handle_selection`/`handle_history`, consumed by `perform_action`
- `format_code` — set by `select_format` or default

---

## Bug Summary (ranked by severity)

| # | Location | Bug | Impact |
|---|----------|-----|--------|
| 1 | `configuration()` line 388 | `rm "$QUEUE_FILE" && echo "[]"` — first-run race: queue file never created if rm fails | `add_to_queue` crashes on first use |
| 2 | `handle_playlist()` line 1057 | Glob empty-check broken (no nullglob) | `--playlist` on empty dir enters invalid state, tries to read `*.json` literal as a file |
| 3 | `process_queue()` line 1026 | `.[].thumbnails` typo — should be `.[].thumbnail` | Thumbnails always null in history for queue-played videos |
| 4 | `handle_playlist()` line 1110 | Same `.[].thumbnails` typo | Same as above for playlist-played videos |
| 5 | `process_queue()` line 995 | `select_format "$video_url"` uses stale global | Format selection prompt references wrong video when queue has >1 item |
| 6 | `save_queue_to_playlist()` line 1051 | `exit 0` instead of `return` | Session unconditionally ends after saving playlist |
| 7 | `handle_selection()` line 1675 | `Toggle_Queue_Mode` does not clear `query` | Re-searches same term silently after toggling, may confuse user |
| 8 | Post-`process_queue` | `queue_mode` not cleared, `QUEUE_FILE` not flushed | Old videos stay in queue; risk of replaying after new adds |

---

## Top 5 Unresolved Implementation Questions

1. **Should the queue be persistent across runs?**  
   The current `rm` in `configuration()` is clearly intentional (queue is per-session), but the `&&` bug means first-run always fails silently. Should the fix be `rm -f … ; echo "[]"` (keep ephemeral) or should an env/config flag gate persistence? This determines the correct fix shape.

2. **Multi-select: single `select_from_menu` function vs separate `select_multi_from_menu`?**  
   The existing `select_from_menu` has a fragile `"$@"` packing convention (prompt/json_data/is_history smuggled as trailing positional args). Adding `--multi` to it would require changing the return type (array vs string), breaking every existing call site. Is the intent to add a parallel `select_multi_from_menu`, or refactor the existing function's signature first?

3. **Queue playback order: should `process_queue` play in insertion order (FIFO) or current reverse order (LIFO)?**  
   `add_to_queue` prepends new items; `process_queue` iterates `from (len-1) down to 0`, which plays oldest-first (FIFO). This is correct for a queue semantically, but the loop index direction and `add_to_queue` prepend design are easy to accidentally break. Should the storage order be reversed (append instead of prepend) to make the play loop a straightforward forward iteration?

4. **`save_queue_to_playlist` — `exit 0` vs `return`: what is the intended post-save flow?**  
   Currently saves then terminates. Should the session continue (user can keep adding / switch to watch)? If `return` is used instead, `STATE` would fall through to `SEARCH` via `perform_action`'s tail — is that the right destination, or should there be an explicit STATE assignment?

5. **sentaku and tv multi-select capability?**  
   Before designing a multi-select abstraction, it needs to be determined whether sentaku and tv can output multiple selected lines (Tab/mark), and if so, in what format. The fzf/rofi paths are clear (newline-separated, `--multi` / `-multi-select`), but the sentaku and tv branches would need separate handling or a documented "multi-select not supported" fallback.

---

## Start Here

Open **`ytsurf.sh` at line 383** (`configuration()`) to see the queue reset bug — it's the root cause of first-run failures. Then read `handle_selection()` starting at line 1645 to understand the full queue state machine. The playlist empty-guard at `handle_playlist()` line 1057 is the second most important defect. For multi-select work, start at `select_from_menu()` line 1529 to understand what the calling convention refactor must look like before `--multi` can be threaded in.
