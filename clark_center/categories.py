from __future__ import annotations

import json
import re
from typing import Any

from .http_client import HttpClient
from .util import clean_text


ISSUE_CATEGORIES = [
    "Monetary policy",
    "Fiscal policy",
    "Taxation",
    "Labor markets",
    "Trade",
    "Immigration",
    "Education",
    "Healthcare",
    "Climate/environment",
    "Financial regulation",
    "Banking",
    "Industrial policy",
    "Antitrust/competition",
    "Housing/urban policy",
    "Growth/productivity",
    "Inequality/redistribution",
    "COVID/pandemic policy",
    "Energy",
    "International economics",
    "Public finance",
    "Political economy",
    "Other",
]


SOURCE_CATEGORY_MAP = {
    "banking": ["Banking"],
    "bonds": ["Financial regulation"],
    "business-cycles-recessions-crises": ["Other"],
    "business-management-corporate-performance": ["Other"],
    "corporate-governance": ["Financial regulation"],
    "democracy-government-public-policy": ["Political economy", "Public finance"],
    "demographics-aging-gender": ["Labor markets", "Inequality/redistribution"],
    "economic-growth-development-productivity": ["Growth/productivity"],
    "economists-economic-theory-economic-organizations": ["Other"],
    "education-skills": ["Education", "Labor markets"],
    "environment-climate-change-natural-resources": ["Climate/environment", "Energy"],
    "finance-and-the-economy": ["Financial regulation"],
    "financial-crises": ["Banking", "Financial regulation"],
    "financial-markets-banking": ["Banking", "Financial regulation"],
    "financial-regulation": ["Financial regulation"],
    "healthcare-wellbeing": ["Healthcare"],
    "international-finance": ["International economics"],
    "international-trade-exchange-rates": ["Trade", "International economics"],
    "investment-management": ["Financial regulation"],
    "investment-infrastructure-cities": ["Housing/urban policy", "Growth/productivity"],
    "investments": ["Financial regulation"],
    "jobs-pay-unemployment": ["Labor markets"],
    "migration": ["Immigration"],
    "monetary-policy-interest-rates-inflation": ["Monetary policy"],
    "personal-finance": ["Other"],
    "poverty-inequality-social-mobility": ["Inequality/redistribution"],
    "public-debt-deficits": ["Fiscal policy", "Public finance"],
    "regulation-competition-market-power": ["Antitrust/competition"],
    "science-technology-innovation": ["Growth/productivity", "Industrial policy"],
    "social-policy-society": ["Political economy"],
    "taxes-public-spending": ["Taxation", "Fiscal policy", "Public finance"],
    "transport": ["Other"],
}

KEYWORD_CATEGORY_MAP = [
    (("covid", "pandemic", "coronavirus"), "COVID/pandemic policy"),
    (("inflation", "interest rate", "fed", "monetary", "central bank", "ecb"), "Monetary policy"),
    (("tax", "tariff"), "Taxation"),
    (("debt", "deficit", "spending", "stimulus", "budget"), "Fiscal policy"),
    (("job", "wage", "unemployment", "labor", "labour"), "Labor markets"),
    (("trade", "tariff", "exchange rate"), "Trade"),
    (("immigration", "migration", "migrant"), "Immigration"),
    (("education", "school", "student"), "Education"),
    (("health", "healthcare", "medicaid", "aca"), "Healthcare"),
    (("climate", "carbon", "emissions", "environment"), "Climate/environment"),
    (("bank", "deposit", "credit", "financial crisis"), "Banking"),
    (("regulation", "derivative", "securities", "ipo", "index"), "Financial regulation"),
    (("antitrust", "competition", "market power", "monopoly"), "Antitrust/competition"),
    (("housing", "rent", "urban", "zoning"), "Housing/urban policy"),
    (("growth", "productivity", "innovation", "science", "ai"), "Growth/productivity"),
    (("inequality", "redistribution", "poverty", "minimum wage"), "Inequality/redistribution"),
    (("energy", "oil", "gas", "electricity"), "Energy"),
    (("euro", "china", "ukraine", "global", "international"), "International economics"),
    (("election", "democracy", "political"), "Political economy"),
]


def fetch_category_lookup(client: HttpClient) -> dict[str, str]:
    categories: dict[str, str] = {}
    for page in range(1, 20):
        url = f"https://kentclarkcenter.org/wp-json/wp/v2/categories?per_page=100&page={page}"
        try:
            text = client.fetch_text(url, "api", f"categories-page-{page}.json")
        except RuntimeError:
            break
        try:
            data: list[dict[str, Any]] = json.loads(text)
        except json.JSONDecodeError:
            break
        if not data:
            break
        for item in data:
            slug = clean_text(item.get("slug"))
            name = clean_text(item.get("name"))
            if slug and name:
                categories[slug] = name
    return categories


def classify_issue_categories(
    source_slugs: list[str],
    title: str,
    statements: list[str],
) -> tuple[str, str, str]:
    issues: list[str] = []
    from_source = False
    for slug in source_slugs:
        for issue in SOURCE_CATEGORY_MAP.get(slug, []):
            if issue not in issues:
                issues.append(issue)
                from_source = True
    text = " ".join([title, *statements]).lower()
    keyword_issues: list[str] = []
    for keywords, issue in KEYWORD_CATEGORY_MAP:
        if any(re.search(rf"\b{re.escape(keyword)}\b", text) for keyword in keywords) and issue not in issues:
            issues.append(issue)
            keyword_issues.append(issue)
    if "Other" in issues and len(issues) > 1:
        issues = [issue for issue in issues if issue != "Other"]
    if not issues:
        issues = ["Other"]
    if from_source and keyword_issues:
        return "; ".join(issues), "mixed", "0.80"
    if from_source:
        return "; ".join(issues), "source", "0.90"
    if keyword_issues:
        return "; ".join(issues), "model_assigned", "0.65"
    return "; ".join(issues), "model_assigned", "0.50"
