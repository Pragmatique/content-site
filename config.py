# src/config.py
from typing import Dict

    
class Settings:
    """Application configuration settings."""
    DATABASE_URL: str = "postgresql+psycopg2://postgres:1234@localhost:5432/mydb"
    SECRET_KEY: str = "your-secret-key-for-jwt"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    CDN_URL = "https://cdn.alinanightsky.com"
    GCORE_S3_DOMAIN = "s-ed1.cloud.gcore.lu"

    # GCore settings
    GCORE_BUCKET_NAME: str = "alinanightsky-website"
    GCORE_ENDPOINT_URL: str = "https://s-ed1.cloud.gcore.lu"
    GCORE_REGION_NAME: str = "s-ed1"
    GCORE_ACCESS_KEY: str = "7HQ7VZOJQXXE1M7NJ6UE"
    GCORE_SECRET_KEY: str = "t4A7iTsstPAlS3rpmdkMXdQbTuVseQVN09Kxuudx"

    # Blockchain settings
    TRON_FULL_NODE: str = "https://nile.trongrid.io"
    TRON_WALLET_ADDRESS: str = "TAVCJF1m5XumpyZLnsUsuSCLrcmdbRA5A2"
    USDT_TRC20_ADDRESS: str = "TXYZopYRdj2D9XRtbG411XZZ3kM5VkAeBf"
    BSC_FULL_NODE: str = "https://data-seed-prebsc-1-s1.binance.org:8545"
    BSC_WALLET_ADDRESS: str = "0x83aEb84f08517560dEBFc7F9652d8d260C921561"
    USDT_BEP20_ADDRESS: str = "0x5c24528E2c29988f696dF755C2f9951AC6D67AEF"

    # Subscription settings
    SUBSCRIPTION_PRICES: Dict[str, float] = {
        "basic": 10.0,
        "pro": 15.0,
        "premium": 20.0
    }
    SUBSCRIPTION_DURATION_DAYS: int = 30

    # Discount settings
    ENABLE_LOYALTY_DISCOUNT: bool = False


settings = Settings()
