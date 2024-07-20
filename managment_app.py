from fastapi import FastAPI
from webapp import create_app
# from telegram_bot.bot import start_bot
import asyncio

app = create_app()

# @app.on_event("startup")
# async def startup_event():
#     # Вставьте код для инициализации приложения, например, создание таблиц, если они не существуют
#     pass
#
# @app.on_event("shutdown")
# async def shutdown_event():
#     # Вставьте код для завершения работы приложения, если это необходимо
#     pass

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=80, log_level="debug")
    # loop = asyncio.get_event_loop()
    # loop.create_task(start_bot())
