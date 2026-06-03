# ytsurf

YouTube in your terminal. Clean and distraction-free.
<p align="center">
  <a href="https://discord.gg/z6u6zwwedz" target="_blank" rel="noopener noreferrer">
    <img src="https://img.shields.io/badge/Discord-Join%20the%20community-5865F2?logo=discord&logoColor=white" alt="Join our Discord" />
  </a>
</p>
<p align="center">
  <img width="720" alt="demo" src="https://github.com/user-attachments/assets/0771f53b-ad16-41a2-9938-9aaaf0eaa1ae" />
</p>


## Features

- Search, stream, or download any YouTube video from your terminal
- Audio-only playback & downloads
- Interactive format/quality selection when playing or downloading
- Video queueing — build a queue across searches, then play or download the whole batch
- Local playlist save/load — save a queue as a named playlist and replay it later
- Syncplay support — watch videos together in sync with friends
- Playback history with quick re-play
- Channel subscriptions with a personalised feed
- Import subscriptions from your YouTube account
- Thumbnail previews in the fzf picker (via chafa)
- Copy short YouTube URLs to clipboard or print them
- Adjustable search result limit
- Custom download directory
- Self-update (`--update`) for manual installations
- External config file — set your defaults once
- **Windows support** via Git Bash / MSYS2


| Selector          | Features                                        | Best For                                        | Platform         |
| ----------------- | ----------------------------------------------- | ----------------------------------------------- | ---------------- |
| **fzf** (default) | Terminal-based, thumbnail previews, lightweight | Most users (fast + previews)                    | Linux, macOS, Windows |
| **rofi**          | GUI menu, keyboard-driven, clean look           | Users who prefer a graphical menu               | Linux only       |
| **sentaku**       | Very minimal, no previews                       | Systems without Go/`fzf` support                | Linux, macOS     |
| **tv**            | Terminal-based, similar to *telescope.nvim*     | Users who want a fancier terminal-based picker  | Linux, macOS     |


## Installation

### Windows (Git Bash / MSYS2)

