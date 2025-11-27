# services/grokpedia_service.py
"""
Multi-file Grokpedia service.
Loads each category from assets/grokpedia/<category>.json
and merges all facts into a unified facts list.

Public API:
 - get_random(category=None)
 - get_categories()
 - get_fact_by_id(id)
"""

import json
import os
import random
import threading
from typing import Optional, List, Dict

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GROKPEDIA_DIR = os.path.join(ROOT_DIR, "assets", "grokpedia")

RECENT_BUFFER_SIZE = 20


class GrokpediaService:
    def __init__(self, folder_path: str):
        self.folder = folder_path

        self._categories: List[str] = []
        self._facts: List[Dict] = []
        self._recent: List[int] = []

        self._lock = threading.Lock()

        self._load_all()

    # -----------------------------------------------------
    # Loading Logic
    # -----------------------------------------------------
    def _load_all(self):
        # Load categories.json
        cat_path = os.path.join(self.folder, "categories.json")
        if not os.path.exists(cat_path):
            raise RuntimeError("Missing categories.json in grokpedia folder.")

        with open(cat_path, "r", encoding="utf-8") as f:
            self._categories = json.load(f)

        # Load each category file
        all_facts = []

        for category in self._categories:
            file_path = os.path.join(self.folder, f"{category}.json")
            if not os.path.exists(file_path):
                print(f"⚠ Missing Grokpedia file: {file_path} — skipping.")
                continue

            with open(file_path, "r", encoding="utf-8") as f:
                items = json.load(f)

            for fact in items:
                fact["category"] = category
                all_facts.append(fact)

        if not all_facts:
            raise RuntimeError("No Grokpedia facts found in any category files.")

        self._facts = all_facts
        print(f"[GROKPEDIA] Loaded {len(self._facts)} facts across {len(self._categories)} categories.")

    # -----------------------------------------------------
    # Public Access
    # -----------------------------------------------------
    def get_categories(self) -> List[str]:
        return self._categories.copy()

    def get_random(self, category: Optional[str] = None) -> Dict:
        with self._lock:
            pool = self._facts

            if category:
                category = category.lower().strip()
                if category not in self._categories:
                    raise ValueError(f"Unknown category: {category}")

                pool = [f for f in self._facts if f.get("category") == category]

            if not pool:
                raise RuntimeError("No facts available for the selected category.")

            non_recent = [f for f in pool if f.get("id") not in self._recent]
            choices = non_recent if non_recent else pool

            fact = random.choice(choices)
            self._push_recent(fact.get("id"))
            return fact

    def _push_recent(self, fid: int):
        if fid is None:
            return
        self._recent.append(fid)
        if len(self._recent) > RECENT_BUFFER_SIZE:
            self._recent.pop(0)

    def get_fact_by_id(self, fid: int) -> Optional[Dict]:
        for f in self._facts:
            if f.get("id") == fid:
                return f
        return None


# ---------------------------------------------------------
# Singleton instance
# ---------------------------------------------------------

_instance: Optional[GrokpediaService] = None

def _get_instance() -> GrokpediaService:
    global _instance
    if _instance is None:
        _instance = GrokpediaService(GROKPEDIA_DIR)
    return _instance


# Public API (imported by handlers)
def get_random(category: Optional[str] = None) -> Dict:
    return _get_instance().get_random(category)

def get_categories() -> List[str]:
    return _get_instance().get_categories()

def get_fact_by_id(fid: int) -> Optional[Dict]:
    return _get_instance().get_fact_by_id(fid)
