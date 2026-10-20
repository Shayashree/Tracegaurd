"""Structured data lookup tool for product records."""
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from backend.config import settings
from backend.tools.base import BaseTool

class DataLookupArgs(BaseModel):
    query: Optional[str] = Field(
        None,
        description="Search term matching product name, description, or multiple products (e.g. 'Product A and Product B')"
    )
    product_id: Optional[str] = Field(
        None,
        description="Exact product ID to lookup (e.g. 'prod_001')"
    )
    category: Optional[str] = Field(
        None,
        description="Optional category filter (e.g. 'Peripherals', 'Audio', 'Accessories')"
    )

class DataLookupTool(BaseTool):
    name = "data_lookup"
    description = (
        "Search products in the local catalog. Supports lookup by product name, keywords, "
        "multiple products, exact product ID, and category filtering. Returns structured product details including prices."
    )
    args_schema = DataLookupArgs

    def __init__(self, data_path: Optional[Path] = None):
        self.data_path = Path(data_path) if data_path else settings.products_json_path

    def _load_data(self) -> List[Dict[str, Any]]:
        if not self.data_path.exists():
            return []
        with open(self.data_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _run(self, args: DataLookupArgs) -> dict:
        items = self._load_data()
        if not items:
            return {
                "count": 0,
                "matches": [],
                "message": f"Product dataset is empty or file not found at {self.data_path}"
            }

        # Filter by exact product_id if provided
        if args.product_id:
            pid = args.product_id.strip().lower()
            matches = [item for item in items if item.get("id", "").lower() == pid]
            return {
                "count": len(matches),
                "matches": matches,
                "message": f"Found {len(matches)} product(s) for ID '{args.product_id}'" if matches else f"No product found for ID '{args.product_id}'"
            }

        filtered = items

        # Filter by category if provided
        if args.category:
            cat = args.category.strip().lower()
            filtered = [item for item in filtered if item.get("category", "").lower() == cat]

        # Search by query
        if args.query:
            q = args.query.strip().lower()
            # Check if query mentions multiple target names (e.g. "Product A and Product B" or "Product A, Product B")
            sub_queries = [sq.strip() for sq in q.replace(" and ", ",").split(",") if sq.strip()]
            
            matched_items: List[Dict[str, Any]] = []
            seen_ids = set()

            for item in filtered:
                name = item.get("name", "").lower()
                desc = item.get("description", "").lower()
                iid = item.get("id", "").lower()
                cat = item.get("category", "").lower()

                # If full query matches directly or query contains product name
                if q in name or name in q or q in desc or q in iid or q in cat:
                    if item["id"] not in seen_ids:
                        matched_items.append(item)
                        seen_ids.add(item["id"])
                    continue

                # Or if any sub-query matches
                for sq in sub_queries:
                    if sq and (sq in name or name in sq or sq in desc or sq in iid):
                        if item["id"] not in seen_ids:
                            matched_items.append(item)
                            seen_ids.add(item["id"])
                        break

            filtered = matched_items

        count = len(filtered)
        if count == 0:
            msg = "No matching records found."
            if args.query:
                msg += f" (Query: '{args.query}')"
            if args.category:
                msg += f" (Category: '{args.category}')"
        else:
            msg = f"Found {count} matching record(s)."

        return {
            "count": count,
            "matches": filtered,
            "message": msg
        }
