"""Auto-publish a GitHub release as a new version of the FreeMoCap Zenodo record.

Replaces the manual "log into Zenodo and click Publish" step. For a given release
tag this script:

1. finds the newest published version under the FreeMoCap concept record
2. opens a "new version" draft on it via the Zenodo deposits API
3. uploads the GitHub source-code archive for the tag
4. fills in metadata (version, date, release notes, creators from CITATION.cff)
5. publishes the draft, so the concept DOI now resolves to this release

Requires a Zenodo personal access token in the ZENODO_ACCESS_TOKEN environment
variable. Create one at https://zenodo.org/account/settings/applications/tokens/new/
with the `deposit:write` and `deposit:actions` scopes.

Set ZENODO_DRY_RUN=1 to do everything except the final publish.
"""

import html
import os
import sys
from datetime import datetime, timezone

import requests
import yaml

ZENODO_API = "https://zenodo.org/api"
CONCEPT_REC_ID = os.environ.get("ZENODO_CONCEPT_REC_ID", "7233713")
CONCEPT_DOI = f"10.5281/zenodo.{CONCEPT_REC_ID}"
RECORD_TITLE = "FreeMoCap: A free, open source markerless motion capture system"
LICENSE_ID = "agpl-3.0-or-later"
MAX_DESCRIPTION_CHARS = 20000


def die(message, response=None):
    if response is not None:
        message = f"{message}\n  HTTP {response.status_code}: {response.text[:2000]}"
    raise SystemExit(message)


def zenodo(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def github_release_notes(repo, tag, gh_token):
    headers = {"Authorization": f"Bearer {gh_token}"} if gh_token else {}
    response = requests.get(
        f"https://api.github.com/repos/{repo}/releases/tags/{tag}", headers=headers, timeout=60
    )
    if response.status_code != 200:
        return ""
    return response.json().get("body") or ""


def latest_release_tag(repo, gh_token):
    headers = {"Authorization": f"Bearer {gh_token}"} if gh_token else {}
    response = requests.get(
        f"https://api.github.com/repos/{repo}/releases/latest", headers=headers, timeout=60
    )
    if response.status_code == 200:
        return response.json().get("tag_name")
    response = requests.get(
        f"https://api.github.com/repos/{repo}/releases?per_page=1", headers=headers, timeout=60
    )
    if response.status_code == 200 and response.json():
        return response.json()[0].get("tag_name")
    return None


def latest_version_recid(token):
    response = requests.get(
        f"{ZENODO_API}/records/{CONCEPT_REC_ID}", headers=zenodo(token), timeout=60
    )
    if response.status_code != 200:
        die(f"Could not resolve Zenodo concept record {CONCEPT_REC_ID}", response)
    return response.json()["id"]


def load_creators():
    cff_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..", "CITATION.cff"
    )
    try:
        with open(cff_path, encoding="utf-8") as cff_file:
            cff = yaml.safe_load(cff_file)
    except FileNotFoundError:
        die(f"CITATION.cff not found at {cff_path}")
    creators = []
    for author in cff.get("authors", []):
        creator = {
            "name": f"{author.get('family-names', '')}, {author.get('given-names', '')}".strip(" ,")
        }
        orcid = (author.get("orcid") or "").replace("https://orcid.org/", "")
        if orcid:
            creator["orcid"] = orcid
        creators.append(creator)
    if not creators:
        die("No authors found in CITATION.cff")
    return creators


