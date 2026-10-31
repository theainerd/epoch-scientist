# Epoch Scientist - common tasks. Paths can be overridden: AAB_DIR, MS_WORK, FFMPEG.
PY ?= python
WORK ?= $(if $(MS_WORK),$(MS_WORK),work)
AAB ?= $(if $(AAB_DIR),$(AAB_DIR),external/AstroAgentBench)
.PHONY: fetch check-verifiers pack-aeossp smoke sealed-aeossp sealed-revisit yardstick-revisit kaggle-datasets videos

fetch:            ## download AstroAgentBench (MIT) into external/
	bash data/fetch_astroagentbench.sh

check-verifiers:  ## frozen verifiers == official code (byte-identical)
	$(PY) data/check_verifier_identity.py

pack-aeossp:      ## pre-compute AEOSSP observation opportunities for all splits (~1-2 min per mission)
	bash data/build_aeossp_pack.sh

smoke:            ## quick reproduction checks
	bash analysis/smoke.sh

sealed-aeossp:    ## score start + Muse best on all sealed AEOSSP missions (needs pack-aeossp)
	bash analysis/sealed_eval.sh aeossp p0 tasks/aeossp/program_0/src/program.py
	bash analysis/sealed_eval.sh aeossp w2c8 results/aeossp/programs/best_w2_cycle8.py

sealed-revisit:   ## score start + Muse best on the 11 sealed Revisit missions
	bash analysis/sealed_eval.sh revisit p0 tasks/revisit/program_0/src/program.py
	bash analysis/sealed_eval.sh revisit w2c10 results/revisit/programs/best_w2_cycle10.py
	$(PY) analysis/revisit_paper_metric.py p0 w2c10

yardstick-revisit: ## benchmark solver j2_rgt_set_cover on all Revisit missions (slow: ~30 min per mission)
	bash yardsticks/revisit_run_j2.sh && $(PY) analysis/score_revisit_yardstick.py

kaggle-datasets:  ## dev-only Kaggle datasets for a new blind run (KAGGLE_USER=<you>)
	$(PY) data/build_kaggle_datasets.py $(KAGGLE_USER)

videos:           ## re-render the 4 videos into work/videos (needs sealed outputs + replays)
	bash viz/make_videos.sh
