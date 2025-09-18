"""Data models for OLX scraper."""

from typing_extensions import Dict, List, Optional, TypedDict


class PriceParam(TypedDict):
    """Represents a price parameter from GraphQL response."""

    value: float
    currency: str


class GenericParam(TypedDict):
    """Represents a generic parameter from GraphQL response."""

    key: str
    label: str


class ParamValue(TypedDict):
    """Union type for parameter values."""

    value: Optional[float]
    currency: Optional[str]
    key: Optional[str]
    label: Optional[str]


class Param(TypedDict):
    """Represents a parameter from GraphQL response."""

    key: str
    value: ParamValue


class Category(TypedDict):
    """Represents a category from GraphQL response."""

    id: int
    type: str


class ListingData(TypedDict):
    """Represents a single listing from GraphQL response."""

    id: int
    title: str
    url: str
    category: Category
    params: List[Param]


class ListingSuccess(TypedDict):
    """Represents successful listing response from GraphQL."""

    __typename: str
    data: List[ListingData]


class GraphQLResponse(TypedDict):
    """Represents the complete GraphQL response."""

    data: Dict[str, ListingSuccess]


class OlxSearchResult(TypedDict):
    """Represents a search result listing from OLX."""

    title: str
    url: str
    description: Optional[str]
    price_value: Optional[float]
    price_currency: Optional[str]
    location: Optional[str]
    condition: Optional[str]
    category_id: Optional[int]
    category_type: Optional[str]
    listing_id: Optional[int]
