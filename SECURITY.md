# Security policy

> **Where this applies.** This policy applies to the project's one official, write-enabled repository, which
> exists only on GitLab: <https://gitlab.com/Tyler-Meador/futaba-usb-driver>. Reports are taken there and
> nowhere else. The GitHub repository is a push-only mirror kept for visibility: it is overwritten from
> GitLab, and a report made on GitHub, by an issue or by private vulnerability reporting, is not seen.

## Supported versions

Only the latest release is supported. A fix ships as a new release; older versions are not patched.

| Version | Supported |
| --- | --- |
| [Latest release](https://gitlab.com/Tyler-Meador/futaba-usb-driver/-/releases/permalink/latest) | Yes |
| Anything older | No |

## Reporting a vulnerability

**Do not open a public issue.** Open a **confidential issue** on GitLab instead:

<https://gitlab.com/Tyler-Meador/futaba-usb-driver/-/issues/new?issue[confidential]=true>

Check that "This issue is confidential" is ticked before you submit. A
[confidential issue](https://docs.gitlab.com/user/project/issues/confidential_issues/) is visible only to
you and to the project's members.

Please include:

- the driver version (`futaba-rc-driver --version`), or the commit;
- the distribution and kernel (`uname -a`), and whether the driver came from a release archive or was run
  from source;
- the steps, and what an attacker gains;
- no live tokens: describe where a secret leaks instead of pasting it.

This is a spare-time project with one maintainer, so there is no guaranteed response time. You will get an
answer on the issue, the fix is named in the release notes, and you are credited there if you want to be.

## What counts

- `install.sh` or `uninstall.sh` doing anything as root beyond what it prints, or leaving a file behind
  that lets another local user gain root.
- Another local user, or a USB device, getting the driver to do more than it was started to do: run
  commands, write files outside its own directory, or signal a process it did not start.
- The scheduling capability on the installed executable (`cap_sys_nice`) being usable for anything other
  than raising the driver's own priority.
- A release archive on GitLab that does not match its published SHA256, or install instructions that fetch
  from anywhere other than the project's GitLab releases.
- A secret committed to the repository.

A wrong axis, a missed frame or a crash is an ordinary bug: file it as an ordinary issue.

## Known properties, not vulnerabilities

These are how the driver and its installer work. Plan around them rather than report them.

- **The udev rule opens whole vendor IDs, and `/dev/uinput`, to the logged-in user.** It covers `1008`
  (Futaba), `0925`, `04d8` and `1781` for the `plugdev` group and the active session. Any program running as
  you can then read those USB devices and create a virtual input device. A driver that runs without root
  needs that access.
- **The installer adds you to the `input` group**, and the uninstaller does not take you out again. Members
  of that group can read every input device on the machine, keyboards included.
- **The installed executable carries `cap_sys_nice`**, so that it can raise its own scheduling priority.
- **The single-instance lock is a TCP listener on `127.0.0.1:1962`.** Any local program that holds that port
  first stops the driver from starting.
- **The driver starts from your shell profile.** The installer adds a line to `~/.profile`, `~/.bashrc` and
  `~/.zshrc`, and writes its log to `~/.futaba-rc-driver-logs.txt`.
- **Run with `sudo`, the whole driver runs as root.** The installer exists so that it never has to.

Vulnerabilities in a transmitter, a receiver or their firmware belong with Futaba Corporation, not here.
