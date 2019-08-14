# SPDX-License-Identifier: AGPL-3.0-only
TEST_FILE?=cg_worker_pool/tests/ psef_test/
SHELL=/bin/bash
TEST_FLAGS?=
PYTHON?=env/bin/python3
export PYTHONPATH=$(CURDIR)
PY_MODULES?=psef cg_celery cg_sqlalchemy_helpers cg_json cg_broker cg_logger cg_worker_pool
PY_ALL_MODULES=$(PY_MODULES) psef_test

.PHONY: test_setup
test_setup:
	mkdir -p /tmp/psef/uploads
	mkdir -p /tmp/psef/mirror_uploads

.PHONY: test_quick
test_quick:
	$(MAKE) test TEST_FLAGS="$(TEST_FLAGS) -x"

.PHONY: test
test:
	$(MAKE) test_no_cov TEST_FLAGS="$(TEST_FLAGS) --cov psef --cov cg_worker_pool --cov-report term-missing"

.PHONY: test_no_cov
test_no_cov: test_setup
	DEBUG=on env/bin/pytest --postgresql=GENERATE $(TEST_FILE) -vvvvvvv \
	    $(TEST_FLAGS)

.PHONY: count
count:
	cloc $(PY_MODULES) src

.PHONY: doctest
doctest: test_setup
	pytest --cov psef \
	       --cov cg_worker_pool \
	       --cov-append \
	       --cov-report term-missing \
	       --doctest-modules psef \
	       -vvvvv $(TEST_FLAGS)

.PHONY: reset_db
reset_db:
	DEBUG_ON=True ./.scripts/reset_database.sh
	$(MAKE) db_upgrade
	$(MAKE) test_data

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
	DEBUG=on env/bin/celery worker --app=broker_runcelery:celery -E

.PHONY: start_dev_celery
start_dev_celery:
	DEBUG=on env/bin/celery worker --app=runcelery:celery -E

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
	isort --recursive $(PY_ALL_MODULES)

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
	mypy $(PY_MODULES)

.PHONY: create_permission
create_permission:
	python ./.scripts/create_permission.py
