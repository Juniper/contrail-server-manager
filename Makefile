all: deps lint test build

.PHONY: docker

deps: ## Setup the go dependencies

lint: ## Runs gometalinter on the source code

test: ## Run go test with race and coverage args

build: ## Run go build

generate: ## Run the source code generator

package: ## Generate the packages

install:

docker-cobbler: ## Generate cobbler docker container
	docker build -t "cobbler" -f docker/cobbler/Dockerfile .

docker-contrail-sm: ## Generate Contrail Server Manager docker container
	docker build -t "contrail-server-manager" -f docker/contrail-sm/Dockerfile .

docker: docker-cobbler docker-contrail-sm

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
