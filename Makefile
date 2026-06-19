PORT ?= 8001
GOAL ?= Which product category has the highest total sales, and what is that total?

.PHONY: gate demo-gate test serve seed ui dev

demo-gate: gate          # alias
gate:
	python -m pytest -q                                     # 1 — suite (FakeModel loop + real test_demo_gate with key)
	@bash harness/scripts/demo_gate.sh $(PORT) "$(GOAL)"    # 2-6 — boot, health, real run, evals, traces

test:
	python -m pytest -q --ignore=tests/test_demo_gate.py    # offline subset (no key needed)

serve:
	python -m agent

seed:
	python -m agent.seed

dev:                                                        # start backend + frontend together (Ctrl-C kills both)
	@trap 'kill 0' INT; python -m agent & cd ui && npm run dev

ui:
	cd ui && npm run dev
