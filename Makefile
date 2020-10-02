# SPDX-License-Identifier: AGPL-3.0-only
TEST_MODULES ?= $(wildcard cg_*/tests/)
TEST_FILE ?= $(TEST_MODULES) psef_test/
TEST_FLAGS ?=
DOCTEST_MODULES ?= psef cg_cache cg_helpers cg_enum cg_sqlalchemy_helpers cg_register cg_maybe
SHELL := $(shell which bash)
PYTHON ?= env/bin/python3
export PYTHONPATH=$(CURDIR)
PY_MODULES ?= psef $(wildcard cg_*)
PY_ALL_MODULES = $(PY_MODULES) psef_test

.PHONY: test_setup
test_setup:
	mkdir -p /tmp/psef/uploads
	mkdir -p /tmp/psef/mirror_uploads

.PHONY: test_quick
test_quick: TEST_FLAGS += -x
test_quick: test

.PHONY: test
test: TEST_FLAGS += --cov psef $(patsubst %/tests/,--cov %,$(TEST_MODULES)) --cov-report term-missing
test: test_no_cov

.PHONY: test_no_cov
test_no_cov: test_setup
	DEBUG=on env/bin/pytest --postgresql=GENERATE $(TEST_FILE) -vvvvvvv \
	    $(TEST_FLAGS)

.PHONY: count
count:
	cloc $(PY_MODULES) src

.PHONY: doctest
doctest: test_setup
	pytest $(patsubst %,--cov %,$(DOCTEST_MODULES)) \
	       $(patsubst %,--doctest-modules %,$(DOCTEST_MODULES)) \
	       --cov-append \
	       --cov-report term-missing \
	       -vvvvv $(TEST_FLAGS)

.PHONY: reset_db_broker
reset_db_broker:
	DEBUG_ON=True ./.scripts/reset_database.sh broker


.PHONY: reset_db
reset_db:
	DEBUG_ON=True ./.scripts/reset_database.sh
	$(MAKE) db_upgrade
	$(MAKE) test_data

.PHONY: migrate_broker
migrate_broker:
	DEBUG_ON=True $(PYTHON) manage_broker.py db migrate
	DEBUG_ON=True $(PYTHON) manage_broker.py db edit
	DEBUG_ON=True $(PYTHON) manage_broker.py db upgrade

.PHONY: migrate
migrate:
	DEBUG_ON=True $(PYTHON) manage.py db migrate
	DEBUG_ON=True $(PYTHON) manage.py db edit
	$(MAKE) db_upgrade

.PHONY: db_upgrade
db_upgrade:
	DEBUG_ON=True $(PYTHON) manage.py db upgrade

.PHONY: test_data
test_data:
	DEBUG_ON=True $(PYTHON) $(CURDIR)/manage.py test_data

.PHONY: broker_start_dev_server
broker_start_dev_server:
	DEBUG=on $(PYTHON) ./run_broker.py

.PHONY: broker_start_dev_celery
broker_start_dev_celery:
	DEBUG=on env/bin/celery worker --app=broker_runcelery:celery -EB

.PHONY: start_dev_celery
start_dev_celery:
	bash ./.scripts/start_celery.bash

.PHONY: start_dev_server
start_dev_server:
	DEBUG=on ./.scripts/start_dev.sh python

.PHONY: start_dev_test_runner
start_dev_test_runner:
	DEBUG=on ./.scripts/start_dev_auto_test_runner.sh

.PHONY: start_dev_npm
start_dev_npm: privacy_statement
	DEBUG=on ./.scripts/start_dev.sh npm

.PHONY: privacy_statement
privacy_statement: src/components/PrivacyNote.vue
src/components/PrivacyNote.vue:
	./.scripts/generate_privacy.py

.PHONY: build_front-end
build_front-end: privacy_statement
	npm run build

.PHONY: seed_data
seed_data:
	DEBUG_ON=True $(PYTHON) $(CURDIR)/manage.py seed

.PHONY: isort
isort:
	isort $(PY_ALL_MODULES)

.PHONY: yapf
yapf:
	yapf -rip $(PY_ALL_MODULES)

.PHONY: prettier
prettier:
	npm run format

.PHONY: format
format: isort yapf prettier

.PHONY: shrinkwrap
shrinkwrap:
	npm shrinkwrap --dev

.PHONY: pylint
pylint:
	pylint $(PY_MODULES) --rcfile=setup.cfg

.PHONY: isort_check
isort_check:
	isort --check-only --diff --recursive $(PY_ALL_MODULES)

.PHONY: yapf_check
yapf_check:
	yapf -vv -rd $(PY_ALL_MODULES)

lint: mypy pylint isort_check
	npm run lint

.PHONY: mypy
mypy:
	mypy $(filter-out cg_override cg_typing_extensions,$(PY_MODULES)) ./*.py --show-traceback

.PHONY: generate_permission_files
generate_permission_files:
	python ./.scripts/generate_permissions_py.py
	python ./.scripts/generate_permissions_ts.py

.PHONY: create_permission
create_permission:
	python ./.scripts/create_permission.py
	$(MAKE) db_upgrade
	$(MAKE) generate_permission_files

.PHONY: docs
docs:
	$(MAKE) -C docs html

.PHONY: hotreload_docs
hotreload_docs:
	pip install sphinx-reload
	sphinx-reload docs/ --watch 'docs/**/*.rst' --watch 'docs/**/*.py'

.PHONY: clean
clean:
	$(MAKE) -C docs clean

.PHONY: build_api_libs
build_api_libs:
	docker build --tag cg_api_libs_builder -f .docker/client_libs/Dockerfile .
	docker run --user=$(shell id -u) -v $(CURDIR)/:/app --rm cg_api_libs_builder

.PHONY: build_swagger
build_swagger:
	python ./.scripts/generate_swagger.py
