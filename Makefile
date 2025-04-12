.PHONY: run test lint clean migrate makemigrations collectstatic shell check

# Default port
PORT ?= 8090

# Default settings module
SETTINGS ?= config.settings.development

# Run the development server
run:
	python manage.py runserver 0.0.0.0:$(PORT)

# Run tests
test:
	python manage.py test viewer

# Run linting
lint:
	flake8 viewer/ config/

# Clean up Python cache files
clean:
	find . -name "__pycache__" -type d -exec rm -rf {} +
	find . -name "*.pyc" -delete
	find . -name "*.pyo" -delete
	find . -name "*.pyd" -delete
	find . -name ".DS_Store" -delete
	find . -name "*.so" -delete
	find . -name "*.ipynb_checkpoints" -exec rm -rf {} +

# Run migrations
migrate:
	python manage.py migrate

# Make migrations
makemigrations:
	python manage.py makemigrations

# Collect static files
collectstatic:
	python manage.py collectstatic --noinput

# Start a shell
shell:
	python manage.py shell

# Run Django system checks
check:
	python manage.py check

# Set up the project from scratch
setup: clean
	pip install -r requirements.txt
	python manage.py migrate
	python manage.py collectstatic --noinput

help:
	@echo "Available commands:"
	@echo "  run             - Run the development server on port $(PORT)"
	@echo "  test            - Run tests"
	@echo "  lint            - Run code linting"
	@echo "  clean           - Clean up Python cache files"
	@echo "  migrate         - Run migrations"
	@echo "  makemigrations  - Make migrations"
	@echo "  collectstatic   - Collect static files"
	@echo "  shell           - Start a shell"
	@echo "  check           - Run Django system checks"
	@echo "  setup           - Set up the project from scratch"
	@echo ""
	@echo "You can customize port with PORT=XXXX"

# OCS Database Django Project Makefile

# Variables
PYTHON = python
MANAGE = $(PYTHON) manage.py
MODULE = viewer
SETTINGS_DEV = config.settings.development
SETTINGS_PROD = config.settings.production
STATIC_DIR = staticfiles
BACKUP_DIR = backup_files

# Default environment
ENV = development

# Export environment variables for the commands
export DJANGO_SETTINGS_MODULE = config.settings.$(ENV)
export PYTHONPATH = $(shell pwd)

# Default target
.PHONY: help
help:
	@echo "Usage: make [target]"
	@echo "Available targets:"
	@echo "  help           - Show this help message"
	@echo "  runserver      - Run the development server"
	@echo "  migrate        - Apply all migrations"
	@echo "  migrations     - Create migrations for the main app"
	@echo "  shell          - Run Django shell"
	@echo "  collectstatic  - Collect static files"
	@echo "  test           - Run tests"
	@echo "  clean          - Remove generated files (pycache, staticfiles, logs)"
	@echo "  pycache-clean  - Remove __pycache__ directories"
	@echo "  backup-db      - Create a database backup"
	@echo "  prod           - Set environment to production"

# Run the development server
.PHONY: runserver
runserver:
	$(MANAGE) runserver 0.0.0.0:8085

# Apply migrations
.PHONY: migrate
migrate:
	$(MANAGE) migrate

# Create migrations
.PHONY: migrations
migrations:
	$(MANAGE) makemigrations $(MODULE)

# Run the shell
.PHONY: shell
shell:
	$(MANAGE) shell

# Collect static files
.PHONY: collectstatic
collectstatic:
	$(MANAGE) collectstatic --noinput

# Run tests
.PHONY: test
test:
	$(MANAGE) test $(MODULE)

# Set production environment
.PHONY: prod
prod:
	$(eval ENV = production)
	@echo "Environment set to production"

# Clean up
.PHONY: clean
clean: pycache-clean
	rm -rf $(STATIC_DIR)/*
	rm -rf logs/*.log
	@echo "Cleaned staticfiles and logs"

# Remove __pycache__ directories
.PHONY: pycache-clean
pycache-clean:
	find . -name "__pycache__" -type d -not -path "./venv*" -exec rm -rf {} +
	find . -name "*.pyc" -delete
	find . -name "*.pyo" -delete
	find . -name "*.pyd" -delete
	@echo "Removed __pycache__ directories and compiled Python files"

# Create database backup
.PHONY: backup-db
backup-db:
	@echo "Creating database backup..."
	@mkdir -p $(BACKUP_DIR)/v$(shell cat version.txt)
	@timestamp=$$(date +"%Y%m%d_%H%M%S"); \
	pg_dump -h localhost -U postgres prod_ocs > $(BACKUP_DIR)/v$(shell cat version.txt)/prod_ocs_$$timestamp.sql
	@echo "Backup created in $(BACKUP_DIR)/v$(shell cat version.txt)/" 