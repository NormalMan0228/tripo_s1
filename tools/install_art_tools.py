"""Install verified official portable art tools without subscriptions or system changes."""
import hashlib
import json
from pathlib import Path
import time
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / ".tools"
REPORT = ROOT / "artifacts/detail-map-20261003"
PACKAGES = [
    {"name": "Material Maker", "version": "1.7", "dir": "material-maker-1.7",
     "url": "https://github.com/RodZill4/material-maker/releases/download/1.7/material_maker_1_7_windows.zip",
     "sha256": "deb4416bc939861d48097a866a8b2bf0363c29ff64874f2e04478658ff900808",
     "source": "https://github.com/RodZill4/material-maker/releases/tag/1.7"},
    {"name": "Krita", "version": "5.3.4", "dir": "krita-5.3.4",
     "url": "https://download.kde.org/stable/krita/5.3.4/krita-x64-5.3.4.zip",
     "source": "https://krita.org/en/download/"},
]


def install(package):
    dest = TOOLS / package["dir"]
    done = dest / "tripothon-install.json"
    if done.exists():
        return json.loads(done.read_text(encoding="utf-8"))
    archive = TOOLS / (package["dir"] + ".zip")
    if not archive.exists():
        part = archive.with_suffix(".partial")
        req = urllib.request.Request(package["url"], headers={"User-Agent": "Tripothon-art-tool-setup"})
        count, last = 0, 0
        with urllib.request.urlopen(req, timeout=90) as response, part.open("wb") as file:
            while chunk := response.read(1024 * 1024):
                file.write(chunk)
                count += len(chunk)
                if count - last > 20 * 1024 * 1024:
                    print(json.dumps({"tool": package["name"], "download_mb": round(count / 1048576)}), flush=True)
                    last = count
        part.replace(archive)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    expected = package.get("sha256")
    if expected and digest != expected:
        raise RuntimeError("official_archive_digest_mismatch")
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        for item in z.infolist():
            target = (dest / item.filename).resolve()
            if not target.is_relative_to(dest.resolve()):
                raise RuntimeError("unsafe_archive_member")
        z.extractall(dest)
    result = {"name": package["name"], "version": package["version"], "path": str(dest),
              "source": package["source"], "archive_sha256": digest,
              "official_digest_checked": bool(expected), "installed_at": time.time(),
              "executables": [str(p.relative_to(ROOT)) for p in dest.rglob("*.exe") if "uninstall" not in p.name.lower()]}
    done.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"tool": package["name"], "installed": True}), flush=True)
    return result


if __name__ == "__main__":
    REPORT.mkdir(parents=True, exist_ok=True)
    results = [install(p) for p in PACKAGES]
    (REPORT / "installed-tools.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2), flush=True)
