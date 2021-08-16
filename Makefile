SHELL := /bin/bash
HELM_CHART=./charts/aporia-importer
HELM_CHART_REPO=aporia-ai/public-helm-charts
DEFAULT_VERSION=1.0.0

# Install dependencies
install-deps:
	@echo [!] Installing Semver
	@sudo wget https://raw.githubusercontent.com/fsaintjacques/semver-tool/master/src/semver -O /usr/bin/semver
	@sudo chmod +x /usr/bin/semver

	@echo [!] Installing yq
	@sudo wget https://github.com/mikefarah/yq/releases/download/v4.6.1/yq_linux_amd64 -O /usr/bin/yq && sudo chmod +x /usr/bin/yq

	@echo [!] Installing Poetry + Nox
	@sudo apt install python3-setuptools
	@sudo pip3 install poetry nox --upgrade

test:
	@echo [!] Running tests
	@nox

# Build docker image
docker-build:
	@echo [!] Building Docker image with tag: $(IMAGE_NAME)
	@docker build -f Dockerfile --no-cache -t $(IMAGE_NAME) .

# Tag docker image
docker-tag:
	$(eval GIT_REVISION=$(shell git rev-parse HEAD | cut -c1-7))
	@echo [!] Tagging $(IMAGE_NAME) image with $(IMAGE_NAME):$(GIT_REVISION)
	@docker tag $(IMAGE_NAME):latest $(IMAGE_NAME):$(GIT_REVISION)

	$(eval VERSION=$(shell git for-each-ref --sort=-v:refname --count=1 refs/tags/[0-9]*.[0-9]*.[0-9]* refs/tags/v[0-9]*.[0-9]*.[0-9]* | cut -d / -f 3-))
	@if [ -n $(VERSION) ]; then \
		echo [!] Tagging $(IMAGE_NAME) image with $(IMAGE_NAME):latest; \
		docker tag $(IMAGE_NAME):latest $(IMAGE_NAME):latest; \
		echo [!] Tagging $(IMAGE_NAME) image with $(IMAGE_NAME):$(VERSION); \
		docker tag $(IMAGE_NAME):latest $(IMAGE_NAME):$(VERSION); \
	fi

# Push image to docker registry
docker-push:
	$(eval GIT_REVISION=$(shell git rev-parse HEAD | cut -c1-7))
	@echo [!] Pushing $(IMAGE_NAME):$(GIT_REVISION)
	@docker push $(IMAGE_NAME):$(GIT_REVISION)

	$(eval VERSION=$(shell git for-each-ref --sort=-v:refname --count=1 refs/tags/[0-9]*.[0-9]*.[0-9]* refs/tags/v[0-9]*.[0-9]*.[0-9]* | cut -d / -f 3-))
	@if [ -n $(VERSION) ]; then \
		echo [!] Pushing $(IMAGE_NAME):latest; \
		docker push $(IMAGE_NAME):latest; \
		echo [!] Pushing $(IMAGE_NAME):$(VERSION); \
		docker push $(IMAGE_NAME):$(VERSION); \
	fi

# Build docker image and push to AWS registry
docker-build-and-push: docker-login docker-build docker-tag docker-push

# Configure helm repo
helm-configure:
	@echo [!] Adding $(HELM_CHART_REPO) helm repo
	@helm repo add --username camparibot --password $(CAMPARIBOT_TOKEN) aporia-helm-charts https://raw.githubusercontent.com/$(HELM_CHART_REPO)/main

# Push chart to helm repository
helm-push:
	@echo [!] Packaging helm chart
	@helm package $(HELM_CHART)

	$(eval PACKAGE_FILENAME=$(shell helm show chart $(HELM_CHART) | yq e '.name' - )-$(shell helm show chart $(HELM_CHART) | yq e '.version' - ).tgz)

	@echo [!] Pushing helm chart to repo
	@rm -rf /tmp/helm-charts && \
		git clone https://camparibot:$(CAMPARIBOT_TOKEN)@github.com/$(HELM_CHART_REPO).git /tmp/helm-charts && \
		mv $(PACKAGE_FILENAME) /tmp/helm-charts
		cd /tmp/helm-charts && \
		helm repo index . && \
		git add index.yaml $(PACKAGE_FILENAME) && \
		git commit -m "$(IMAGE_NAME) $(shell helm show chart $(HELM_CHART) | yq e '.version' - )" && \
		git push

