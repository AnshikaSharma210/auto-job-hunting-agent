from __future__ import annotations

from urllib.parse import quote_plus

from selenium.webdriver.remote.webdriver import WebDriver

from auto_job_hunting_agent.config import SETTINGS
from auto_job_hunting_agent.models import JobPosting


def _parse_cards_minimal(driver: WebDriver, platform: str, max_items: int = 12) -> list[JobPosting]:
    """Best-effort parsing; LinkedIn DOM changes often — extend selectors locally."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    wait = WebDriverWait(driver, min(SETTINGS.selenium_page_load_timeout, 20))
    jobs: list[JobPosting] = []

    # Try common LinkedIn list selectors (may break without maintenance).
    selectors = [
        "ul.scaffold-layout__list-container li.jobs-search-results__list-item",
        "li.jobs-search-results__list-item",
        "div.job-card-container",
    ]
    root: list = []
    for sel in selectors:
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, sel)))
            root = driver.find_elements(By.CSS_SELECTOR, sel)
            if root:
                break
        except Exception:
            continue

    if not root:
        return jobs

    import hashlib

    for el in root[:max_items]:
        try:
            title_el = el.find_element(By.CSS_SELECTOR, "a.job-card-list__title, a.job-card-container__link")
            title = title_el.text.strip()
            href = title_el.get_attribute("href") or ""
        except Exception:
            continue
        company = location = salary = None
        try:
            company = el.find_element(By.CSS_SELECTOR, "span.job-card-container__primary-description").text.strip()
        except Exception:
            pass
        try:
            location = el.find_element(By.CSS_SELECTOR, "li.job-card-container__metadata-item").text.strip()
        except Exception:
            pass
        desc = f"{title}\n{company or ''}\n{location or ''}"
        jid = hashlib.sha256(f"{platform}:{title}:{href}".encode()).hexdigest()[:20]
        jobs.append(
            JobPosting(
                id=jid,
                platform=platform,
                title=title,
                company=company,
                location=location,
                salary_text=salary,
                url=href,
                description=desc,
            )
        )
    return jobs


def search_linkedin_jobs(
    driver: WebDriver,
    role: str,
    location: str,
    salary_min_lpa: float | None = None,
) -> list[JobPosting]:
    keywords = quote_plus(role)
    loc = quote_plus(location)
    url = f"https://www.linkedin.com/jobs/search/?keywords={keywords}&location={loc}"
    driver.get(url)
    return _parse_cards_minimal(driver, platform="linkedin")
