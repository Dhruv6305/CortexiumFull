import ast, sys, os
os.chdir(os.path.dirname(os.path.abspath(__file__)))
results = []

for f in ['ml_pipeline.py', 'server.py']:
    try:
        ast.parse(open(f, encoding='utf-8').read())
        results.append(f'SYNTAX_OK: {f}')
    except SyntaxError as e:
        results.append(f'SYNTAX_ERR: {f}: {e}')

sys.path.insert(0, '.')
try:
    from ml_pipeline import (BaselineCatBoostPredictor, PersonalizedCatBoostPredictor,
        DataCollector, train_personalized_model, get_active_metrics,
        BASELINE_MODEL_PATH, PERSONALIZED_MODEL_PATH, PERSONALIZED_METRICS_PATH,
        FEATURE_COLUMNS, TARGET_COLUMN, train_and_evaluate)
    results.append('IMPORT_OK: ml_pipeline')
except Exception as e:
    results.append(f'IMPORT_ERR: {e}')
    with open('check_out.txt', 'w') as fh:
        fh.write('\n'.join(results))
    sys.exit(1)

try:
    bp = BaselineCatBoostPredictor()
    results.append(f'BASELINE_LOAD: {bp.is_loaded}')
    if bp.is_loaded:
        surf, prob = bp.predict('laptop',
            {'table': (10,10,400,300), 'chair': (450,10,620,300)},
            (50,50,200,180), 0.85, (480,640))
        results.append(f'BASELINE_PREDICT: laptop->{surf} prob={round(prob,3)}')
except Exception as e:
    results.append(f'BASELINE_ERR: {e}')

try:
    m = get_active_metrics()
    results.append(f'ACTIVE_METRICS_TYPE: {m.get("model_type") if m else None}')
    results.append(f'ACTIVE_METRICS_ACC: {m.get("accuracy") if m else None}')
except Exception as e:
    results.append(f'METRICS_ERR: {e}')

try:
    pp = PersonalizedCatBoostPredictor()
    results.append(f'PERSONALIZED_LOAD: {pp.is_loaded}')
except Exception as e:
    results.append(f'PERSONALIZED_ERR: {e}')

results.append(f'FEATURE_COUNT: {len(FEATURE_COLUMNS)}')
results.append(f'BASELINE_FILE_EXISTS: {os.path.exists(BASELINE_MODEL_PATH)}')
results.append(f'PERSONALIZED_EXISTS: {os.path.exists(PERSONALIZED_MODEL_PATH)}')

with open('check_out.txt', 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(results) + '\n')
