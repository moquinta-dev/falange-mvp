from dataclasses import dataclass
from unicodedata import normalize


@dataclass(frozen=True)
class CatalogItem:
    id: str
    name: str
    aliases: tuple[str, ...]


CATALOG_ITEMS = (
    CatalogItem(
        id="pizza-calabresa-grande",
        name="Pizza grande de calabresa",
        aliases=("pizza", "calabresa", "pizza grande", "grande de calabresa"),
    ),
)


def normalize_text(value: str) -> str:
    ascii_text = normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return ascii_text.lower().strip()


def find_catalog_item(message: str) -> CatalogItem | None:
    normalized_message = normalize_text(message)
    for item in CATALOG_ITEMS:
        if any(normalize_text(alias) in normalized_message for alias in item.aliases):
            return item
    return None


def format_catalog() -> str:
    return ", ".join(item.name for item in CATALOG_ITEMS)
