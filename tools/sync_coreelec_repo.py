"""Publish the upstream Omega ARMv7 release for CoreELEC builds that only recognize the 'linux' platform."""

import argparse
import hashlib
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.request import urlopen

from build_kodi_repo import (
    ADDON_ID,
    REPO_ROOT,
    SITE_URL,
    RepoError,
    deterministic_zip,
    metadata_element,
    pvr_api_major,
    write_index,
)

REPO_ID = "repository.dispatcharr-coreelec-omega"
INDEX_URL = SITE_URL + "kodi21/addons.xml"
ARM_PACKAGE = re.compile(
    rf"(?P<release>\d+\.\d+\.\d+)-Omega/addon-{re.escape(ADDON_ID)}-(?P=release)-coreelec-armv7\.zip"
)


def coreelec_entry(index, checksum):
    if checksum.split()[:1] != [hashlib.sha256(index).hexdigest()]:
        raise RepoError("upstream Omega index checksum mismatch")
    matches = []
    for entry in ET.fromstring(index).findall("addon"):
        if entry.get("id") != ADDON_ID:
            continue
        meta = metadata_element(entry)
        match = ARM_PACKAGE.fullmatch(meta.findtext("path", ""))
        if not match:
            continue
        package_version = re.escape(match["release"]) + r"\.\d+"
        if pvr_api_major(entry) != 8 or not re.fullmatch(package_version, entry.get("version", "")):
            raise RepoError("CoreELEC package has an unexpected Kodi API or package version")
        platform = meta.find("platform")
        if platform is None or platform.text not in ("linux-armv7", "linux"):
            raise RepoError("CoreELEC package has an unexpected platform")
        platform.text = "linux"
        matches.append(entry)
    if len(matches) != 1:
        raise RepoError(f"expected one Omega CoreELEC ARMv7 package, found {len(matches)}")
    return matches[0]


def build(output):
    with urlopen(INDEX_URL, timeout=30) as response:
        index = response.read()
    with urlopen(INDEX_URL + ".sha256", timeout=30) as response:
        checksum = response.read().decode("ascii")
    entry = coreelec_entry(index, checksum)
    ET.indent(entry)
    directory = output / "index"
    directory.mkdir(parents=True, exist_ok=True)
    write_index(directory, [entry])

    manifest = (REPO_ROOT / "kodi-repository" / REPO_ID / "addon.xml").read_text(encoding="utf-8").encode("utf-8")
    version = ET.fromstring(manifest).attrib["version"]
    archive = output / f"{REPO_ID}-{version}.zip"
    deterministic_zip(archive, {REPO_ID + "/": b"", REPO_ID + "/addon.xml": manifest}, 315532800)
    print(f"{archive.name} offers {ADDON_ID} {entry.attrib['version']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    try:
        build(parser.parse_args().output)
    except (RepoError, OSError, ET.ParseError) as error:
        sys.exit(str(error))
