# Endpoints come from the azd environment and credentials from `az login`; no keys.
AZD_ENV = eval "$$(azd env get-values | grep -E '^AZURE_(EVENTHUBS_NAMESPACE|EVENTHUB_NAME|COSMOS_ENDPOINT|COSMOS_DATABASE)=')" && \
	export AZURE_EVENTHUBS_NAMESPACE AZURE_EVENTHUB_NAME AZURE_COSMOS_ENDPOINT AZURE_COSMOS_DATABASE

.PHONY: check m01 stream-m01 tune-detector dev-feeds heldout-feeds scoreboard deploy-web video-clips

check:
	uv run ruff check . && uv run ruff format --check .
	uv run python scripts/check_engine_isolation.py
	uv run pytest -q

m01:
	uv run proofline-engine generate --script engine/scripts/planted/m01.yaml --out data/m01/

# Gate 2: the Match Clock replays m01 through Event Hubs; ingest stores it in Cosmos and
# the detector opens its cases there.
stream-m01: m01
	$(AZD_ENV) && run=m01-$$(date +%s) && \
	{ uv run proofline ingest --match m01 --run-id $$run & pid=$$!; } && \
	sleep 15 && uv run proofline-engine clock --match-dir data/m01 --run-id $$run && \
	wait $$pid

tune-detector:
	uv run python scripts/tune_detector.py

# The dev split's matches as feeds (events and metadata only) for the product's batch runs;
# the scripts and ground truth stay sealed in engine/suites.
dev-feeds:
	for script in engine/suites/*/dev/scripts/*.yaml; do \
		uv run proofline-engine generate --script $$script --out data/dev/$$(basename $$script .yaml)/ || exit 1; \
	done

# The held-out split's feeds, the same way: run once, after the agents are frozen.
heldout-feeds:
	for script in engine/suites/*/heldout/scripts/*.yaml; do \
		uv run proofline-engine generate --script $$script --out data/heldout/$$(basename $$script .yaml)/ || exit 1; \
	done

# After any new evaluation record: the README's scoreboard block and the console's fixture.
scoreboard:
	uv run python -m eval scoreboard --records eval/records --write README.md > /dev/null
	uv run python surfaces/web/scripts/export_scoreboard.py

# The public link: the replay build on the azd environment's Static Web App, pointed at the
# environment's live API for typed questions. The deployment token is read at deploy time and
# never stored.
deploy-web:
	api=$$(azd env get-value API_URL) && cd surfaces/web && corepack pnpm install --frozen-lockfile \
		&& corepack pnpm fixtures && VITE_PROOFLINE_API=$$api corepack pnpm build
	rg=$$(azd env get-value AZURE_RESOURCE_GROUP) && \
	name=$$(az staticwebapp list -g $$rg --query '[0].name' -o tsv) && \
	SWA_CLI_DEPLOYMENT_TOKEN=$$(az staticwebapp secrets list -n $$name -g $$rg --query properties.apiKey -o tsv) \
	npx -y @azure/static-web-apps-cli@2.0.10 deploy surfaces/web/dist --env production

# The demo video's on-screen beats as silent 1080p clips of the public link (one real live
# question included), into runs/video/ for narration and editing.
video-clips:
	node --experimental-websocket surfaces/web/scripts/record_beats.mjs $$(azd env get-value WEB_URL) runs/video
