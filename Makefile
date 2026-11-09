# Test and inspection entry points for the spitballing plugin.
#
# The kernel is imported as `tools.spitball`, which only resolves when the
# plugin root is on the path -- so every target sets PYTHONPATH explicitly
# rather than relying on cwd, as the skill does via ${CLAUDE_PLUGIN_ROOT}.

PYTHON ?= python3
ROOT   := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
PY     := PYTHONPATH="$(ROOT)" $(PYTHON)
RUNS   := $(notdir $(wildcard docs/spitball/*))
OUT    ?= build

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show this help
	@grep -hE '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) \
	  | awk -F':.*?## ' '{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'
	@echo
	@echo "  runs: $(RUNS)"

.PHONY: test
test: unit contract ## Run everything (unit + contract)

# Listed explicitly rather than discovered: discovery would also pull in
# test_contract, which `test` runs as its own target.
UNIT := $(addprefix tools.spitball.tests.test_,band panel fringe cli) \
        tools.eval.tests.test_validate tools.eval.tests.test_audit \
        tools.eval.tests.test_rejudge tools.inspect.tests.test_build

.PHONY: unit
unit: ## Kernel arithmetic tests
	@$(PY) -m unittest $(UNIT)

.PHONY: contract
contract: ## SKILL.md <-> kernel <-> committed-artifact seams
	@$(PY) -m unittest tools.spitball.tests.test_contract -v

.PHONY: check
check: ## Validate run artifacts: make check RUN=docs/spitball/<topic>
	@test -n "$(RUN)" || { echo "usage: make check RUN=<run-dir>"; exit 2; }
	@$(PY) -m tools.eval validate $(RUN)

# eval: one headless run of the staged plugin, archived to eval/runs/NNNN/.
# Spends a full agent run (12-agent panel); not part of `make test`.
BRIEF         ?= eval/briefs/head-cool.json
PROMPT        ?= slash
SKILL_VARIANT ?=
DESC_VARIANT  ?=
MODEL         ?= opus
PERMS         ?= bypassPermissions

.PHONY: eval
eval: ## One headless run: make eval BRIEF= PROMPT=slash|natural|pressure [SKILL_VARIANT= DESC_VARIANT= MODEL= PERMS=]
	@command -v claude >/dev/null || { echo "claude CLI not found" >&2; exit 1; }
	@d=$$($(PY) -m tools.eval run --brief "$(BRIEF)" --prompt "$(PROMPT)" \
	  --skill-variant "$(SKILL_VARIANT)" --desc-variant "$(DESC_VARIANT)" \
	  --model "$(MODEL)" --permission-mode "$(PERMS)") && echo "archived $$d" && \
	$(PY) -m tools.eval audit "$$d"; \
	for t in "$$d"/docs/spitball/*/; do [ -d "$$t" ] && $(PY) -m tools.eval validate "$$t"; done; true

.PHONY: eval-summary
eval-summary: ## Table over runs: make eval-summary RUNS_SEL="eval/runs/0001 eval/runs/0002"
	@$(PY) -m tools.eval audit --summary $(or $(RUNS_SEL),$(wildcard eval/runs/[0-9]*))

.PHONY: inspect
inspect: $(addprefix $(OUT)/,$(addsuffix .html,$(RUNS))) ## Build run inspector pages
	@echo "→ open $(OUT)/index.html"
	@printf '<!doctype html><meta charset=utf-8><title>spitball runs</title>' > $(OUT)/index.html
	@printf '<h1>spitball runs</h1><ul>' >> $(OUT)/index.html
	@for r in $(RUNS); do printf '<li><a href="%s.html">%s</a></li>' "$$r" "$$r" >> $(OUT)/index.html; done
	@printf '</ul>' >> $(OUT)/index.html

$(OUT)/%.html: docs/spitball/% tools/inspect/build.py
	@mkdir -p $(OUT)
	@$(PY) -m tools.inspect $< -o $@

.PHONY: open
open: inspect ## Build and open the inspector in a browser
	@$(PYTHON) -c "import webbrowser,pathlib; \
	  webbrowser.open(pathlib.Path('$(OUT)/index.html').resolve().as_uri())"

# install: register this checkout as a folder marketplace, then install or
# update the plugin from it. Restart Claude Code to pick up changes.
MARKETPLACE := spitballing-marketplace
PLUGIN      := spitballing@$(MARKETPLACE)

.PHONY: install
install: ## Install/update the plugin from this checkout (user scope)
	@command -v claude >/dev/null || { echo "claude CLI not found" >&2; exit 1; }
	@claude plugin marketplace list | grep -q '❯ $(MARKETPLACE)$$' \
	  || claude plugin marketplace add "$(ROOT)"
	@claude plugin marketplace update $(MARKETPLACE)
	@if claude plugin list | grep -q '❯ $(PLUGIN)$$'; \
	  then claude plugin update $(PLUGIN); \
	  else claude plugin install $(PLUGIN); fi

.PHONY: clean
clean: ## Remove build output and caches
	@rm -rf $(OUT) .pytest_cache
	@find tools -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