# Bump version
bump-version:
	$(eval CURRENT_VERSION=$(shell git for-each-ref --sort=-v:refname --count=1 refs/tags/[0-9]*.[0-9]*.[0-9]* refs/tags/v[0-9]*.[0-9]*.[0-9]* | cut -d / -f 3-))
	$(eval NEW_VERSION=v$(shell \
		if [ -z $(CURRENT_VERSION) ]; then \
			echo $(DEFAULT_VERSION); \
		else \
			semver bump patch $(CURRENT_VERSION); \
		fi; \
	))
	$(eval CURRENT_BRANCH=$(shell git rev-parse --abbrev-ref HEAD))
	$(eval BRANCH_PROTECTION_PATTERN=$(shell \
		if [[ $(CURRENT_BRANCH) == release/* ]]; then \
			echo "release/*"; \
		else \
			echo $(CURRENT_BRANCH); \
		fi; \
	))
	$(eval REPOSITORY_NAME=$(shell echo "$(GITHUB_REPOSITORY)" | cut -d / -f 2))

	@git log -1 --pretty="%B" > /tmp/commit-message
	@sed -i '1s/^/\[$(NEW_VERSION)] /' /tmp/commit-message

	@echo [!] Bumping version from $(CURRENT_VERSION) to $(NEW_VERSION)

	@poetry version $(NEW_VERSION) || true
	@git add pyproject.toml || true

	yq e '.appVersion = "$(NEW_VERSION)"' -i $(HELM_CHART)/Chart.yaml

	git add $(HELM_CHART)/Chart.yaml
	git commit -F /tmp/commit-message --amend --no-edit

	git tag -a -m "Version $(NEW_VERSION)" $(NEW_VERSION)

	@BRANCH_PROTECTION_ID=`curl https://api.github.com/graphql \
		-H "Authorization: bearer $(CAMPARIBOT_TOKEN)" -H "Content-Type: application/json" \
		-X POST -d '{ "query": "query { repository(name: \"$(REPOSITORY_NAME)\", owner: \"aporia-ai\") { branchProtectionRules(first: 100) { nodes { id, pattern } } } }" }' | \
		jq -r '.data.repository.branchProtectionRules.nodes | .[] | select(.pattern == "$(BRANCH_PROTECTION_PATTERN)") | .id'`; \
	if [ ! -z $$BRANCH_PROTECTION_ID ]; \
	then \
		echo [!] Temporarily Change GitHub branch protection pattern \(to disable it for our branch\); \
		curl https://api.github.com/graphql \
			-H "Authorization: bearer $(CAMPARIBOT_TOKEN)" -H "Content-Type: application/json" \
			-X POST -d "{ \"query\": \"mutation { updateBranchProtectionRule(input: { branchProtectionRuleId: \\\"$$BRANCH_PROTECTION_ID\\\", pattern: \\\"__this-branch-does-not-exist__\\\"  } ) { clientMutationId } }\" }"; \
		trap '\
			echo [!] Re-enabling GitHub branch protection for our pattern; \
			curl https://api.github.com/graphql \
				-H "Authorization: bearer $(CAMPARIBOT_TOKEN)" -H "Content-Type: application/json" \
				-X POST -d "{ \"query\": \"mutation { updateBranchProtectionRule(input: { branchProtectionRuleId: \\\"$$BRANCH_PROTECTION_ID\\\", pattern: \\\"$(BRANCH_PROTECTION_PATTERN)\\\"  } ) { clientMutationId } }\" }"; \
		' EXIT; \
	fi; \
	echo [!] Git Push; \
	git push --force;

	echo "::set-output name=bumped_version_commit_hash::`git log --pretty=format:'%H' -n 1`";

deploy: docker-build-and-push helm-configure helm-push
