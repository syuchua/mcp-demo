# main.py
import asyncio
from src.clients import start_cli
from src.log import setup_logger

logger = setup_logger(log_level="INFO")

if __name__ == "__main__":
    asyncio.run(start_cli())