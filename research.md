# Research: Windows Compatibility for ytsurf.sh

## Summary

Most of ytsurf.sh's dependencies have usable Windows equivalents in Git Bash / MSYS2, but two areas require **code changes**: (1) `notify-send` has no drop-in and needs a shim, and (2) the `--input-ipc-server` socket path for mpv must switch from a Unix socket path (`/tmp/mpv.sock`) to a Windows named pipe path (`\\.\pipe\mpv-pipe`), and socat cannot communicate with it from MSYS2. Chafa runs natively on Windows but sixel image sizing in Windows Terminal is broken due to a known upstream limitation; Unicode-block fallback mode works. Everything else (stat, sha256sum, fzf, perl one-liners, XDG paths) is fully functional in Git Bash without changes.

---

## Findings

### 1. chafa on Windows

1. **Native Windows binaries exist** — The official chafa download page ([hpjansson.org/chafa/download](https://hpjansson.org/chafa/download/)) provides prebuilt standalone `.zip` binaries for x86_64-windows, e.g. `chafa-1.14.1-1-x86_64-windows.zip`. [Source](https://hpjansson.org/chafa/releases/static/)

2. **MSYS2 package available** — `pacman -S mingw-w64-x86_64-chafa` installs chafa 1.18.2-1 from the `mingw64` repo. Also installable via **Scoop**: `scoop install chafa`. [Source](https://packages.msys2.org/packages/mingw-w64-x86_64-chafa)

3. **Sixel sizing is broken in Windows Terminal** ⚠️ — chafa relies on `ioctl()` to probe pixel dimensions; Windows has no equivalent. It falls back to assuming 8×8-pixel cells, making sixel output render too small. This is a known upstream bug (chafa issue #211). The `-s` size flag also does not help. [Source](https://github.com/hpjansson/chafa/issues/211)

4. **Workaround: use Unicode block/symbols mode** — `chafa --format symbols` (or `chafa -f symbols`) renders using Unicode block characters instead of sixels — no pixel-dimension query needed, works correctly in Windows Terminal and mintty (Git Bash default terminal). This is the safe fallback for ytsurf's preview pane.

5. **iterm2 inline protocol is erratic on mintty** — `chafa -f iterm` sometimes outputs extra trailing space, causing the shell prompt to land at the bottom-right of the image rather than below it. Avoid iterm2 format on Windows. [Source](https://github.com/hpjansson/chafa/issues/194)

---

### 2. `stat -c "%Y"` on Windows

6. **Git Bash ships GNU coreutils including `stat`** — Git for Windows bundles the MSYS2 runtime with GNU coreutils (`stat.exe`, version 8.32+). `stat -c "%Y" file` works identically to Linux — returns Unix mtime as seconds since epoch. No change needed. [Source](https://packages.msys2.org/package/coreutils)

7. **Perl alternative also works** — `perl -e 'print((stat("file"))[9])'` is portable across Strawberry Perl, MSYS2 perl, and Linux perl. This is the safest cross-platform fallback if GNU `stat` is somehow absent.

8. **GNU `date -r` is available** — Git Bash ships GNU `date`, so `date -r file +%s` also works as a one-liner for mtime.

9. **PowerShell approach produces Windows FILETIME, not Unix epoch** — `(Get-Item file).LastWriteTime.ToFileTime()` gives Windows FILETIME (100-ns intervals since 1601), not Unix epoch. Do NOT use this in a bash script expecting Unix timestamps.

---

### 3. `notify-send` on Windows

10. **No native `notify-send` in Git Bash / MSYS2** — There is no package providing a `notify-send` binary for Git Bash (not WSL). All WSL-specific tools (`wsl-notify-send`, `notify-send-wsl`) require WSL and do not apply here.

11. **Lightest approach: silent no-op shim** — Add this guard in the script for Windows:
    ```bash
    if ! command -v notify-send &>/dev/null; then
      notify-send() { :; }
    fi
    ```
    This is zero-dependency and prevents errors. Notifications are silently dropped.

12. **`msg * "text"` (built-in Windows)** — `msg.exe` ships with Windows 10 Pro/Enterprise. Usage from Git Bash: `msg '*' "$message"`. Pops a dialog box (not a toast). Requires an interactive session; may fail on Home edition or locked sessions. [Source](https://gist.github.com/maddouri/b541087fbb8353ae39f882848f326ede)

13. **BurntToast PowerShell module** — `powershell -command "New-BurntToastNotification -Text 'ytsurf','$msg'"`. Requires `Install-Module BurntToast` (one-time, admin). Produces proper Windows toast notifications. [Source](https://github.com/windos/burnttoast)

14. **Recommended pattern for the script**:
    ```bash
    _notify() {
      if command -v notify-send &>/dev/null; then
        notify-send "$@"
      elif [[ "$OS" == "Windows_NT" ]]; then
        powershell -command "New-BurntToastNotification -Text '$1','$2'" 2>/dev/null || true
      fi
    }
    ```

---

### 4. XDG dirs on Windows (Git Bash / MSYS2)

15. **`$HOME` in Git Bash = `/c/Users/<username>`** — Git Bash maps the Windows user profile to MSYS-style paths. `echo $HOME` → `/c/Users/YourName` which corresponds to `C:\Users\YourName`. [Source](https://graphite.com/guides/git-change-home-directory-git-bash)

16. **`${XDG_CONFIG_HOME:-$HOME/.config}` resolves to `/c/Users/<username>/.config`** — This creates `C:\Users\<username>\.config\ytsurf\`. The directory is created silently by `mkdir -p` in Git Bash with no issues. This path is NOT `%APPDATA%` (`C:\Users\<username>\AppData\Roaming`).

17. **`~/.config/ytsurf` is a reasonable location for Git Bash users** — It's consistent with what WSL/Linux users expect and what Git itself uses. However, Windows-native users unfamiliar with MSYS paths may not find it easily. For a friendlier Windows default, the script could add:
    ```bash
    if [[ "$OS" == "Windows_NT" && -z "$XDG_CONFIG_HOME" ]]; then
      XDG_CONFIG_HOME="$(cygpath -u "$APPDATA")"
    fi
    ```
    This maps `%APPDATA%` → `/c/Users/<username>/AppData/Roaming` so config lands in `%APPDATA%\ytsurf`.

18. **`$XDG_CONFIG_HOME` is not set by default** — Neither Git Bash nor Windows sets this variable. The `:-$HOME/.config` fallback always applies unless the user sets it explicitly.

---

### 5. fzf on Windows

19. **fzf works in Windows Terminal with Git Bash** — Core functionality (search, selection, `{n}` index bindings, key bindings) works correctly. fzf ships a native Windows binary (`fzf.exe`). [Source](https://github.com/junegunn/fzf)

20. **ANSI colors in preview work on Windows Terminal, not mintty** ⚠️ — When running Git Bash inside **Windows Terminal**, fzf preview ANSI colors render correctly. When running via **mintty** (standalone Git Bash), colors in the preview pane can be broken (issue #4199). Recommend instructing users to run inside Windows Terminal. [Source](https://github.com/junegunn/fzf/issues/4199)

21. **Chafa thumbnail preview in fzf `--preview`** — Works with Unicode block mode (`chafa -f symbols`). Sixel mode inside fzf's preview pane is additionally broken because fzf itself remaps the preview subprocess's terminal dimensions. There is a known open issue for sixel support in fzf on Windows (issue #4399 in fzf repo). For ytsurf's use case, forcing `CHAFA_FORMAT=symbols` in the preview command is the pragmatic fix. [Source](https://github.com/junegunn/fzf/issues/4399)

22. **`{n}` index placeholders** — Work correctly on Windows; no platform-specific issues found.

---

### 6. mpv on Windows

23. **`mpv https://youtu.be/XXXX` works on Windows** — mpv Windows builds support URL playback via yt-dlp. Place `yt-dlp.exe` in the same directory as `mpv.exe` or in system PATH. mpv will invoke it automatically. [Source](https://github.com/mpv-player/mpv/issues/4727)

24. **`--input-ipc-server` uses named pipes on Windows, NOT Unix sockets** ⚠️ — This is a **hard behavioral difference** requiring script changes:
    - **Linux**: `mpv --input-ipc-server=/tmp/mpvsocket`
    - **Windows**: `mpv --input-ipc-server=\\.\pipe\mpv-pipe`
    From Git Bash, use the MSYS-escaped form: `//./pipe/mpv-pipe`

25. **socat cannot communicate with Windows named pipes** — MSYS2/Cygwin ports of socat do not implement `PIPE:` connectors for Windows named pipes. You cannot use `socat - //./pipe/mpv-pipe` to send JSON commands. [Source](https://github.com/mpv-player/mpv/blob/master/DOCS/man/ipc.rst)

26. **Workaround for sending IPC commands from bash on Windows**:
    - Simple one-way (no response): `echo '{"command":["cycle","pause"]}' > //./pipe/mpv-pipe`
    - Two-way (with response): requires a PowerShell script using `System.IO.Pipes.NamedPipeClientStream`, or a small helper binary. [Source](https://github.com/mpv-player/mpv/discussions/14703)

27. **Recommended Windows IPC shim**:
    ```bash
    mpv_send() {
      local cmd="$1"
      if [[ "$OS" == "Windows_NT" ]]; then
        echo "$cmd" > //./pipe/mpv-pipe 2>/dev/null
      else
        echo "$cmd" | socat - "$MPV_SOCKET"
      fi
    }
    ```

---

### 7. perl one-liner portability

28. **Single-quoted perl one-liners work correctly in Git Bash** — Git Bash uses a POSIX-compatible shell (bash), where single quotes protect all special characters. The one-liner `perl -0777 -ne 'print $1 if /var ytInitialData = (.*?);\s*<\/script>/s'` runs without modification when invoked from Git Bash. [Source](https://stackoverflow.com/questions/660624)

29. **Single quotes BREAK in CMD.EXE and PowerShell** ⚠️ — CMD.EXE does not treat `'` as a string delimiter. Running the same one-liner directly in `cmd.exe` gives `Can't find string terminator "'" anywhere before EOF`. This is only a problem if the script is ever invoked outside Git Bash. Since ytsurf.sh is a bash script, this is a non-issue as long as it runs in bash.

30. **`-0777` slurp mode and `/s` modifier are fully portable** — These Perl features work identically on Strawberry Perl (Windows), MSYS2 perl, and Linux perl. No version-specific concerns.

31. **MSYS2 perl vs Strawberry Perl** — MSYS2 includes perl, but for a standalone Windows install, Strawberry Perl is preferable. Both handle the one-liner identically when invoked from bash. Path handling (backslash vs forward slash) is not an issue since no file paths appear inside the `-e` code.

---

### 8. `sha256sum` on Windows

32. **`sha256sum` is available in Git Bash** — Git for Windows bundles GNU coreutils including `sha256sum.exe`. Usage is identical to Linux: `sha256sum file` or `echo "content" | sha256sum`. [Source](https://stackoverflow.com/questions/64192561)

33. **Output format is identical** — GNU `sha256sum` on Windows produces the same two-space-separated format: `abc123...  filename` (two spaces). For stdin: `abc123...  -`. No gotchas with the double-space format vs any Windows-specific output.

34. **Available in MSYS2 as well** — Part of the `coreutils` package in the `msys` repo.

35. **Windows built-in `certutil` format differs** — `certutil -hashfile file SHA256` outputs a verbose multi-line format (header line, uppercase hash, footer line). Do NOT use certutil as a drop-in for `sha256sum` in scripts expecting `<hash>  <filename>` format.

---

## Hard Blockers

| Item | Severity | Notes |
|------|----------|-------|
| `--input-ipc-server` path format | **MEDIUM** — requires code change | Linux socket path must become Windows named pipe path; socat unusable from MSYS2 for bidirectional IPC |
| `notify-send` | **LOW** — graceful degradation | No drop-in available; a no-op shim is the easiest fix |
| chafa sixel sizing | **LOW** — fallback works | Sixels render too small in Windows Terminal; must use `-f symbols` mode instead |
| fzf preview ANSI in mintty | **LOW** — Windows Terminal works | Only an issue in standalone mintty, not Windows Terminal |

---

## Sources

### Kept
- **hpjansson.org/chafa/download** — Official chafa download page, confirms native Windows binaries
- **packages.msys2.org/packages/mingw-w64-x86_64-chafa** — Confirms MSYS2 package 1.18.2-1
- **github.com/hpjansson/chafa/issues/211** — Confirms sixel sizing bug in Windows Terminal with technical detail
- **github.com/hpjansson/chafa/issues/194** — Confirms iterm2 format erratic behavior on mintty
- **mpv.io/manual/stable** — Official mpv docs confirming named pipe on Windows
- **github.com/mpv-player/mpv/blob/master/DOCS/man/ipc.rst** — Confirms socat cannot work with Windows named pipes
- **github.com/mpv-player/mpv/discussions/14703** — PowerShell named pipe workaround
- **github.com/junegunn/fzf/issues/4199** — ANSI color bug in fzf preview on mintty
- **github.com/junegunn/fzf/issues/4399** — Sixel fzf preview bug on Windows
- **stackoverflow.com/questions/660624** — Perl single-quote quoting on Windows CMD vs bash
- **stackoverflow.com/questions/64192561** — sha256sum availability in Git Bash confirmed
- **graphite.com/guides/git-change-home-directory-git-bash** — $HOME resolution in Git Bash
- **github.com/windos/burnttoast** — BurntToast PowerShell module for toast notifications

### Dropped
- **WSL-specific notify-send tools** (wsl-notify-send, notify-send-wsl, win_notify) — Not applicable; these require WSL, not Git Bash / MSYS2 native
- **shellmap.eversources.app** — Useful reference but secondary/aggregator; primary sources used instead
- **gnuwin32.sourceforge.net** — Obsolete (last updated ~2010); MSYS2/Git for Windows supersedes this

---

## Gaps

1. **fzf `--preview` terminal size on Windows** — It is unclear whether fzf correctly reports terminal dimensions to the preview subprocess on Windows Terminal. If chafa in preview mode receives incorrect `$FZF_PREVIEW_COLUMNS`/`$FZF_PREVIEW_LINES`, images may still be incorrectly sized even in symbol mode. Testing with a real setup would confirm.

2. **rofi / sentaku / tv on Windows** — These Linux-only GUI/TUI tools have no Windows equivalents; the script presumably guards against their absence. No research was done on replacing them (out of scope per task framing).

3. **mpv Windows binary source** — The research confirms the feature works but didn't identify the recommended Windows mpv download source (shinchiro builds vs. official). Users should use the shinchiro `mpv-x86_64` nightly builds from `sourceforge.net/projects/mpv-player-windows/`.

4. **`curl` / `jq` / `ffmpeg` on Windows** — Not researched in depth (all have well-known Windows builds via Scoop/winget/MSYS2 and are considered non-issues).
