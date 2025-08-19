# Makefile (Windows)
APP = app:app
PORT = 8000
RUNSERVER = uvicorn $(APP) --reload --port $(PORT)

dev:
	@echo Running DEV...
	@if exist .env.dev (copy /Y .env.dev .env >nul)
	@$(RUNSERVER)

staging:
	@echo Running STAGING...
	@if exist .env.staging (copy /Y .env.staging .env >nul)
	@$(RUNSERVER)

prod:
	@echo Not running PROD locally. Configure on Render.

up:
	@$(RUNSERVER)

shell:
	@python -i -c "from settings import settings; print(settings.dict())"