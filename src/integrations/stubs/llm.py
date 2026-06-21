from typing import Any


class StubLLMClient:
    async def complete(self, messages: list[dict]) -> dict[str, Any]:
        """Canned deterministic response — no network, no API key."""
        return {
            "sql": "SELECT product, SUM(revenue) AS total_revenue FROM dataset GROUP BY product ORDER BY total_revenue DESC LIMIT 5",
            "rows": [
                {"product": "Widget A", "total_revenue": 5000},
                {"product": "Widget B", "total_revenue": 4200},
                {"product": "Widget C", "total_revenue": 3800},
                {"product": "Widget D", "total_revenue": 3100},
                {"product": "Widget E", "total_revenue": 2900},
            ],
            "columns": ["product", "total_revenue"],
            "row_count": 5,
            "table_markdown": "| product | total_revenue |\n|---------|---------------|\n| Widget A | 5000 |\n| Widget B | 4200 |\n| Widget C | 3800 |\n| Widget D | 3100 |\n| Widget E | 2900 |",
            "chart_spec": {
                "data": [{"x": ["Widget A", "Widget B", "Widget C", "Widget D", "Widget E"], "y": [5000, 4200, 3800, 3100, 2900], "type": "bar", "name": "total_revenue"}],
                "layout": {"xaxis": {"title": "product"}, "yaxis": {"title": "total_revenue"}, "title": "Top 5 Products by Revenue"}
            },
            "suggestions": ["Break down by category", "Show revenue trend over time"],
            "summary": "[STUB] Top 5 products by revenue returned.",
        }
