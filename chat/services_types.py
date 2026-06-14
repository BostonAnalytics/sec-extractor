from dataclasses import dataclass


@dataclass
class Snippet:
    item_code: str
    title: str
    text: str
    score: float
