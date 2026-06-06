from dataclasses import dataclass
from unicodedata import normalize


@dataclass(frozen=True)
class CatalogItem:
    id: int
    name: str
    description: str
    size: tuple[str, ...]
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class CatalogMatch:
    item: CatalogItem
    size: str | None = None


CATALOG_ITEMS = (
    CatalogItem(
        id=101,
        description="Muçarela, calabresa fatiada e cebola fresca.",
        name="calabresa",
        size=("grande", "média"),
        aliases=(
            "calabresa",
            "grande de calabresa",
            "média de calabresa",
            "calabresa grande",
            "calabresa média",
            "cebola fresca",
            "calbresa fatiada",
        ),
    ),
    CatalogItem(
        id=102,
        description="Muçarela em dobro e molho de tomate.",
        name="muçarela",
        size=("grande", "média"),
        aliases=(
            "muçarela",
            "grande de muçarela",
            "média de muçarela",
            "muçarela grande",
            "muçarela média",
            "molho de tomate",
            "muçarela em dobro",
        ),
    ),
    CatalogItem(
        id=103,
        description="Muçarela, tomate fatiado, manjericão fresco e parmesão ralado.",
        name="marguerita",
        size=("grande", "média"),
        aliases=(
            "marguerita",
            "grande de marguerita",
            "média de marguerita",
            "marguerita grande",
            "marguerita média",
            "tomate fatiado",
            "manjericão fresco",
            "parmesão ralado",
        ),
    ),
)

CATALOG_QUERY_TERMS = (
    "pizza",
    "pizzas",
    "cardapio",
    "catalogo",
    "menu",
    "opcoes",
    "sabor",
    "sabores",
    "tamanho",
    "tamanhos",
)


def normalize_text(value: str) -> str:
    ascii_text = normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return ascii_text.lower().strip()


def find_catalog_size(message: str, item: CatalogItem) -> str | None:
    normalized_message = normalize_text(message)
    best: tuple[int, str] | None = None
    for size in item.size:
        normalized_size = normalize_text(size)
        if normalized_size in normalized_message:
            if best is None or len(normalized_size) > best[0]:
                best = (len(normalized_size), size)
    return best[1] if best else None


def find_catalog_item(message: str) -> CatalogMatch | None:
    normalized_message = normalize_text(message)
    best: tuple[int, CatalogItem] | None = None
    for item in CATALOG_ITEMS:
        for alias in item.aliases:
            normalized_alias = normalize_text(alias)
            if normalized_alias in normalized_message:
                if best is None or len(normalized_alias) > best[0]:
                    best = (len(normalized_alias), item)
    if best is None:
        return None
    item = best[1]
    return CatalogMatch(item=item, size=find_catalog_size(message, item))


def is_catalog_query(message: str) -> bool:
    normalized_message = normalize_text(message)
    return any(term in normalized_message for term in CATALOG_QUERY_TERMS)


def format_order_label(match: CatalogMatch) -> str:
    if match.size:
        return f"Pizza {match.size} de {match.item.name}"
    return f"Pizza de {match.item.name}"


def format_catalog_item(item: CatalogItem) -> str:
    sizes = " ou ".join(item.size)
    return f"{item.name} ({sizes}): {item.description}"


def format_catalog() -> str:
    return " ".join(format_catalog_item(item) for item in CATALOG_ITEMS)


def format_size_prompt(item: CatalogItem) -> str:
    sizes = " ou ".join(item.size)
    return f"Qual tamanho da pizza de {item.name}? Temos {sizes}."


def needs_size_selection(match: CatalogMatch) -> bool:
    return match.size is None and len(match.item.size) > 1
