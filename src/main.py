from fastapi import FastAPI

from .core.utils.startup import lifespan, setup_app

app = FastAPI(lifespan=lifespan)
setup_app(app)
