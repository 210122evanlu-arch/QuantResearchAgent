"""External financial-data source adapters."""

from data_sources.baostock import (
    BaoStockBuildConfig,
    BaoStockBuildResult,
    BaoStockDataError,
    BaoStockIVOLDataBuilder,
)
from data_sources.baostock_industry import (
    BaoStockIndustryConfig,
    BaoStockIndustryError,
    BaoStockIndustryResult,
    align_industry_to_panel,
    build_baostock_industry_cache,
    load_industry_snapshots,
)
from data_sources.baostock_universe import (
    BaoStockHistoricalUniverseBuilder,
    BaoStockUniverseConfig,
    BaoStockUniverseResult,
)
from data_sources.company_public import (
    BaoStockCompanyDataProvider,
    CNInfoAnnouncementClient,
    CompanyPublicDataConfig,
    CompanyPublicDataError,
    to_baostock_code,
)
from data_sources.fama_french import (
    CsmarFactorDataConfig,
    FactorDataConfig,
    FactorDataError,
    FactorDataSet,
    load_csmar_five_factor_data,
    load_five_factor_data,
    prepare_five_factor_ivol_panel,
)
from data_sources.risk_free import (
    ChinaBondRiskFreeConfig,
    ChinaBondRiskFreeResult,
    RiskFreeDataError,
    align_risk_free_to_dates,
    download_chinabond_risk_free,
    load_risk_free_proxy,
)
from data_sources.thesis_v2 import ThesisV2Config, build_thesis_v2_dataset
from data_sources.tushare import (
    TushareBuildConfig,
    TushareBuildResult,
    TushareDataError,
    TushareIVOLDataBuilder,
)

__all__ = [
    "BaoStockBuildConfig",
    "BaoStockBuildResult",
    "BaoStockCompanyDataProvider",
    "BaoStockDataError",
    "BaoStockHistoricalUniverseBuilder",
    "BaoStockIVOLDataBuilder",
    "BaoStockIndustryConfig",
    "BaoStockIndustryError",
    "BaoStockIndustryResult",
    "BaoStockUniverseConfig",
    "BaoStockUniverseResult",
    "CNInfoAnnouncementClient",
    "ChinaBondRiskFreeConfig",
    "ChinaBondRiskFreeResult",
    "CompanyPublicDataConfig",
    "CompanyPublicDataError",
    "CsmarFactorDataConfig",
    "FactorDataConfig",
    "FactorDataError",
    "FactorDataSet",
    "RiskFreeDataError",
    "ThesisV2Config",
    "TushareBuildConfig",
    "TushareBuildResult",
    "TushareDataError",
    "TushareIVOLDataBuilder",
    "align_industry_to_panel",
    "align_risk_free_to_dates",
    "build_baostock_industry_cache",
    "build_thesis_v2_dataset",
    "download_chinabond_risk_free",
    "load_csmar_five_factor_data",
    "load_five_factor_data",
    "load_industry_snapshots",
    "load_risk_free_proxy",
    "prepare_five_factor_ivol_panel",
    "to_baostock_code",
]
