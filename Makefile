.PHONY: help run migrate makemigrations collectstatic shell check test lint clean

# Default development server port
PORT ?= 8090

help:
	@echo "Available targets:"
	@echo "  run             - Run the development server on port $(PORT)"
	@echo "  migrate         - Apply migrations"
	@echo "  makemigrations  - Create migrations"
	@echo "  collectstatic   - Collect static files"
	@echo "  shell           - Open the Django shell"
	@echo "  check           - Run Django system checks"
	@echo "  test            - Run tests"
	@echo "  lint            - Run flake8 on ocs/ and config/"
	@echo "  clean           - Remove __pycache__ and compiled Python files"
	@echo ""
	@echo "Override the port with: make run PORT=8085"

run:
	python manage.py runserver 0.0.0.0:$(PORT)

migrate:
	python manage.py migrate

makemigrations:
	python manage.py makemigrations

collectstatic:
	python manage.py collectstatic --noinput

shell:
	python manage.py shell

check:
	python manage.py check

test:
	python manage.py test ocs

lint:
	flake8 ocs/ config/

clean:
	find . -path ./venv -prune -o -name "__pycache__" -type d -exec rm -rf {} +
	find . -path ./venv -prune -o -name "*.py[co]" -delete
