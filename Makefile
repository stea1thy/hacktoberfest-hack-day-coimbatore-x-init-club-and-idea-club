.PHONY: run test eval

run:
	streamlit run app.py

test:
	pytest -q

eval:
	python eval/run_eval.py
