"""Execute generated tests in the existing isolated subprocess/container boundary."""
import json
import tempfile
from tools.files import FileTools
from tools.execution import CodeRunner

MARKER = '\n__QA_REPORT__='
PYTEST_ARGS = ['-q', '--tb=short', '-p', 'no:cacheprovider', 'qa_tests/test_generated.py']
DRIVER = '''import sys, pathlib, json, os
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] = '1'
import pytest
records=[]
class Reporter:
    def pytest_runtest_logreport(self, report):
        if report.when == 'call' or report.failed or report.skipped:
            records.append({'nodeid':report.nodeid, 'phase':report.when,
                            'outcome':report.outcome, 'detail':str(report.longrepr)[:4000] if report.longrepr else ''})
    def pytest_collectreport(self, report):
        if report.failed:
            records.append({'nodeid':report.nodeid, 'phase':'collection',
                            'outcome':'failed', 'detail':str(report.longrepr)[:4000]})
result=pytest.main(ARGS, plugins=[Reporter()])
print(MARKER + json.dumps({'exit_code':int(result), 'records':records}), flush=True)
sys.exit(int(result))
'''


class PytestRunner:
    def __init__(self, timeout=10, image='coder-python-qa:module3', backend='docker'):
        if not 0 < timeout <= 60:
            raise ValueError('QA timeout must be in (0, 60] seconds')
        self.timeout, self.image, self.backend = timeout, image, backend

    def run(self, source, test_code):
        with tempfile.TemporaryDirectory(prefix='qa-run-') as folder:
            files = FileTools(folder)
            # Only application files are delivered. Coder tests/config cannot replace QA.
            for name, content in source.items():
                if name == 'conftest.py' or name.endswith('/conftest.py') or name.startswith('qa_tests/'):
                    raise ValueError('Reserved QA path')
                files.write_file(name, content)
            files.write_file('qa_tests/test_generated.py', test_code)
            driver = 'ARGS = ' + repr(PYTEST_ARGS) + '\nMARKER = ' + repr(MARKER) + '\n' + DRIVER
            files.write_file('_qa_runner.py', driver)
            execution = CodeRunner(files, timeout=self.timeout, image=self.image,
                                   backend=self.backend).run_code('_qa_runner.py')
        records = []
        try:
            payload = json.loads(execution.stdout.rsplit(MARKER, 1)[1])
            if payload['exit_code'] != execution.exit_code or not isinstance(payload['records'], list):
                raise ValueError('Invalid pytest result')
            records = payload['records']
        except (IndexError, KeyError, ValueError, TypeError):
            if execution.status == 'passed':
                execution = execution.model_copy(update={'status':'failed',
                    'stderr':execution.stderr + '\nMissing valid pytest results'})
        return execution, records
