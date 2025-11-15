import json
from pathlib import Path
from typing import List, Optional
from langchain_core.tools import tool

# Load the product database once when the module is imported
_db_path = Path(__file__).parent / "structured_products_db.json"
with open(_db_path, "r") as f:
    _product_db = json.load(f)


@tool
def search_structured_products(
    risk_profile: Optional[str] = None,
    currency: Optional[str] = None,
    min_coupon_pa: Optional[float] = None,
) -> List[dict]:
    """
    Searches the bank's database for structured products based on specified criteria.

    Args:
        risk_profile: The client's risk profile. Valid values are 'Konservativ', 'Ausgewogen', 'Wachstum'.
        currency: The desired currency of the product. Valid values are 'CHF', 'EUR', 'USD'.
        min_coupon_pa: The minimum annual coupon percentage (e.g., 5.5 for 5.5%).
    """
    results = _product_db

    if risk_profile:
        results = [
            p for p in results if p["risk_profile"].lower() == risk_profile.lower()
        ]

    if currency:
        results = [p for p in results if p["currency"].lower() == currency.lower()]

    if min_coupon_pa is not None:
        results = [
            p for p in results if p["coupon_pa"] and p["coupon_pa"] >= min_coupon_pa
        ]

    return results[:10]  # Return a maximum of 10 results to keep the context small