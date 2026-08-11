"""Curated journal registry used to constrain academic discovery."""

from dataclasses import dataclass


@dataclass(frozen=True)
class JournalDefinition:
    name: str
    issn: str
    homepage: str
    category: str


CORE_FINANCE_JOURNALS: tuple[JournalDefinition, ...] = (
    JournalDefinition(
        name="The Journal of Finance",
        issn="0022-1082",
        homepage="https://afajof.org/journal-of-finance/",
        category="core_finance",
    ),
    JournalDefinition(
        name="Review of Financial Studies",
        issn="0893-9454",
        homepage="https://sfs.org/review-of-financial-studies/",
        category="core_finance",
    ),
    JournalDefinition(
        name="Journal of Financial Economics",
        issn="0304-405X",
        homepage="https://www.sciencedirect.com/journal/journal-of-financial-economics",
        category="core_finance",
    ),
    JournalDefinition(
        name="Journal of Financial and Quantitative Analysis",
        issn="0022-1090",
        homepage="https://www.cambridge.org/core/journals/journal-of-financial-and-quantitative-analysis",
        category="core_finance",
    ),
    JournalDefinition(
        name="Review of Finance",
        issn="1572-3097",
        homepage="https://academic.oup.com/rof",
        category="core_finance",
    ),
    JournalDefinition(
        name="Journal of Financial Econometrics",
        issn="1479-8409",
        homepage="https://academic.oup.com/jfec",
        category="financial_econometrics",
    ),
    JournalDefinition(
        name="Journal of Econometrics",
        issn="0304-4076",
        homepage="https://www.sciencedirect.com/journal/journal-of-econometrics",
        category="econometrics",
    ),
    JournalDefinition(
        name="Management Science",
        issn="0025-1909",
        homepage="https://pubsonline.informs.org/journal/mnsc",
        category="management_science",
    ),
    JournalDefinition(
        name="Econometrica",
        issn="0012-9682",
        homepage="https://www.econometricsociety.org/publications/econometrica",
        category="economics",
    ),
)

JOURNALS_BY_ISSN = {journal.issn.upper(): journal for journal in CORE_FINANCE_JOURNALS}
