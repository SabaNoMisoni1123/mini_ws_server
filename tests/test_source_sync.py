import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from mini_ws_server.source_sync import (  # noqa: E402
    SiteDataDocument,
    SourceSyncError,
    SourceSynchronizer,
    build_sync_plan,
)


ARTICLE = {
    "url": "https://example.test/article",
    "title": "記事",
    "epoch": 100,
    "hash": "hash-1",
    "org": "省庁",
}


class FakeReference:
    def __init__(self, document_id):
        self.document_id = document_id


class FakeRepository:
    def __init__(self, sites=(), articles=None):
        self.sites = list(sites)
        self.articles = articles or {}
        self.added = []
        self.updated = []
        self.deleted_articles = []
        self.deleted_sites = []
        self.article_delete_failures = set()

    def list_site_data(self):
        return self.sites

    def list_articles(self, site_id):
        return [article.copy() for article in self.articles.get(site_id, [])]

    def add_site_data(self, data):
        self.added.append(data.copy())

    def update_site_data(self, reference, data):
        self.updated.append((reference.document_id, data.copy()))

    def delete_site_articles(self, site_id):
        self.deleted_articles.append(site_id)
        if site_id in self.article_delete_failures:
            raise RuntimeError("article deletion failed")
        return len(self.articles.get(site_id, []))

    def delete_site_data(self, reference):
        self.deleted_sites.append(reference.document_id)


def site(document_id, site_id, name="名前", url="https://example.test", no=0):
    return SiteDataDocument(
        document_id=document_id,
        reference=FakeReference(document_id),
        data={"id": site_id, "name": name, "url": url, "no": no},
    )


def synchronizer(repository, output=None):
    return SourceSynchronizer(
        repository,
        config_path=PROJECT_ROOT / "config" / "sources.json",
        now=lambda: datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc),
        output=output or (lambda _message: None),
    )


