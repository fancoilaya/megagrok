# services/grokpedia_service.py
"""
Grokpedia Service
Loads and serves Grokpedia facts from assets/grokpedia/grokpedia.json.

Provides:
 - get_random(category=None)
 - get_categories()
 - Optional: get_fact_by_id(id)

This module is synchronous and TeleBot-compatible.
"""

import json
import os
import random
import threading
from typing import Optional, List, Dict

# Path to JSON file
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GROKPEDIA_PATH = os.path.join(ROOT_DIR, "assets", "grokpedia", "grokpedia.json")

# Avoid repeat facts
RECENT_BUFFER_SIZE = 20


class GrokpediaService:
    def __init__(self, json_path: str):
        self.json_path = json_path

        # internal storage
        self._facts: List[Dict] = []
        self._categories: List[str] = []

        # recent fact IDs to avoid repeats
        self._recent: List[int] = []

        # lock for thread safety (scheduler + command calls)
        self._lock = threading.Lock()

        self._load_json()

    # -----------------------------------------------------
    # JSON Loader
    # -----------------------------------------------------
    def _load_json(self):
        if not os.path.exists(self.json_path):
            raise RuntimeError(f"Grokpedia JSON file not found: {self.json_path}")

        with open(self.json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self._facts = data.get("facts", [])
        self._categories = data.get("categories", [])

        if not self._facts:
            raise RuntimeError("Grokpedia JSON contains no facts.")

    # -----------------------------------------------------
    # Public API
    # -----------------------------------------------------

    def get_categories(self) -> List[str]:
        """Return a list of category names."""
        return list(self._categories)

    def get_random(self, category: Optional[str] = None) -> Dict:
        """
        Returns a random fact, optionally filtered by category.
        Avoids the most recent N facts.
        """
        with self._lock:
            pool = self._facts

            # Filter by category if given
            if category:
                category = category.lower().strip()
                if category not in self._categories:
                    raise ValueError(f"Unknown category: {category}")
                pool = [f for f in self._facts if f.get("category") == category]

            if not pool:
                raise RuntimeError("No facts available in selected category.")

            # Avoid repeats
            non_recent = [f for f in pool if f.get("id") not in self._recent]
            choices = non_recent if non_recent else pool  # fallback if exhausted

            fact = random.choice(choices)
            self._add_to_recent(fact.get("id"))
            return fact

    def _add_to_recent(self, fact_id: int):
        """Track last N fact IDs to avoid repetition."""
        if fact_id is None:
            return
        self._recent.append(fact_id)
        if len(self._recent) > RECENT_BUFFER_SIZE:
            self._recent.pop(0)

    def get_fact_by_id(self, fid: int) -> Optional[Dict]:
        """Optional helper: retrieve a fact by ID."""
        for fact in self._facts:
            if fact.get("id") == fid:
                return fact
        return None


# ---------------------------------------------------------
# Singleton-like instance (imported by handlers & scheduler)
# ---------------------------------------------------------

_service_instance: Optional[GrokpediaService] = None


def _get_instance() -> GrokpediaService:
    global _service_instance
    if _service_instance is None:
        _service_instance = GrokpediaService(GROKPEDIA_PATH)
    return _service_instance


# ---------------------------------------------------------
# Public module-level functions
# (used by bot/handlers/grokpedia.py)
# ---------------------------------------------------------

def get_random(category: Optional[str] = None) -> Dict:
    return _get_instance().get_random(category)


def get_categories() -> List[str]:
    return _get_instance().get_categories()


def get_fact_by_id(fid: int) -> Optional[Dict]:
    return _get_instance().get_fact_by_id(fid)
