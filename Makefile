SHELL := /bin/bash

.PHONY: plan bootstrap migrate verify backup restore-test embedding-build embedding-deploy embedding-verify openai-proxy-build openai-proxy-deploy openai-proxy-verify birdynator-build birdynator-deploy birdynator-verify

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

openai-proxy-build:
	@bash ./scripts/build-openai-proxy.sh

openai-proxy-deploy:
	@bash ./scripts/deploy-openai-proxy.sh

openai-proxy-verify:
	@bash ./scripts/verify-openai-proxy.sh

birdynator-build:
	@bash ./scripts/build-birdynator.sh

birdynator-deploy:
	@bash ./scripts/deploy-birdynator.sh

birdynator-verify:
	@bash ./scripts/verify-birdynator.sh
