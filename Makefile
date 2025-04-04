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