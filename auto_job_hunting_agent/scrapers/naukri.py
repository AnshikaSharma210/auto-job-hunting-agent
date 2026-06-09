from __future__ import annotations

from urllib.parse import quote_plus

from selenium.webdriver.remote.webdriver import WebDriver

from auto_job_hunting_agent.models import JobPosting


def search_naukri_jobs(
    driver: WebDriver,
    role: str,
    location: str,
    salary_min_lpa: float | None = None,
) -> list[JobPosting]:
    """Naukri search is highly dynamic; this opens a keyword search and parses article cards."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    import hashlib

    from auto_job_hunting_agent.config import SETTINGS

    q = quote_plus(role)
    url = f"https://www.naukri.com/jobs-in-india?k={q}"
    driver.get(url)
    wait = WebDriverWait(driver, min(SETTINGS.selenium_page_load_timeout, 20))
    jobs: list[JobPosting] = []

    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.cust-job-tuple")))
    except Exception:
        return jobs

    cards = driver.find_elements(By.CSS_SELECTOR, "div.cust-job-tuple")[:12]
    for el in cards:
        try:
            title_el = el.find_element(By.CSS_SELECTOR, "a.title")
            title = title_el.text.strip()
            href = title_el.get_attribute("href") or ""
        except Exception:
            continue
        company = comp_text = None
        try:
            comp_text = el.find_element(By.CSS_SELECTOR, "a.comp-name").text.strip()
            company = comp_text
        except Exception:
            pass
        loc = None
        try:
            loc = el.find_element(By.CSS_SELECTOR, "span.locWdth").text.strip()
        except Exception:
            pass
        salary = None
        try:
            salary = el.find_element(By.CSS_SELECTOR, "span.salary").text.strip()
        except Exception:
            pass
        desc_bits = [title, company or "", loc or "", salary or ""]
        desc = "\n".join(x for x in desc_bits if x)
        jid = hashlib.sha256(f"naukri:{title}:{href}".encode()).hexdigest()[:20]
        jobs.append(
            JobPosting(
                id=jid,
                platform="naukri",
                title=title,
                company=company,
                location=loc or location,
                salary_text=salary,
                url=href,
                description=desc,
            )
        )
    return jobs
