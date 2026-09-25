SHELL := /bin/bash

.PHONY: plan bootstrap migrate verify backup restore-test embedding-build embedding-deploy embedding-verify

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

embedding-build:
	@./scripts/build-embedding.sh

embedding-deploy:
	@./scripts/deploy-embedding.sh

embedding-verify:
	@./scripts/verify-embedding.sh
