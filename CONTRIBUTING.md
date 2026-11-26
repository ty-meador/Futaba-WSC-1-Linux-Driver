# Contributing

> **Where this applies.** This guide applies to the project's one official, write-enabled repository, which
> exists only on GitLab: <https://gitlab.com/Tyler-Meador/futaba-usb-driver>. Issues, merge requests and
> releases live there and nowhere else. The GitHub repository is a push-only mirror kept for visibility: it
> is overwritten from GitLab, and an issue or pull request opened anywhere but GitLab is not seen.

Thank you for looking. This is a small project with one maintainer; the notes below are what makes a
report or a change easy to take.

## Ways to help

- **Report what your transmitter did.** The driver is only tried on the hardware its users own, so a report
  from a model that is not in the README's list is worth a lot, whether it worked or not.
  [Open an issue](https://gitlab.com/Tyler-Meador/futaba-usb-driver/-/issues/new) with the "Bug" template.
- **Propose a change** with the "Proposal" template before writing anything larger than a fix, so the design
  is agreed before the code exists. A request to support another transmitter is a proposal too.
- **Send a fix** as a merge request on GitLab (below).
- **Correct the documentation.** A stale version number or a command that no longer works is a bug.

Security problems do not go in a public issue: see [`SECURITY.md`](SECURITY.md).

## What a change has to keep

These are the promises the [README](README.md) makes to the people who install the driver. A change that
breaks one is declined however well it works.

- **One command installs it.** A release is a standalone executable; nobody who installs it manages a Python
  environment or a package. A new dependency is bundled by the build, never left for the user to install.
- **It lives in the user's home directory.** `install.sh` runs as the regular user and asks for `sudo` only
  for the udev rule, the `uinput` module, the `input` group and the scheduling capability. A change that
  needs root for anything else says so, and says why, before the code is written.
- **The uninstaller takes away what the installer added.** Anything new in
  `tools/artifact-templates/scripts/install.sh` has its removal in `uninstall.sh` in the same change.
- **One process for each transmitter.** A device that fails must not take another one down with it.
- **The frame path stays constant time.** Work that can be done once, such as a calibration map, is done
  before the first frame and not on every frame.

## Setting up

```sh
sudo apt install build-essential python3-dev libusb-1.0-0-dev   # Debian and Ubuntu
python3 -m venv .venv
source .venv/bin/activate
pip install ".[dev]"
make build      # compiles the standalone executable with Nuitka
make test       # starts the built executable and prints its version
```

The [developer guide](developers_guide/README.md) has the packages for other distributions, the layout of the
repository and how the build, package and template steps work. The tools under `tools/` refuse to run outside
the virtual environment.

To run the driver from source against a transmitter, use `sudo ./run.sh` (the comment at the top of
[`run.sh`](run.sh) says why), with the same arguments as the installed command: `--calibrate`, `--setup`,
`--daemonize`, `--reload`, `--version`.

## Checked on hardware, or not

The project has **no automated test suite and no CI pipeline**. `make test` shows that the executable starts
and nothing more, so the only real check is a transmitter plugged into a computer. Say in the merge request
which of these is true:

- **Checked on hardware**: the transmitter and USB receiver, the distribution, and what you saw, for example
  the axes moving in `jstest /dev/input/js0` or in a simulator.
- **Not checked on hardware**: built only. That is fine, and it helps to know which changes still need a
  transmitter plugged in before they are released.

## Adding a transmitter

1. Add `src/Futaba/configs/_MODEL.json` and `src/Futaba/calibrations/_MODEL.json`. The leading underscore
   marks a default that ships with the driver; files without it are a user's own and are ignored by git.
2. Add the detection in `src/Futaba/Manager.py`.
3. Put the output of `lsusb -v` for the device in the merge request, so the next person can check the
   frame size and the channel count against it.

## Merge requests

1. Fork on GitLab and branch from `main`.
2. One change per merge request.
3. Leave the version in `pyproject.toml` and the `release/X.Y.Z` tags alone: the maintainer cuts releases
   with `make release` and `make publish`.
4. Fill in the merge request template and tick
   [Allow commits from members who can merge](https://docs.gitlab.com/user/project/merge_requests/allow_collaboration/).

The maintainer may adjust a change before merging it.

### Work written with an AI model

Contributions written with the help of an AI model are welcome. The bar does not move: you built it, you
read the diff, and you say honestly what was and was not checked on hardware.

## What must not be committed

The repository is public, and a pushed commit cannot be quietly taken back.

- No tokens (`GITLAB_TOKEN` or any other), `.env` files or personal paths.
- No calibration or config files of your own. They carry your receiver's serial number in the file name;
  only the underscore-prefixed defaults belong in the repository.
- No build output (`build/`, `dist/`), logs or pid files.
- Nothing that belongs to Futaba Corporation: no firmware, manuals or vendor software.

## Licence

The project is [MIT](LICENSE) licensed. By contributing you agree that your contribution is offered under
the same licence, and that you have the right to offer it.

## Conduct

Everyone taking part is expected to follow the [code of conduct](CODE_OF_CONDUCT.md).
