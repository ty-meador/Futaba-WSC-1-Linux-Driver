#!/usr/bin/env python3
"""Publish the packaged distributables as a GitLab release.

Uploads the archives and checksums created by package.py to the project's
generic package registry, then creates (or completes) the GitLab release for
the matching ``release/X.Y.Z`` tag with one asset link per file. The links are
what the install instructions download from:

    <project>/-/releases/release%2FX.Y.Z/downloads/<file name>

Requires a GitLab access token with the ``api`` scope in ``GITLAB_TOKEN``.
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request
from argparse import ArgumentParser
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit

from __config__ import (
    EXECUTABLE_NAME,
    PACKAGE_DIR,
    RELEASE_TAG_PREFIX,
    REPOSITORY,
    releaseDownloadUrl,
)
from util import runCommand

ARCHIVE_SUFFIXES = (".tar.gz", ".tar.xz", ".tar.gz.sha256", ".tar.xz.sha256")


def gitVersion() -> str:
    """Version of the checked out release tag, the same way package.py finds it."""
    described = runCommand("git describe --tags --always --dirty 2>/dev/null") or ""
    match = re.search(r"(\d+\.\d+\.\d+)", described)
    if not match:
        sys.exit("Error: could not determine the version from git tags. Use --version.")
    return match.group(1)


class GitLab:
    """Minimal GitLab REST client for one project."""

    def __init__(self, repositoryUrl: str, token: str) -> None:
        parts = urlsplit(str(repositoryUrl))
        self.api = f"{parts.scheme}://{parts.netloc}/api/v4"
        self.token = token
        # Resolve to the numeric id so renamed/moved project paths keep working
        projectPath = quote(parts.path.strip("/").removesuffix(".git"), safe="")
        self.project = f"{self.api}/projects/{self.request('GET', f'{self.api}/projects/{projectPath}')['id']}"

    def request(
        self,
        method: str,
        url: str,
        body: Any = None,
        upload: Path | None = None,
        missingOk: bool = False,
    ) -> Any:
        headers = {"PRIVATE-TOKEN": self.token}
        data: Any = None
        if upload is not None:
            data = upload.open("rb")
            headers["Content-Length"] = str(upload.stat().st_size)
            headers["Content-Type"] = "application/octet-stream"
        elif body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=600) as response:
                content = response.read()
                return json.loads(content) if content else None
        except urllib.error.HTTPError as e:
            if missingOk and e.code == 404:
                return None
            detail = e.read().decode(errors="replace")[:300]
            sys.exit(f"Error: {method} {url} failed: {e.code} {detail}")
        finally:
            if upload is not None:
                data.close()


def publish(
    version: str,
    artifactDir: Path,
    releasedAt: str | None,
    description: str | None,
    dryRun: bool,
) -> None:
    """Upload the distributables of a version and attach them to its release."""
    tag = f"{RELEASE_TAG_PREFIX}{version}"
    packageName = f"{EXECUTABLE_NAME}-{version}-linux-x86_64"
    files = [artifactDir / f"{packageName}{suffix}" for suffix in ARCHIVE_SUFFIXES]
    missing = [str(f) for f in files if not f.is_file()]
    if missing:
        sys.exit(
            f"Error: missing distributables: {', '.join(missing)}\nRun 'make package' first."
        )

    downloadUrl = releaseDownloadUrl(version)
    print(f"Release:  {tag}")
    print(f"Download: {downloadUrl}/{packageName}.tar.gz")
    if dryRun:
        for f in files:
            print(f"  would upload {f.name} ({f.stat().st_size} bytes)")
        return

    token = os.environ.get("GITLAB_TOKEN")
    if not token:
        sys.exit("Error: set GITLAB_TOKEN to a GitLab access token with the 'api' scope.")
    gitlab = GitLab(str(REPOSITORY), token)

    encodedTag = quote(tag, safe="")
    if not gitlab.request(
        "GET", f"{gitlab.project}/repository/tags/{encodedTag}", missingOk=True
    ):
        sys.exit(f"Error: tag {tag} is not on GitLab yet. Run: git push --tags")

    release = gitlab.request(
        "GET", f"{gitlab.project}/releases/{encodedTag}", missingOk=True
    )
    linked = {link["name"] for link in release["assets"]["links"]} if release else set()

    links = []
    for f in files:
        if f.name in linked:
            print(f"  {f.name} already attached, skipping")
            continue
        packageUrl = f"{gitlab.project}/packages/generic/{EXECUTABLE_NAME}/{version}/{f.name}"
        print(f"  uploading {f.name}")
        gitlab.request("PUT", packageUrl, upload=f)
        links.append(
            {
                "name": f.name,
                "url": packageUrl,
                "direct_asset_path": f"/{f.name}",
                "link_type": "other" if f.name.endswith(".sha256") else "package",
            }
        )

    if release is None:
        if description is None:
            description = (
                f"Futaba RC Driver {version} for Linux x86_64.\n\n"
                "```shell\n"
                f"wget {downloadUrl}/{packageName}.tar.gz && tar -xzf {packageName}.tar.gz"
                f" && cd {packageName} && ./install.sh\n"
                "```\n"
            )
        payload: dict[str, Any] = {
            "name": f"{EXECUTABLE_NAME} {version}",
            "tag_name": tag,
            "description": description,
            "assets": {"links": links},
        }
        if releasedAt:
            payload["released_at"] = releasedAt
        gitlab.request("POST", f"{gitlab.project}/releases", body=payload)
        print(f"Created release {tag}")
    else:
        for link in links:
            gitlab.request(
                "POST", f"{gitlab.project}/releases/{encodedTag}/assets/links", body=link
            )
        print(f"Updated release {tag}")


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--version", help="Version to publish (default: from the checked out git tag)."
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        help="Directory holding the archives and checksums (default: dist/<package name>).",
    )
    parser.add_argument(
        "--released-at",
        help="ISO 8601 release date, for backfilling a historical release.",
    )
    parser.add_argument("--description", help="Release notes (Markdown).")
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be published."
    )
    ARGS = parser.parse_args()

    print("Futaba RC Driver Release Publisher")
    print("=" * 40)
    releaseVersion = ARGS.version or gitVersion()
    publish(
        releaseVersion,
        ARGS.artifact_dir
        or PACKAGE_DIR / f"{EXECUTABLE_NAME}-{releaseVersion}-linux-x86_64",
        ARGS.released_at,
        ARGS.description,
        ARGS.dry_run,
    )
