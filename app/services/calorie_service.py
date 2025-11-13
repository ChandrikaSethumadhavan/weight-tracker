from __future__ import annotations

import math
import random
import re
import json
from dataclasses import dataclass
from typing import Dict, Optional

import requests


@dataclass
class CalorieEstimate:
    calories: float
    source: str
    raw_response: Optional[str] = None
    note: Optional[str] = None
    carbs: float = 0.0
    protein: float = 0.0
    fat: float = 0.0


class CalorieAdvisor:
    """Best-effort helper that leans on GPT/Open APIs when possible."""

    DEFAULT_LIBRARY: Dict[str, Dict[str, float]] = {
        "banana": {"calories": 105, "carbs": 27, "protein": 1.3, "fat": 0.3},
        "apple": {"calories": 95, "carbs": 25, "protein": 0.5, "fat": 0.3},
        "orange": {"calories": 62, "carbs": 15, "protein": 1.2, "fat": 0.2},
        "protein shake": {"calories": 180, "carbs": 10, "protein": 25, "fat": 3},
        "grilled chicken breast": {"calories": 220, "carbs": 0, "protein": 43, "fat": 5},
        "boiled egg": {"calories": 78, "carbs": 0.6, "protein": 6, "fat": 5},
        "greek yogurt": {"calories": 130, "carbs": 9, "protein": 17, "fat": 4},
        "oatmeal bowl": {"calories": 150, "carbs": 27, "protein": 5, "fat": 3},
        "salad bowl": {"calories": 190, "carbs": 14, "protein": 6, "fat": 12},
        "avocado toast": {"calories": 240, "carbs": 24, "protein": 7, "fat": 14},
        "brown rice bowl": {"calories": 215, "carbs": 45, "protein": 5, "fat": 2},
        "dal bowl": {"calories": 230, "carbs": 30, "protein": 13, "fat": 6},
        "idli": {"calories": 70, "carbs": 12, "protein": 2, "fat": 0.2},
        "dosa": {"calories": 160, "carbs": 25, "protein": 3, "fat": 5},
        "chapati": {"calories": 110, "carbs": 18, "protein": 3, "fat": 3},
    }

    def __init__(
        self,
        openai_api_key: Optional[str] = None,
        nutrition_api_key: Optional[str] = None,
    ) -> None:
        self.openai_api_key = openai_api_key
        self.nutrition_api_key = nutrition_api_key
        self._session = requests.Session()

    def estimate(self, description: str) -> CalorieEstimate:
        normalized = description.strip().lower()
        if not normalized:
            raise ValueError("Description cannot be empty.")

        if normalized in self.DEFAULT_LIBRARY:
            values = self.DEFAULT_LIBRARY[normalized]
            return CalorieEstimate(
                calories=values["calories"],
                carbs=values["carbs"],
                protein=values["protein"],
                fat=values["fat"],
                source="library",
            )

        if self.openai_api_key:
            try:
                return self._ask_gpt(description)
            except Exception as error:  # pragma: no cover - network
                return self._fallback_estimate(normalized, "gpt-fallback", error)

        if self.nutrition_api_key:
            try:
                return self._call_nutrition_api(description)
            except Exception as error:  # pragma: no cover - network
                return self._fallback_estimate(normalized, "nutrition-fallback", error)

        return self._heuristic_estimate(normalized)

    # ------------------------------------------------------------------
    def _heuristic_estimate(self, text: str) -> CalorieEstimate:
        base = 120.0
        if "salad" in text:
            base = 180
        elif any(word in text for word in ["pizza", "burger", "fries"]):
            base = 420
        elif "smoothie" in text or "shake" in text:
            base = 210
        elif any(word in text for word in ["rice", "biriyani", "biryani"]):
            base = 310
        elif "paneer" in text:
            base = 260
        elif "soup" in text:
            base = 140
        multiplier = 1.0
        portion_match = re.search(r"(\d+(\.\d+)?)\s*(g|gram|grams|ml|cup|cups|piece)", text)
        if portion_match:
            qty = float(portion_match.group(1))
            unit = portion_match.group(3)
            if unit in {"g", "gram", "grams"}:
                multiplier = qty / 100.0
            elif unit in {"ml"}:
                multiplier = qty / 200.0
            elif unit in {"cup", "cups"}:
                multiplier = qty
            elif unit == "piece":
                multiplier = max(1.0, qty)
        fuzz = random.uniform(-20, 40)
        calories = max(20.0, base * multiplier + fuzz)
        carbs, protein, fat = self._macro_from_calories(calories, text)
        return CalorieEstimate(calories, "heuristic", carbs=carbs, protein=protein, fat=fat)

    def _ask_gpt(self, description: str) -> CalorieEstimate:
        payload = {
            "model": "gpt-4o-mini",
            "temperature": 0.2,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a macro-friendly nutrition estimator. Respond ONLY with JSON "
                        'formatted as {"calories":123,"carbs":40,"protein":25,"fat":10}. '
                        "Do not include any extra text."
                    ),
                },
                {"role": "user", "content": description},
            ],
        }
        response = self._session.post(
            "https://api.openai.com/v1/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {self.openai_api_key}"},
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            calories = self._extract_number(content)
            carbs, protein, fat = self._macro_from_calories(calories, description)
            return CalorieEstimate(calories, "openai:gpt-4o-mini", raw_response=content, carbs=carbs, protein=protein, fat=fat)
        return CalorieEstimate(
            calories=float(parsed.get("calories", 0)),
            carbs=float(parsed.get("carbs", 0)),
            protein=float(parsed.get("protein", 0)),
            fat=float(parsed.get("fat", 0)),
            source="openai:gpt-4o-mini",
            raw_response=content,
        )

    def _call_nutrition_api(self, description: str) -> CalorieEstimate:
        response = self._session.get(
            "https://api.api-ninjas.com/v1/nutrition",
            params={"query": description},
            headers={"X-Api-Key": self.nutrition_api_key},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        calories = sum(item.get("calories", 0) for item in payload)
        carbs = sum(item.get("carbohydrates_total_g", 0) for item in payload)
        protein = sum(item.get("protein_g", 0) for item in payload)
        fat = sum(item.get("fat_total_g", 0) for item in payload)
        return CalorieEstimate(calories, "api-ninjas", raw_response=str(payload), carbs=carbs, protein=protein, fat=fat)

    def _fallback_estimate(self, normalized: str, source: str, error: Exception) -> CalorieEstimate:
        estimate = self._heuristic_estimate(normalized)
        estimate.source = source
        estimate.note = str(error)
        return estimate

    def _macro_from_calories(self, calories: float, description: str) -> tuple[float, float, float]:
        lower_text = description.lower()
        # basic heuristic ratios
        if any(word in lower_text for word in ["shake", "smoothie", "protein"]):
            ratios = (0.35, 0.45, 0.2)
        elif any(word in lower_text for word in ["salad", "bowl", "veggie"]):
            ratios = (0.45, 0.3, 0.25)
        elif any(word in lower_text for word in ["rice", "pasta", "bread", "chapati", "idli", "dosa"]):
            ratios = (0.55, 0.2, 0.25)
        else:
            ratios = (0.5, 0.25, 0.25)
        carbs = calories * ratios[0] / 4
        protein = calories * ratios[1] / 4
        fat = calories * ratios[2] / 9
        return round(carbs, 1), round(protein, 1), round(fat, 1)

    @staticmethod
    def _extract_number(text: str) -> float:
        match = re.search(r"(\d+(\.\d+)?)", text)
        if not match:
            raise ValueError(f"Could not parse calories from: {text}")
        return float(match.group(1))
