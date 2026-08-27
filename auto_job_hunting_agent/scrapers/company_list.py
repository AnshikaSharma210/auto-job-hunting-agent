"""
Curated company → ATS mapping for direct career-page queries.

Each entry: company_name → {"ats": "greenhouse"|"lever"|"ashby", "slug": "<board-token>"}

The slug is the token that appears in the company's careers URL, e.g.
  Greenhouse: https://boards.greenhouse.io/stripe  → slug = "stripe"
  Lever:      https://jobs.lever.co/netflix        → slug = "netflix"
  Ashby:      https://jobs.ashbyhq.com/openai      → slug = "openai"

Sources verified against live endpoints as of mid-2026.
Add your own companies via the COMPANY_LIST_EXTRA env var (see config.py).
"""
from __future__ import annotations

# ── Format ────────────────────────────────────────────────────────────────────
# "Company Name": {"ats": "greenhouse" | "lever" | "ashby", "slug": "ats-slug"}

COMPANY_ATS_MAP: dict[str, dict[str, str]] = {
    # ── India — Fintech ───────────────────────────────────────────────────────
    "Razorpay": {"ats": "lever", "slug": "razorpay"},
    "PhonePe": {"ats": "greenhouse", "slug": "phonepe"},
    "CRED": {"ats": "greenhouse", "slug": "cred"},
    "Groww": {"ats": "lever", "slug": "groww"},
    "Zerodha": {"ats": "greenhouse", "slug": "zerodha"},
    "Juspay": {"ats": "greenhouse", "slug": "juspay"},
    "Khatabook": {"ats": "lever", "slug": "khatabook"},
    "Slice": {"ats": "greenhouse", "slug": "slice"},
    "Jupiter": {"ats": "lever", "slug": "jupitermoney"},
    "Fi Money": {"ats": "greenhouse", "slug": "epifi"},
    "Smallcase": {"ats": "lever", "slug": "smallcase"},
    "BharatPe": {"ats": "greenhouse", "slug": "bharatpe"},

    # ── India — Consumer / E-commerce ─────────────────────────────────────────
    "Swiggy": {"ats": "greenhouse", "slug": "swiggy"},
    "Zomato": {"ats": "lever", "slug": "zomato"},
    "Meesho": {"ats": "lever", "slug": "meesho"},
    "Zepto": {"ats": "greenhouse", "slug": "zepto"},
    "Nykaa": {"ats": "greenhouse", "slug": "nykaa"},
    "Urban Company": {"ats": "lever", "slug": "urbancompany"},
    "HealthifyMe": {"ats": "lever", "slug": "healthifyme"},
    "Pristyn Care": {"ats": "lever", "slug": "pristyncare"},
    "Mfine": {"ats": "lever", "slug": "mfine"},

    # ── India — SaaS / Tech ───────────────────────────────────────────────────
    "BrowserStack": {"ats": "lever", "slug": "browserstack"},
    "Freshworks": {"ats": "greenhouse", "slug": "freshworks"},
    "Chargebee": {"ats": "lever", "slug": "chargebee"},
    "Postman": {"ats": "lever", "slug": "postman"},
    "Clevertap": {"ats": "greenhouse", "slug": "clevertap"},
    "Druva": {"ats": "lever", "slug": "druva"},
    "Hasura": {"ats": "lever", "slug": "hasura"},
    "Darwinbox": {"ats": "lever", "slug": "darwinbox"},
    "Whatfix": {"ats": "lever", "slug": "whatfix"},
    "Sprinklr": {"ats": "greenhouse", "slug": "sprinklr"},
    "InMobi": {"ats": "greenhouse", "slug": "inmobi"},
    "MoEngage": {"ats": "greenhouse", "slug": "moengage"},
    "Capillary Technologies": {"ats": "greenhouse", "slug": "capillary"},
    "Wingify": {"ats": "greenhouse", "slug": "wingify"},
    "Zenoti": {"ats": "greenhouse", "slug": "zenoti"},
    "Leadsquared": {"ats": "greenhouse", "slug": "leadsquared"},
    "Exotel": {"ats": "lever", "slug": "exotel"},
    "Yellow.ai": {"ats": "greenhouse", "slug": "yellowmessenger"},

    # ── India — MNCs with India offices ──────────────────────────────────────
    "Atlassian": {"ats": "greenhouse", "slug": "atlassian"},
    "Adobe": {"ats": "greenhouse", "slug": "adobe"},
    "Publicis Sapient": {"ats": "greenhouse", "slug": "publicissapient"},
    "ThoughtSpot": {"ats": "greenhouse", "slug": "thoughtspot"},
    "Nutanix": {"ats": "greenhouse", "slug": "nutanix"},
    "Palo Alto Networks": {"ats": "greenhouse", "slug": "paloaltonetworks"},
    "Rubrik": {"ats": "greenhouse", "slug": "rubrik"},

    # ── Global — AI / LLM ─────────────────────────────────────────────────────
    "OpenAI": {"ats": "ashby", "slug": "openai"},
    "Anthropic": {"ats": "ashby", "slug": "anthropic"},
    "Mistral AI": {"ats": "ashby", "slug": "mistral"},
    "Cohere": {"ats": "greenhouse", "slug": "cohere"},
    "Hugging Face": {"ats": "lever", "slug": "huggingface"},
    "Perplexity AI": {"ats": "ashby", "slug": "perplexityai"},
    "Groq": {"ats": "ashby", "slug": "groq"},
    "Scale AI": {"ats": "greenhouse", "slug": "scaleai"},
    "Weights & Biases": {"ats": "lever", "slug": "wandb"},
    "LangChain": {"ats": "ashby", "slug": "langchain"},
    "Replit": {"ats": "ashby", "slug": "replit"},
    "Stability AI": {"ats": "greenhouse", "slug": "stabilityai"},
    "Character.ai": {"ats": "greenhouse", "slug": "character"},

    # ── Global — Infrastructure / Cloud ──────────────────────────────────────
    "Stripe": {"ats": "greenhouse", "slug": "stripe"},
    "MongoDB": {"ats": "greenhouse", "slug": "mongodb"},
    "Twilio": {"ats": "greenhouse", "slug": "twilio"},
    "Cloudflare": {"ats": "greenhouse", "slug": "cloudflare"},
    "Hashicorp": {"ats": "greenhouse", "slug": "hashicorp"},
    "Datadog": {"ats": "greenhouse", "slug": "datadog"},
    "Confluent": {"ats": "greenhouse", "slug": "confluent"},
    "dbt Labs": {"ats": "greenhouse", "slug": "dbtlabs"},
    "Elastic": {"ats": "greenhouse", "slug": "elastic"},
    "PagerDuty": {"ats": "greenhouse", "slug": "pagerduty"},
    "JFrog": {"ats": "greenhouse", "slug": "jfrog"},
    "Grafana Labs": {"ats": "greenhouse", "slug": "grafanalabs"},
    "Snowflake": {"ats": "greenhouse", "slug": "snowflake"},
    "Databricks": {"ats": "greenhouse", "slug": "databricks"},
    "Okta": {"ats": "greenhouse", "slug": "okta"},
    "Box": {"ats": "greenhouse", "slug": "box"},
    "Splunk": {"ats": "greenhouse", "slug": "splunk"},
    "New Relic": {"ats": "greenhouse", "slug": "newrelic"},
    "Dynatrace": {"ats": "greenhouse", "slug": "dynatrace"},

    # ── Global — Product / SaaS ───────────────────────────────────────────────
    "Notion": {"ats": "greenhouse", "slug": "notion"},
    "Figma": {"ats": "greenhouse", "slug": "figma"},
    "Canva": {"ats": "greenhouse", "slug": "canva"},
    "Asana": {"ats": "greenhouse", "slug": "asana"},
    "Airtable": {"ats": "greenhouse", "slug": "airtable"},
    "HubSpot": {"ats": "greenhouse", "slug": "hubspot"},
    "Zendesk": {"ats": "greenhouse", "slug": "zendesk"},
    "Intercom": {"ats": "greenhouse", "slug": "intercom"},
    "Dropbox": {"ats": "greenhouse", "slug": "dropbox"},
    "Pinterest": {"ats": "greenhouse", "slug": "pinterest"},
    "Airbnb": {"ats": "greenhouse", "slug": "airbnb"},
    "Miro": {"ats": "greenhouse", "slug": "miro"},
    "GitHub": {"ats": "greenhouse", "slug": "github"},
    "Zoom": {"ats": "greenhouse", "slug": "zoom"},

    # ── Global — Finance / Crypto ─────────────────────────────────────────────
    "Coinbase": {"ats": "lever", "slug": "coinbase"},
    "Robinhood": {"ats": "greenhouse", "slug": "robinhood"},
    "Brex": {"ats": "lever", "slug": "brex"},
    "Plaid": {"ats": "lever", "slug": "plaid"},
    "Ripple": {"ats": "greenhouse", "slug": "ripple"},

    # ── Global — Media / Social / Collaboration ───────────────────────────────
    "Reddit": {"ats": "lever", "slug": "reddit"},
    "Linear": {"ats": "ashby", "slug": "linear"},
    "Vercel": {"ats": "ashby", "slug": "vercel"},
    "Supabase": {"ats": "ashby", "slug": "supabase"},
    "PlanetScale": {"ats": "lever", "slug": "planetscale"},
}
