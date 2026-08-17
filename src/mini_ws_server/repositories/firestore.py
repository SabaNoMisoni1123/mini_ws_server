"""Firestore への記事・サイト情報の永続化。"""

import logging
import os
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, firestore


LOGGER = logging.getLogger(__name__)
DEFAULT_CREDENTIAL_FILENAME = "ws-db-11235813-firebase-adminsdk-lh4mi-440ec2e232.json"


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

    def load_all_hashes(self, site_id: str) -> set[str]:
        """指定情報元に保存済みの全記事ハッシュを取得する。"""
        docs = self.db.collection(site_id).select(["hash"]).stream()
        return {doc.to_dict().get("hash") for doc in docs if doc.to_dict().get("hash")}

    def list_articles(self, site_id: str) -> list[dict]:
        """指定情報元の全記事を取得する。"""
        return [doc.to_dict() for doc in self.db.collection(site_id).stream()]

    def delete_site_articles(self, site_id: str) -> int:
        """指定情報元の記事ドキュメントをまとめて削除する。"""
        documents = list(self.db.collection(site_id).stream())
        for start in range(0, len(documents), 400):
            batch = self.db.batch()
            for document in documents[start : start + 400]:
                batch.delete(document.reference)
            batch.commit()
        return len(documents)

    def list_site_data(self) -> list:
        """siteData の全属性と更新・削除用の文書参照を取得する。"""
        from ..source_sync import SiteDataDocument

        return [
            SiteDataDocument(
                document_id=document.id,
                reference=document.reference,
                data=document.to_dict(),
            )
            for document in self.db.collection("siteData").stream()
        ]

    def add_site_data(self, data: dict) -> None:
        """同期済み属性を持つ siteData 文書を追加する。"""
        self.db.collection("siteData").add(data)

    @staticmethod
    def update_site_data(reference: object, data: dict) -> None:
        """既存 siteData 文書の同期対象属性を更新する。"""
        reference.update(data)

    @staticmethod
    def delete_site_data(reference: object) -> None:
        """既存 siteData 文書を削除する。"""
        reference.delete()

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
