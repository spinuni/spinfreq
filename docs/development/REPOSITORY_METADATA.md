# GitHub About metadata

The intended public description, website and topics are versioned in
[`.github/repository.json`](../../.github/repository.json). This file alone
does not change GitHub's repository settings.

Review and apply using GitHub CLI on a machine with repository access:

```bash
python scripts/update_repository_about.py
python scripts/update_repository_about.py --apply
```

The first command only prints the metadata. The second updates the description,
website and topics on `spinuni/spinfreq` through the GitHub API. No web service
or simulation deployment is involved. During this implementation, API requests
returned `Forbidden`; the remote About update therefore remains pending.

Alternatively, use the gear beside **About** on the GitHub repository homepage
and enter the values from the JSON file. The website URL identifies the Pages
address; its metadata does not establish that Pages deployment has succeeded.
