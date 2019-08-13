# Do not really on artifacts created by make for all targets.
.PHONY: all venv flake8 unit package clean tests check dist

all: venv check dist

venv:
	@echo Preparing virtual enviornment using pipenv.
	pipenv --version
	env PIPENV_QUIET=true pipenv install --dev

flake8: 
	@echo Checking code quality.
	pipenv run flake8 wca tests example workloads prm

unit: 
	@echo Running unit tests.
	pipenv run env PYTHONPATH=.:workload-collocation-agent pytest tests

package: 
	@echo Building wca pex file.
	-rm dist/wca-prm.pex
	-rm .pex-build/wca*
	-rm .pex-build/prm*
	-rm -rf prm.egg-info/
	pipenv run env PYTHONPATH=. pex . workload-collocation-agent -v --cache-dir=.pex-build --output=dist/wca-prm.pex -m wca.main:main
	./dist/wca-prm.pex --version


check: flake8

dist: package

clean:
	@echo Cleaning.
	rm -rf .pex-build
	rm -rf prm.egg-info
	rm -rf dist
	pipenv --rm
