# exebox

> A declarative frontend for wine/proton — run Windows programs on Linux the way
> you run containers: one program, one box, one manifest.

**Three things, done well: install, manage, launch Windows `.exe`.**
No game-database, no store scraping, no hidden magic — if it's not in your
manifest, it doesn't happen.

## Highlights

- **Declarative manifests** (`game.yaml`, compose-style): engine, fake-C-drive
  (prefix), entry exe, cwd, env, DLL overrides, install steps — readable,
  diffable, git-friendly. Unknown fields are *errors*, not silently ignored.
- **Zero hidden parameters**: official Proton called directly (no protonfixes
  injecting flags by game ID), no `wine start` rewrites, and
  `launch --dry-run` prints the exact command + environment delta.
- **One box per program** — manifest, prefix, game files and logs in one
  directory. `rm -rf` the box and the program is *gone*.
- **Process-tree governance**: subreaper + signal forwarding + prefix-session
  tracking. Ctrl-C (or `kill`) reaps the whole wine tree; never touches your
  other running programs.
- **Prefix lifecycle**: `prefix reset` (nuke the fake C: and retry — the #1
  wine troubleshooting move), `prefix shell` (an interactive shell with the
  *exact* launch environment — a `docker exec` for wine).
- **doctor**: one-command health check with fix suggestions. Diagnose, never
  mutate.

## Install

Requires Python ≥3.13 and [uv](https://docs.astral.sh/uv/). This repo:

```bash
git clone https://github.com/dingiv/exebox && cd exebox
uv sync
uv run exebox --help
```

## Quick start

```bash
exebox install /path/to/setup.exe   # 8-step wizard (or hand-write game.yaml)
exebox list                         # everything at a glance
exebox list --protons               # engines found on this machine
exebox launch myapp                 # play / run
exebox launch myapp --dry-run       # audit: exact command + env
exebox launch myapp --bg            # background; exebox ps; kill <pid>
exebox doctor myapp                 # health check with suggestions
exebox prefix shell myapp           # drop into the box's environment
```

## Manifest example

```yaml
name: Mental Omega 3
exe: ./MentalOmegaClient.exe        # relative form — see notes
proton: Proton - Experimental       # fuzzy-resolved against installed engines
prefix: /home/you/Games/exebox/mo3/prefix
game_dir: /home/you/Games/exebox/mo3/prefix/pfx/drive_c/.../Mental Omega
path_append: [...]                  # prepend to PATH (mono Process.Start etc.)
install:
  source: /downloads/setup.exe
  args: ["/S"]                      # installer flags (NSIS-style)
  steps:
    - { type: reg_add, key: 'Software\\MyApp', value_name: InstallPath,
        value: 'C:\\MyApp', reg_arch: "32" }
```

Contracts learned the hard way (locked in by golden-snapshot tests):
exes inside the game dir are passed as `./relative` (absolute paths get quoted
by wine and break naive DRM-shell parsers); prefix version ratchet is guarded
(Steam-managed prefixes are never auto-upgraded); launcher-style bootstrappers
are tracked via prefix session until the real program exits.

## Docs

See `docs/` (Chinese): requirements, design, implementation plan, competitor
research, and battle-tested Proton internals (directory model, process trees,
diagnostics). English docs are on the v1.4 roadmap.

## License

MIT
