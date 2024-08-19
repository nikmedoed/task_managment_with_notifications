import asyncio

import uvicorn

from shared.app_config import app_config
from telegram_bot import start_bot
from webapp import create_app

app = create_app()


async def run_fastapi():
    config = uvicorn.Config(app, host=app_config.host, port=app_config.port, log_level=app_config.log_level)
    server = uvicorn.Server(config)
    await server.serve()


async def main():
    await asyncio.gather(
        run_fastapi(),
        start_bot(),
    )


if __name__ == "__main__":
    asyncio.run(main())
