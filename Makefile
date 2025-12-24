PY ?= python3
LATEST := versions/v0.046/spiral_core_v046_frontier-recent-k-fix.py

.PHONY: run latest help

help:
	@echo "Targets:"
	@echo "  make run     # run latest prototype (v0.46)"
	@echo "  make latest  # alias of run"

run: $(LATEST)
	$(PY) $(LATEST)

latest: run

