"""Opt-in Docker checks for our own request fixture, not the instructor's fixture."""
import json
import os
import pytest
from orchestration.api_fixture import verify_api_source

pytestmark = pytest.mark.skipif(os.getenv('RUN_MODULE2_DOCKER_TESTS') != '1',
                               reason='Build coder-python-api:module2 and opt into Docker checks')

# Trusted reference implementation used ONLY to test the verifier itself.
REFERENCE = '''from flask import Flask, request, jsonify
app = Flask(__name__)
@app.get('/health')
def health(): return jsonify(status='ok')
@app.post('/echo')
def echo():
    if not request.is_json: return jsonify(error='JSON required'), 415
    body = request.get_json(silent=True)
    if not isinstance(body, dict): return jsonify(error='object required'), 400
    return jsonify(body)
'''


def test_request_fixture_accepts_correct_api():
    result = verify_api_source({'app.py': REFERENCE})
    assert result.status == 'passed', result
    records = json.loads(result.stdout)
    assert len(records) == 8 and all(r['passed'] for r in records)


def test_request_fixture_rejects_missing_validation():
    source = REFERENCE.replace("if not isinstance(body, dict): return jsonify(error='object required'), 400", 'if False: pass')
    result = verify_api_source({'app.py': source})
    assert result.status == 'failed'
    assert any(not r['passed'] for r in json.loads(result.stdout))


def test_request_fixture_rejects_early_success_exit():
    result = verify_api_source({'app.py': 'raise SystemExit(0)'})
    assert result.status == 'failed'
    assert 'Missing or invalid' in result.stderr
