"""Models package — data classes for type hinting."""
from dataclasses import dataclass
from typing import Optional


@dataclass
class Product:
    name: str
    price: float
    store: str
    url: str
    rating: float = 0.0
    reviews: int = 0
    image_url: str = ""
    currency: str = "EGP"
    pros: list = None
    cons: list = None
    specs: dict = None

    def __post_init__(self):
        if self.pros is None:
            self.pros = []
        if self.cons is None:
            self.cons = []
        if self.specs is None:
            self.specs = {}
