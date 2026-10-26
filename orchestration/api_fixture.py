"""Run the documented local request fixture against generated Flask code in Docker."""
import json
import tempfile
from pathlib import Path
from tools.files import FileTools
from tools.execution import CodeRunner

FIXTURE = Path(__file__).resolve().parents[1] / 'tests/fixtures/api_requests.json'
DRIVER = '''import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from app import app
cases = json.loads(pathlib.Path('_acceptance_cases.json').read_text())['cases']
client = app.test_client()
results = []
for case in cases:
    kwargs = {key:case[key] for key in ('json','data','content_type') if key in case}
    response = client.open(case['path'], method=case['method'], **kwargs)
    passed = response.status_code == case['status']
    if 'response' in case:
        passed = passed and response.get_json(silent=True) == case['response']
    results.append({'name':case['name'], 'passed':passed, 'status':response.status_code,
                    'body':response.get_json(silent=True)})
print(json.dumps(results))
assert all(r['passed'] for r in results), 'API request fixture failed'
'''


def verify_api_source(source, image='coder-python-api:module2', backend='docker'):
    with tempfile.TemporaryDirectory(prefix='api-fixture-') as folder:
        files = FileTools(folder)
        for name, content in source.items():
            files.write_file(name, content)
        files.write_file('_acceptance_probe.py', DRIVER)
        files.write_file('_acceptance_cases.json', FIXTURE.read_text())
        result = CodeRunner(files, image=image, backend=backend).run_code('_acceptance_probe.py')
        if result.status == 'passed':
            try:
                records = json.loads(result.stdout)
                cases = json.loads(FIXTURE.read_text())['cases']
                assert len(records) == len(cases)
                assert all(r['passed'] is True and r['name'] == c['name'] and r['status'] == c['status']
                           for r,c in zip(records,cases))
            except (ValueError, TypeError, KeyError, AssertionError):
                result = result.model_copy(update={'status':'failed',
                    'stderr':result.stderr + '\nMissing or invalid acceptance-fixture results'})
        return result
