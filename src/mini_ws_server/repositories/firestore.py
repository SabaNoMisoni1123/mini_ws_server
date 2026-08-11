"""Firestore への記事・サイト情報の永続化。"""

import logging
import os
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, firestore


LOGGER = logging.getLogger(__name__)
DEFAULT_CREDENTIAL_FILENAME = "ws-db-11235813-firebase-adminsdk-lh4mi-50c38e64b5.json"


class FirestoreRepository:
    """既存の Firestore コレクション構造を扱うリポジトリ。"""

    def __init__(self, credential_path: str | Path | None = None):
        path = Path(
            credential_path
            or os.environ.get("FIREBASE_ADMIN_SDK")
            or DEFAULT_CREDENTIAL_FILENAME
        )
        if not path.is_absolute():
            path = Path(__file__).resolve().parents[3] / path

        if not firebase_admin._apps:
            credential = credentials.Certificate(str(path))
            firebase_admin.initialize_app(credential)
        self.db = firestore.client()

    def load_current_hashes(self, site_id: str) -> set[str]:
        try:
            docs = (
                self.db.collection(site_id)
                .order_by("epoch", direction=firestore.Query.DESCENDING)
                .limit(50)
                .select(["hash"])
                .stream()
            )
            return {doc.to_dict().get("hash") for doc in docs if doc.to_dict().get("hash")}
        except Exception:
            LOGGER.exception("Failed to load current hashes: %s", site_id)
            return set()

    def add_article(self, site_id: str, item: dict) -> None:
        self.db.collection(site_id).add(item)

    def update_last_run(self, epoch: int) -> None:
        self.db.collection("timeLog").document("lastTime").update({"lastTimeEpoch": epoch})

    def add_sites(self, site_dict: dict) -> int:
        docs = self.db.collection("siteData").select(["id"]).stream()
        current_ids = {doc.to_dict().get("id") for doc in docs if doc.to_dict().get("id")}
        number = len(current_ids)
        added = 0
        for site_id, config in site_dict.items():
            if site_id in current_ids:
                LOGGER.info("Already added: %s", site_id)
                continue
            self.db.collection("siteData").add(
                {"id": site_id, "no": number, "name": config["name"], "url": config["url"]}
            )
            number += 1
            added += 1
        return added
