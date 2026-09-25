SHELL := /bin/bash

.PHONY: plan bootstrap migrate verify backup restore-test

plan:
	@./scripts/plan.sh

bootstrap:
	@./scripts/bootstrap.sh

migrate:
	@./scripts/migrate.sh

verify:
	@./scripts/verify.sh

backup:
	@./scripts/backup-postgres.sh

restore-test:
	@./scripts/restore-test.sh