class SourceSyncTest(unittest.TestCase):
    def test_adds_source_only_in_config(self):
        repository = FakeRepository()
        sources = {"new": {"name": "新規", "url": "https://new.example.test"}}

        result = synchronizer(repository).synchronize(sources, apply=True)

        self.assertTrue(result.success)
        self.assertEqual(
            repository.added,
            [{"id": "new", "name": "新規", "url": "https://new.example.test", "no": 0}],
        )

    def test_name_url_and_no_are_updated_and_all_numbers_are_reassigned(self):
        sources = {
            "first": {"name": "新名称", "url": "https://new.example.test"},
            "second": {"name": "二番目", "url": "https://second.example.test"},
        }
        repository = FakeRepository(
            [
                site("doc-first", "first", name="旧名称", url="https://old.example.test", no=5),
                site("doc-second", "second", name="二番目", url="https://second.example.test", no=8),
            ]
        )

        result = synchronizer(repository).synchronize(sources, apply=True)

        self.assertEqual(result.updated, 2)
        self.assertEqual(
            repository.updated,
            [
                ("doc-first", {"name": "新名称", "url": "https://new.example.test", "no": 0}),
                ("doc-second", {"name": "二番目", "url": "https://second.example.test", "no": 1}),
            ],
        )

    def test_deleted_source_is_backed_up_then_articles_and_site_are_deleted(self):
        repository = FakeRepository(
            [site("old-doc", "old")],
            {"old": [ARTICLE]},
        )
        with tempfile.TemporaryDirectory() as directory:
            backup_dir = Path(directory) / "backup"
            result = synchronizer(repository).synchronize(
                {}, apply=True, confirm_delete=True, backup_dir=backup_dir
            )

            self.assertEqual(
                json.loads((backup_dir / "old.json").read_text(encoding="utf-8")),
                [ARTICLE],
            )
            manifest = json.loads((backup_dir / "manifest.json").read_text(encoding="utf-8"))

        self.assertTrue(result.success)
        self.assertEqual(result.backed_up_articles, 1)
        self.assertEqual(repository.deleted_articles, ["old"])
        self.assertEqual(repository.deleted_sites, ["old-doc"])
        self.assertEqual(manifest["backups"]["old"]["article_count"], 1)
        self.assertEqual(manifest["result"]["status"], "completed")
        self.assertEqual(manifest["result"]["site_results"], {"old": "deleted"})

    def test_empty_article_collection_is_backed_up_and_deleted(self):
        repository = FakeRepository([site("old-doc", "old")])
        with tempfile.TemporaryDirectory() as directory:
            backup_dir = Path(directory) / "backup"
            result = synchronizer(repository).synchronize(
                {}, apply=True, confirm_delete=True, backup_dir=backup_dir
            )
            self.assertEqual(json.loads((backup_dir / "old.json").read_text()), [])

        self.assertTrue(result.success)
        self.assertEqual(repository.deleted_sites, ["old-doc"])

    def test_invalid_backup_prevents_every_firestore_change(self):
        invalid = {key: value for key, value in ARTICLE.items() if key != "hash"}
        repository = FakeRepository(
            [site("old-doc", "old")],
            {"old": [invalid]},
        )
        sources = {"new": {"name": "新規", "url": "https://new.example.test"}}
        with tempfile.TemporaryDirectory() as directory:
            result = synchronizer(repository).synchronize(
                sources,
                apply=True,
                confirm_delete=True,
                backup_dir=Path(directory) / "backup",
            )

        self.assertFalse(result.success)
        self.assertEqual(repository.added, [])
        self.assertEqual(repository.updated, [])
        self.assertEqual(repository.deleted_articles, [])
        self.assertEqual(repository.deleted_sites, [])

    def test_article_delete_failure_keeps_corresponding_site_data(self):
        repository = FakeRepository([site("old-doc", "old")], {"old": [ARTICLE]})
        repository.article_delete_failures.add("old")
        with tempfile.TemporaryDirectory() as directory:
            result = synchronizer(repository).synchronize(
                {}, apply=True, confirm_delete=True, backup_dir=directory
            )

        self.assertFalse(result.success)
        self.assertEqual(repository.deleted_sites, [])

    def test_duplicate_or_missing_site_id_prevents_changes(self):
        missing = SiteDataDocument("missing-doc", FakeReference("missing-doc"), {"name": "なし"})
        repository = FakeRepository([site("one", "same"), site("two", "same"), missing])

        result = synchronizer(repository).synchronize(
            {"new": {"name": "新規", "url": "https://new.example.test"}}, apply=True
        )

        self.assertFalse(result.success)
        self.assertEqual(len(result.plan.inconsistencies), 2)
        self.assertEqual(repository.added, [])

    def test_dry_run_changes_neither_firestore_nor_backup_directory(self):
        repository = FakeRepository([site("old-doc", "old")], {"old": [ARTICLE]})
        with tempfile.TemporaryDirectory() as directory:
            backup_dir = Path(directory) / "not-created"
            result = synchronizer(repository).synchronize({}, backup_dir=backup_dir)
            self.assertFalse(backup_dir.exists())

        self.assertTrue(result.success)
        self.assertEqual(repository.deleted_articles, [])
        self.assertEqual(repository.deleted_sites, [])

    def test_existing_backup_requires_overwrite_option(self):
        repository = FakeRepository([site("old-doc", "old")], {"old": [ARTICLE]})
        with tempfile.TemporaryDirectory() as directory:
            backup_dir = Path(directory)
            (backup_dir / "old.json").write_text("old content", encoding="utf-8")
            failed = synchronizer(repository).synchronize(
                {}, apply=True, confirm_delete=True, backup_dir=backup_dir
            )
            self.assertEqual((backup_dir / "old.json").read_text(encoding="utf-8"), "old content")
            succeeded = synchronizer(repository).synchronize(
                {},
                apply=True,
                confirm_delete=True,
                backup_dir=backup_dir,
                overwrite_backup=True,
            )

        self.assertFalse(failed.success)
        self.assertTrue(succeeded.success)

    def test_delete_requires_explicit_confirmation(self):
        repository = FakeRepository([site("old-doc", "old")])

        with self.assertRaises(SourceSyncError):
            synchronizer(repository).synchronize({}, apply=True)

        self.assertEqual(repository.deleted_articles, [])

    def test_plan_reports_each_changed_field(self):
        plan = build_sync_plan(
            {"source": {"name": "新", "url": "https://new.example.test"}},
            [site("doc", "source", name="旧", url="https://old.example.test", no=2)],
        )

        self.assertEqual(plan.updates[0].changed_fields, ("name", "url", "no"))


if __name__ == "__main__":
    unittest.main()
