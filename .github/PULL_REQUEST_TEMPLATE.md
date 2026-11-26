<!--
Where this applies: the project's one official, write-enabled repository exists only on GitLab.
This GitHub repository is a push-only mirror: a pull request opened here is not reviewed, and the branch it
targets is overwritten from GitLab.

Please open a merge request instead:
https://gitlab.com/Tyler-Meador/futaba-usb-driver/-/merge_requests/new

CONTRIBUTING.md has the rules; the checklist below is the same one the GitLab template carries.
-->

## What this changes

<!-- What someone with a transmitter now sees, in a sentence a user would understand. Link the GitLab issue. -->

## How it was checked

- [ ] `make build` and `make test` passed
- [ ] Checked on hardware (transmitter ..., distribution ..., what was seen), **or** not checked on hardware: built only

## Checklist

- [ ] One change
- [ ] Nothing new for a user to install by hand, and nothing new that needs `sudo` (or the description says what and why)
- [ ] Whatever `install.sh` now adds, `uninstall.sh` removes
- [ ] No version bump and no tag: the maintainer cuts releases
- [ ] No tokens, personal calibration or config files, build output, logs or personal paths
