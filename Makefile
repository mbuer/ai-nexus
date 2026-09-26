SHELL := /bin/bash

.PHONY: plan bootstrap migrate verify repo-check backup restore-test postgres-harden embedding-build embedding-deploy embedding-verify openai-proxy-build openai-proxy-deploy openai-proxy-verify birdnet-proxy-build birdnet-proxy-deploy birdnet-proxy-verify birdynator-build birdynator-deploy birdynator-update birdynator-verify

plan:
	@./scripts/plan.sh

bootstrap:
	@./scripts/bootstrap.sh

migrate:
	@./scripts/migrate.sh

verify:
	@./scripts/verify.sh

repo-check:
	@bash ./scripts/repo-check.sh

backup:
	@./scripts/backup-postgres.sh

restore-test:
	@./scripts/restore-test.sh

postgres-harden:
	@bash ./scripts/harden-postgres.sh

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

birdnet-proxy-build:
	@bash ./scripts/build-birdnet-proxy.sh

birdnet-proxy-deploy:
	@bash ./scripts/deploy-birdnet-proxy.sh

birdnet-proxy-verify:
	@bash ./scripts/verify-birdnet-proxy.sh

birdynator-build:
	@bash ./scripts/build-birdynator.sh

birdynator-deploy:
	@bash ./scripts/deploy-birdynator.sh

birdynator-update:
	@bash ./scripts/update-birdynator.sh

birdynator-verify:
	@bash ./scripts/verify-birdynator.sh