ytsurf runs on Windows via **Git Bash** (bundled with [Git for Windows](https://gitforwindows.org/)) or **MSYS2**. **Windows Terminal** is strongly recommended for correct thumbnail preview rendering.

**1. Install dependencies — run in PowerShell:**

```powershell
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser -Force
irm get.scoop.sh | iex

scoop install main/yt-dlp main/jq main/curl main/fzf main/mpv main/ffmpeg
```

For thumbnail previews (optional):

```powershell
scoop bucket add extras
scoop install extras/chafa
```

For desktop toast notifications (optional):

```powershell
Install-Module -Name BurntToast -Scope CurrentUser
```

**2. Install ytsurf — run in Git Bash:**

```bash
mkdir -p ~/bin
curl -o ~/bin/ytsurf https://raw.githubusercontent.com/ppaauuoo/ytsurf/main/ytsurf.sh
chmod +x ~/bin/ytsurf
```

No PATH changes needed — Git Bash automatically includes `~/bin`. Restart Git Bash, then run `ytsurf`.

**Windows notes:**
- Config and data live in `~/.config/ytsurf/` → `C:\Users\<you>\.config\ytsurf\`
- `--rofi` is not supported on Windows (rofi requires X11)
- Thumbnail previews automatically use Unicode symbols mode; sixel mode is unavailable in Windows Terminal
- `perl` is bundled with Git for Windows — no separate install needed
- Run inside **Windows Terminal** for best results; standalone mintty may have fzf preview colour issues

### Linux / macOS (curl)

```bash
mkdir -p ~/bin
curl -o ~/bin/ytsurf https://raw.githubusercontent.com/ppaauuoo/ytsurf/main/ytsurf.sh
chmod +x ~/bin/ytsurf
```

`~/bin` is usually in PATH already. If not, add `export PATH="$HOME/bin:$PATH"` to your `~/.bashrc` or `~/.zshrc`.

### Arch Linux (AUR)

> Installs the upstream release — does not include Windows support.

```bash
yay -S ytsurf
# or
paru -S ytsurf
```

### Homebrew

> Installs the upstream release — does not include Windows support.

```bash
brew tap stan-breaks/ytsurf https://github.com/stan-breaks/ytsurf
brew install stan-breaks/ytsurf/ytsurf
```

### NixOS (system-wide, flakes)

> Installs the upstream release — does not include Windows support.

In your `flake.nix`:

```nix
{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    ytsurf.url = "github:Stan-breaks/ytsurf";
  };

  outputs = { self, nixpkgs, ytsurf, ... }:
  let
    system = "x86_64-linux";
  in {
    nixosConfigurations.thanaros = nixpkgs.lib.nixosSystem {
      inherit system;
      modules = [
        ({ pkgs, ... }: {
          nixpkgs.overlays = [
            ytsurf.overlays.default
          ];

          environment.systemPackages = with pkgs; [
            ytsurf
          ];
        })
      ];
    };
  };
}
```


## Dependencies

| Dependency | Required | Notes |
| ---------- | -------- | ----- |
| `bash`     | ✅ | 4.0+ recommended; macOS ships 3.2, Homebrew bash fixes this |
| `yt-dlp`   | ✅ | Video fetching and streaming |
| `mpv`      | ✅ | Playback |
| `jq`       | ✅ | JSON parsing |
| `curl`     | ✅ | HTTP requests |
| `perl`     | ✅ | HTML extraction (bundled with Git for Windows) |
| `ffmpeg`   | ✅ | Audio remuxing for downloads |
| `fzf`      | ✅* | Default interactive picker (*one of fzf/rofi/sentaku required) |
| `chafa`    | ⚡ Optional | Thumbnail previews in fzf; falls back gracefully if absent |
| `rofi`     | ⚡ Optional | Alternative GUI picker (Linux only) |
| `sentaku`  | ⚡ Optional | Minimal picker for systems without Go/fzf |
| `syncplay` | ⚡ Optional | Co-watching with friends (`--syncplay`) |

**Arch Linux:**

```bash
sudo pacman -S yt-dlp jq curl mpv fzf chafa rofi ffmpeg perl
```

**macOS (Homebrew):**

```bash
brew install yt-dlp jq curl mpv fzf chafa ffmpeg perl
```


## Usage

```
USAGE:
  ytsurf [OPTIONS] [QUERY]

OPTIONS:
  --audio             Play/download audio-only version
  --download, -d      Download instead of playing
  --format, -f        Interactively choose format/resolution
  --queue, -q         Add videos to a queue; play or download the whole batch
  --playlist          Play a saved local playlist
  --watch, -w         Watch video immediately, skipping the action menu
  --syncplay          Watch YouTube with friends in sync
  --history           Show and replay from viewing history
  --feed, -F          View videos from your subscribed channels
  --subscribe, -s     Add a channel to subscriptions
  --unsubscribe       Remove a channel from subscriptions
  --import-subs       Import subscriptions from your YouTube account
  --copy-url          Copy or print the short YouTube URL
  --rofi              Use rofi instead of fzf (Linux only)
  --sentaku           Use sentaku instead of fzf
  --tv                Use tv instead of fzf
  --limit <N>         Number of search results (default: 15)
  --block             Use chafa block/Unicode mode instead of sixel
  --edit, -e          Open the config file in your editor
  --debug             Enable debug logging to ~/.cache/ytsurf/ytsurf.log
  --update            Self-update the script (manual installs only)
  --version, -V       Show version
  --help, -h          Show this help message

EXAMPLES:
  ytsurf lo-fi study mix
  ytsurf --audio orchestral soundtrack
  ytsurf --download --format jazz piano
  ytsurf --queue                         # build a queue interactively
  ytsurf --history
  ytsurf --feed
```

Run `ytsurf` without arguments to enter interactive mode.


## Configuration

Config lives at `~/.config/ytsurf/config`. CLI flags always override config values.

```bash
# ~/.config/ytsurf/config

# Number of search results to show
#limit=15

# Always use audio-only mode
#audio_only=false

# Use rofi instead of fzf (Linux only)
#use_rofi=false

# Use sentaku instead of fzf
#use_sentaku=false

# Use tv instead of fzf
#use_tv=false

# Default to download mode
#download_mode=false

# Custom download directory
#download_dir="$HOME/Downloads"

# Maximum history entries to keep
#max_history_entries=100

# Editor for --edit
#editor="nvim"

# Player binary (mpv or iina)
#player="mpv"

# Desktop notifications (true/false)
#notify=true

# Use chafa block/Unicode mode instead of sixel
#chafa_block_mode=false
```


## Troubleshooting

### mpv doesn't play the selected video

Some systems have mpv configured to use `youtube-dl` instead of `yt-dlp`, which causes ytsurf to show "playing…" without starting playback.

**Fix — create a symlink:**

```bash
sudo ln -s /usr/bin/yt-dlp /usr/local/bin/youtube-dl
```

### No thumbnail previews

Thumbnails require `chafa`. Install it and re-run ytsurf.

If you're on Windows and thumbnails look wrong, run with `--block` to force Unicode symbols mode:

```bash
ytsurf --block lo-fi study mix
```

### Windows: fzf preview colours look wrong

Run ytsurf inside **Windows Terminal** (not the standalone Git Bash / mintty window). Windows Terminal supports 24-bit colour; mintty's fzf preview pane has known ANSI issues.

### Windows: `--rofi` exits with an error

`rofi` requires X11 and is not available on Windows. Use the default `fzf` picker instead (no flag needed).


## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md).
Check out [FUTURE_FEATURES.md](FUTURE_FEATURES.md) for upcoming ideas.


## License

Released under the [GNU General Public License v3.0](LICENSE).


## Star History

<a href="https://www.star-history.com/#Stan-breaks/ytsurf&Date">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=Stan-breaks/ytsurf&type=Date&theme=dark" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=Stan-breaks/ytsurf&type=Date" />
   <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=Stan-breaks/ytsurf&type=Date" />
 </picture>
</a>
