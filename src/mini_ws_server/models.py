"""アプリケーション内で扱うデータの型定義。"""

from dataclasses import asdict, dataclass
import re
from typing import NotRequired, TypedDict
from urllib.parse import urlsplit, urlunsplit


_URL_PATTERN = re.compile(r"https?://[^\s]+")
_SECRET_PATTERN = re.compile(
    r"(?i)\b(token|secret|password|credential|api[_-]?key)\b(\s*[:=]\s*)([^\s,;]+)"
)


def safe_error_message(error: Exception) -> str:
    """例外文から URL のクエリと一般的な秘密値を除いて返す。"""
    message = str(error) or type(error).__name__

    def redact_url(match: re.Match[str]) -> str:
        parsed = urlsplit(match.group(0))
        query = "redacted" if parsed.query else ""
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, ""))

    message = _URL_PATTERN.sub(redact_url, message)
    return _SECRET_PATTERN.sub(r"\1\2[redacted]", message)


class Article(TypedDict):
    url: str
    title: str
    epoch: int
    hash: str
    org: str


class SiteConfig(TypedDict):
    name: str
    url: str
    useDefaultFunc: bool
    arg: dict
    funcID: NotRequired[str]


@dataclass(frozen=True)
class UpdateError:
    """更新中に発生した、外部へ公開可能な失敗情報。"""

    scope: str
    source_id: str | None
    message: str

    def to_dict(self) -> dict[str, str | None]:
        """JSON 化可能な辞書へ変換する。"""
        return asdict(self)


class UpdateResult(dict[str, int]):
    """従来の辞書 API を保ちつつ、集約した失敗も保持する。"""

    def __init__(
        self,
        added: dict[str, int] | None = None,
        errors: list[UpdateError] | None = None,
    ) -> None:
        super().__init__(added or {})
        self.errors = errors if errors is not None else []

    @property
    def added(self) -> dict[str, int]:
        """構造化結果用に、追加件数の辞書を返す。"""
        return self

    @property
    def success(self) -> bool:
        """失敗が一件もなければ ``True`` を返す。"""
        return not self.errors

    @property
    def status(self) -> str:
        """機械可読な全体状態を返す。"""
        if any(error.scope == "fatal" for error in self.errors):
            return "failed"
        return "completed" if self.success else "completed_with_errors"

    def to_dict(self) -> dict[str, object]:
        """標準出力へ書き出せる結果辞書へ変換する。"""
        return {
            "status": self.status,
            "added": dict(self),
            "errors": [error.to_dict() for error in self.errors],
        }
