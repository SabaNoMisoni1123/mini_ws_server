"""設定ファイルを正として Firestore の情報元一覧を同期する。"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable

from .data_transfer import read_articles, write_articles


@dataclass(frozen=True)
class SiteDataDocument:
    """Firestore の siteData 文書と、その更新・削除用参照を保持する。"""

    document_id: str
    reference: object
    data: dict


@dataclass(frozen=True)
class SyncItem:
    """情報元1件の同期計画。"""

    site_id: str
    expected: dict | None
    current: SiteDataDocument | None
    changed_fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class SyncPlan:
    """Firestore に変更を加える前に確定した差分計画。"""

    additions: tuple[SyncItem, ...] = ()
    updates: tuple[SyncItem, ...] = ()
    unchanged: tuple[SyncItem, ...] = ()
    deletions: tuple[SyncItem, ...] = ()
    inconsistencies: tuple[str, ...] = ()


@dataclass
class SyncResult:
    """同期結果と CLI の終了判定に必要な集計を保持する。"""

    plan: SyncPlan
    applied: bool
    added: int = 0
    updated: int = 0
    deleted: int = 0
    backed_up_articles: int = 0
    failed_ids: list[str] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)
    site_results: dict[str, str] = field(default_factory=dict)
    backup_dir: Path | None = None

    @property
    def success(self) -> bool:
        """失敗した情報元またはデータ不整合がなければ成功とする。"""
        return not self.failed_ids and not self.plan.inconsistencies


class SourceSyncError(RuntimeError):
    """同期の安全条件を満たさない場合のエラー。"""


def build_sync_plan(sources: dict, documents: Iterable[SiteDataDocument]) -> SyncPlan:
    """設定順から期待値を作り、現在の siteData との差分を返す。"""
    expected_by_id: dict[str, dict] = {}
    inconsistencies: list[str] = []
    for number, (site_id, config) in enumerate(sources.items()):
        if not isinstance(config, dict) or "name" not in config or "url" not in config:
            inconsistencies.append(f"設定 {site_id}: name または url がありません")
            continue
        expected_by_id[site_id] = {
            "id": site_id,
            "name": config["name"],
            "url": config["url"],
            "no": number,
        }

    current_by_id: dict[str, SiteDataDocument] = {}
    for document in documents:
        site_id = document.data.get("id")
        if not isinstance(site_id, str) or not site_id.strip():
            inconsistencies.append(f"siteData 文書 {document.document_id}: id がありません")
            continue
        if site_id in current_by_id:
            previous = current_by_id[site_id]
            inconsistencies.append(
                f"siteData.id {site_id}: 文書 {previous.document_id} と "
                f"{document.document_id} で重複しています"
            )
            continue
        current_by_id[site_id] = document

    additions: list[SyncItem] = []
    updates: list[SyncItem] = []
    unchanged: list[SyncItem] = []
    for site_id, expected in expected_by_id.items():
        current = current_by_id.get(site_id)
        if current is None:
            additions.append(SyncItem(site_id, expected, None))
            continue
        changed_fields = tuple(
            field_name
            for field_name in ("name", "url", "no")
            if current.data.get(field_name) != expected[field_name]
        )
        item = SyncItem(site_id, expected, current, changed_fields)
        (updates if changed_fields else unchanged).append(item)

    deletions = [
        SyncItem(site_id, None, document)
        for site_id, document in current_by_id.items()
        if site_id not in expected_by_id
    ]
    return SyncPlan(
        additions=tuple(additions),
        updates=tuple(updates),
        unchanged=tuple(unchanged),
        deletions=tuple(deletions),
        inconsistencies=tuple(inconsistencies),
    )


class SourceSynchronizer:
    """差分表示、バックアップ検証、Firestore 反映を調整する。"""

    def __init__(
        self,
        repository: object,
        *,
        config_path: str | Path,
        now: Callable[[], datetime] | None = None,
        output: Callable[[str], None] = print,
    ):
        self.repository = repository
        self.config_path = Path(config_path)
        self._now = now or (lambda: datetime.now().astimezone())
        self._output = output

    def synchronize(
        self,
        sources: dict,
        *,
        apply: bool = False,
        confirm_delete: bool = False,
        backup_dir: str | Path | None = None,
        overwrite_backup: bool = False,
    ) -> SyncResult:
        """情報元設定と siteData を比較し、指定時だけ差分を反映する。"""
        started_at = self._now()
        plan = build_sync_plan(sources, self.repository.list_site_data())
        self._print_plan(plan)
        result = SyncResult(plan=plan, applied=apply)
        result.site_results.update(
            {item.site_id: "unchanged" for item in plan.unchanged}
        )

        if plan.inconsistencies:
            for index, message in enumerate(plan.inconsistencies, start=1):
                failure_id = f"data-integrity-{index}"
                result.failed_ids.append(failure_id)
                result.errors[failure_id] = message
                result.site_results[failure_id] = "failed"
            self._print_summary(result)
            return result
        if not apply:
            self._print_summary(result)
            return result
        if plan.deletions and not confirm_delete:
            raise SourceSyncError("削除対象があるため --confirm-delete が必要です。")

        backup_records: dict[str, dict] = {}
        if plan.deletions:
            destination = (
                Path(backup_dir)
                if backup_dir is not None
                else Path.cwd() / started_at.strftime("backup-%Y-%m-%d")
            )
            result.backup_dir = destination
            try:
                backup_records = self._backup_deletions(
                    plan.deletions, destination, overwrite_backup
                )
                result.backed_up_articles = sum(
                    record["article_count"] for record in backup_records.values()
                )
                self._write_manifest(
                    destination,
                    started_at,
                    backup_records,
                    result,
                    "backups_verified",
                )
            except Exception as exc:
                result.failed_ids.extend(item.site_id for item in plan.deletions)
                for item in plan.deletions:
                    result.errors[item.site_id] = f"バックアップ失敗: {exc}"
                    result.site_results[item.site_id] = "failed"
                    self._output(f"失敗: {item.site_id} (バックアップ失敗: {exc})")
                self._print_summary(result)
                return result

        for item in plan.additions:
            try:
                self.repository.add_site_data(item.expected)
                result.added += 1
                result.site_results[item.site_id] = "added"
                self._output(f"追加完了: {item.site_id}")
            except Exception as exc:
                self._record_failure(result, item.site_id, exc)
        for item in plan.updates:
            try:
                values = {
                    field_name: item.expected[field_name]
                    for field_name in ("name", "url", "no")
                }
                self.repository.update_site_data(item.current.reference, values)
                result.updated += 1
                result.site_results[item.site_id] = "updated"
                self._output(f"更新完了: {item.site_id}")
            except Exception as exc:
                self._record_failure(result, item.site_id, exc)
        for item in plan.deletions:
            try:
                self.repository.delete_site_articles(item.site_id)
            except Exception as exc:
                self._record_failure(result, item.site_id, exc)
                continue
            try:
                self.repository.delete_site_data(item.current.reference)
                result.deleted += 1
                result.site_results[item.site_id] = "deleted"
                self._output(f"削除完了: {item.site_id}")
            except Exception as exc:
                self._record_failure(result, item.site_id, exc)

        if result.backup_dir is not None:
            try:
                self._write_manifest(
                    result.backup_dir,
                    started_at,
                    backup_records,
                    result,
                    "completed" if result.success else "completed_with_errors",
                )
            except Exception as exc:
                self._record_failure(result, "manifest", exc)
        self._print_summary(result)
        return result

    def _backup_deletions(
        self,
        deletions: tuple[SyncItem, ...],
        destination: Path,
        overwrite: bool,
    ) -> dict[str, dict]:
        for item in deletions:
            if Path(item.site_id).name != item.site_id or item.site_id in {".", ".."}:
                raise SourceSyncError(f"バックアップに使えない情報元 ID です: {item.site_id}")
        target_paths = [destination / f"{item.site_id}.json" for item in deletions]
        target_paths.append(destination / "manifest.json")
        existing = [path for path in target_paths if path.exists()]
        if existing and not overwrite:
            names = ", ".join(path.name for path in existing)
            raise FileExistsError(f"既存バックアップを上書きできません: {names}")

        articles_by_id = {
            item.site_id: self.repository.list_articles(item.site_id) for item in deletions
        }
        destination.mkdir(parents=True, exist_ok=True)
        records: dict[str, dict] = {}
        temporary_paths: dict[str, Path] = {}
        try:
            for item in deletions:
                handle, temporary_name = tempfile.mkstemp(
                    prefix=f".{item.site_id}-", suffix=".json", dir=destination
                )
                os.close(handle)
                temporary_path = Path(temporary_name)
                temporary_paths[item.site_id] = temporary_path
                articles = articles_by_id[item.site_id]
                write_articles(temporary_path, articles)
                restored = read_articles(temporary_path)
                original_hashes = {article["hash"] for article in articles}
                restored_hashes = {article["hash"] for article in restored}
                if len(restored) != len(articles) or restored_hashes != original_hashes:
                    raise SourceSyncError(f"バックアップ検証に失敗しました: {item.site_id}")
                records[item.site_id] = {
                    "article_count": len(restored),
                    "file": f"{item.site_id}.json",
                }
            for site_id, temporary_path in temporary_paths.items():
                temporary_path.replace(destination / f"{site_id}.json")
            return records
        finally:
            for temporary_path in temporary_paths.values():
                temporary_path.unlink(missing_ok=True)

    def _write_manifest(
        self,
        destination: Path,
        started_at: datetime,
        backups: dict[str, dict],
        result: SyncResult,
        status: str,
    ) -> None:
        manifest = {
            "executed_at": started_at.isoformat(),
            "config_path": str(self.config_path.resolve()),
            "mode": "apply" if result.applied else "dry-run",
            "backup_site_ids": [item.site_id for item in result.plan.deletions],
            "backups": backups,
            "result": {
                "status": status,
                "added": result.added,
                "updated": result.updated,
                "deleted": result.deleted,
                "backed_up_articles": result.backed_up_articles,
                "failed_ids": result.failed_ids,
                "errors": result.errors,
                "site_results": result.site_results,
            },
        }
        path = destination / "manifest.json"
        temporary = destination / ".manifest.json.tmp"
        temporary.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)

    def _record_failure(self, result: SyncResult, site_id: str, exc: Exception) -> None:
        if site_id not in result.failed_ids:
            result.failed_ids.append(site_id)
        result.errors[site_id] = str(exc)
        result.site_results[site_id] = "failed"
        self._output(f"失敗: {site_id} ({exc})")

    def _print_plan(self, plan: SyncPlan) -> None:
        for item in plan.additions:
            self._output(f"追加: {item.site_id}")
        for item in plan.updates:
            self._output(f"更新: {item.site_id} ({', '.join(item.changed_fields)})")
        for item in plan.unchanged:
            self._output(f"変更なし: {item.site_id}")
        for item in plan.deletions:
            self._output(f"削除: {item.site_id}")
        for message in plan.inconsistencies:
            self._output(f"不整合: {message}")

    def _print_summary(self, result: SyncResult) -> None:
        plan = result.plan
        deletion_label = "削除完了数" if result.applied else "削除予定数"
        self._output(f"追加数: {result.added if result.applied else len(plan.additions)}")
        self._output(f"更新数: {result.updated if result.applied else len(plan.updates)}")
        self._output(f"変更なし数: {len(plan.unchanged)}")
        deletion_count = result.deleted if result.applied else len(plan.deletions)
        self._output(f"{deletion_label}: {deletion_count}")
        self._output(f"バックアップ済み記事数: {result.backed_up_articles}")
        self._output(f"失敗数: {len(result.failed_ids)}")
        if result.failed_ids:
            self._output(f"失敗した ID: {', '.join(result.failed_ids)}")
        if result.backup_dir is not None:
            self._output(f"バックアップ先: {result.backup_dir.resolve()}")
