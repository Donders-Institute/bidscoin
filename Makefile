help:
	@egrep -h '\s##\s' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m  %-30s\033[0m %s\n", $$1, $$2}'

install: ## install python dependencies and bidscoin package
	@pip install --upgrade pip
	@pip install -e .[all]
	@python setup.py install
	@pip install pytest

test: ## run all the tests in the tests folder
	@pytest tests/

ci: install test ## emulate ci, runs install and test