def main():
    token = os.environ.get("ZENODO_ACCESS_TOKEN")
    if not token:
        die("ZENODO_ACCESS_TOKEN is not set (see the module docstring for how to create one)")
    repo = os.environ.get("GITHUB_REPOSITORY", "freemocap/freemocap")
    tag = os.environ.get("RELEASE_TAG")
    if not tag:
        tag = latest_release_tag(repo, os.environ.get("GH_TOKEN", ""))
        if not tag:
            die("RELEASE_TAG is not set and no releases were found on the repository")
        print(f"  RELEASE_TAG not set - using the most recent release: {tag}")
    repo_name = repo.split("/")[-1]
    dry_run = os.environ.get("ZENODO_DRY_RUN", "") == "1"

    print(f"Publishing release {tag} of https://github.com/{repo} to Zenodo under {CONCEPT_DOI}")
    headers = zenodo(token)

    latest_recid = latest_version_recid(token)
    print(f"  newest published version is record {latest_recid}")

    response = requests.get(
        f"{ZENODO_API}/deposit/depositions/{latest_recid}", headers=headers, timeout=60
    )
    if response.status_code != 200:
        die(f"Could not fetch the published Zenodo deposit {latest_recid}", response)
    latest_draft_url = response.json().get("links", {}).get("latest_draft")

    if latest_draft_url:
        print("  an unpublished new version draft already exists - reusing it")
    else:
        print("  opening a new version draft")
        response = requests.post(
            f"{ZENODO_API}/deposit/depositions/{latest_recid}/actions/newversion",
            headers=headers,
            timeout=60,
        )
        if response.status_code != 201:
            die(f"Failed to create a new version draft on Zenodo record {latest_recid}", response)
        latest_draft_url = response.json().get("links", {}).get("latest_draft")
        if not latest_draft_url:
            die("Zenodo did not return a 'latest_draft' link", response)

    response = requests.get(latest_draft_url, headers=headers, timeout=60)
    if response.status_code != 200:
        die("Failed to fetch the new version draft", response)
    draft = response.json()
    draft_id = draft["id"]

    for existing_file in draft.get("files", []):
        requests.delete(
            f"{ZENODO_API}/deposit/depositions/{draft_id}/files/{existing_file['id']}",
            headers=headers,
            timeout=60,
        )

    source_zip_url = f"https://github.com/{repo}/archive/refs/tags/{tag}.zip"
    print(f"  downloading {source_zip_url}")
    response = requests.get(source_zip_url, timeout=900)
    if response.status_code != 200:
        die(f"Failed to download source archive {source_zip_url}", response)
    file_name = f"{repo_name}-{tag}.zip"
    response = requests.put(
        f"{draft['links']['bucket']}/{file_name}",
        data=response.content,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/octet-stream"},
        timeout=1800,
    )
    if response.status_code not in (200, 201):
        die("Failed to upload the source archive to Zenodo", response)
    print(f"  uploaded {repo_name}-{tag}.zip ({response.json().get('size', '?')} bytes)")

    notes = html.escape(github_release_notes(repo, tag, os.environ.get("GH_TOKEN", "")))
    notes = notes.replace("\r\n", "\n").replace("\n", "<br/>")[:MAX_DESCRIPTION_CHARS]
    metadata = {
        "title": RECORD_TITLE,
        "upload_type": "software",
        "publication_date": datetime.now(timezone.utc).date().isoformat(),
        "creators": load_creators(),
        "description": notes or f"Release {tag} of https://github.com/{repo}",
        "version": tag,
        "license": {"id": LICENSE_ID},
        "access_right": "open",
        "related_identifiers": [
            {
                "identifier": f"https://github.com/{repo}/tree/{tag}",
                "relation": "isSupplementTo",
                "resource_type": "software",
            }
        ],
    }
    response = requests.put(
        f"{ZENODO_API}/deposit/depositions/{draft_id}",
        json={"metadata": metadata},
        headers=headers,
        timeout=60,
    )
    if response.status_code != 200:
        die("Failed to update the draft's metadata", response)

    if dry_run:
        print(f"  ZENODO_DRY_RUN is set - draft {draft_id} is fully staged but NOT published")
        print(f"  review it at {draft['links'].get('html', 'https://zenodo.org/deposit')}")
        return

    response = requests.post(
        f"{ZENODO_API}/deposit/depositions/{draft_id}/actions/publish", headers=headers, timeout=300
    )
    if response.status_code != 202:
        die("Failed to publish the new version", response)

    published = response.json()
    print(f"  published version DOI: {published.get('doi')}")
    print(f"  concept DOI (always resolves to the newest version): {CONCEPT_DOI}")


if __name__ == "__main__":
    try:
        main()
    except requests.RequestException as error:
        sys.exit(f"Network error talking to Zenodo/GitHub: {error}")
