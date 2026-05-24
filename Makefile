BACKEND_DIR := backend
FRONTEND_DIR := frontend
PYTEST := python -m pytest

.PHONY: test-unit test-integration test-e2e test-frontend test-all test-ci

test-unit:
	cd $(BACKEND_DIR) && $(PYTEST) \
		tests/test_rag_service.py tests/test_intent_router.py \
		tests/test_rag.py tests/unit/test_intent_router.py \
		tests/test_booking_agent.py tests/test_llm_router.py \
		tests/test_drift_detector.py tests/test_metrics.py \
		tests/test_resolve_predictions.py tests/test_retrain_task.py \
		--cov=. --cov-report=term-missing -v

test-integration:
	cd $(BACKEND_DIR) && $(PYTEST) \
		tests/test_api.py tests/test_voice.py tests/test_voice_preprod.py \
		tests/test_scheduling_agent.py tests/test_ops_agent.py \
		tests/test_admin_api.py tests/test_patient_frontend_contract.py \
		tests/integration \
		--cov=. --cov-report=term-missing -v

test-e2e:
	cd $(BACKEND_DIR) && $(PYTEST) tests/integration -v --timeout=60

test-frontend:
	cd $(FRONTEND_DIR) && npm run test:patient-contract && npm run test:admin-contract

test-all:
	$(MAKE) test-unit
	$(MAKE) test-integration
	$(MAKE) test-e2e
	$(MAKE) test-frontend

test-ci:
	docker-compose -f docker-compose.dev.yml up -d
	sleep 30
	$(MAKE) test-all
	docker-compose -f docker-compose.dev.yml down
