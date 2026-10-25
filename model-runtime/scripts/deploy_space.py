"""Upload the trusted main-branch source to an existing private Docker Space."""

import os
from pathlib import Path

from huggingface_hub import HfApi


def main():
    token = os.environ.get("HF_TOKEN")
    repo_id = os.environ.get("HF_SPACE_ID")
    if not token or not repo_id:
        raise SystemExit(
            "HF_TOKEN and HF_SPACE_ID must be configured as protected GitHub secrets."
        )

    api = HfApi(token=token)
    info = api.repo_info(repo_id=repo_id, repo_type="space")
    if not info.private:
        raise SystemExit("Refusing deployment: the target Space is not Private.")
    if info.sdk != "docker":
        raise SystemExit(
            "Refusing deployment: the target Space does not use Docker SDK."
        )

    commit = api.upload_folder(
        repo_id=repo_id,
        repo_type="space",
        folder_path=str(Path(__file__).resolve().parents[1]),
        commit_message="Deploy RANGKUL AI runtime from trusted main branch",
        token=token,
        ignore_patterns=[
            ".git/**",
            ".github/**",
            ".packages/**",
            ".pytest_cache/**",
            ".ruff_cache/**",
            ".venv/**",
            "work/**",
            "__pycache__/**",
            "**/__pycache__/**",
            "tests/**",
            "benchmarks/**",
        ],
    )
    print(f"Uploaded Space revision {commit.oid}")


if __name__ == "__main__":
    main()
