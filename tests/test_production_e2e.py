"""Opt-in clean Compose acceptance test; makes real model calls."""
import json
import os
from pathlib import Path
import subprocess
import time
import httpx
from uuid import uuid4
import pytest


@pytest.mark.skipif(os.getenv('RUN_MODULE4_COMPOSE')!='1',reason='Opt into live clean Compose deployment')
def test_clean_compose_bst_end_to_end(tmp_path):
    root=Path(__file__).resolve().parents[1]
    project='module4-'+uuid4().hex[:8]
    output=root/'docs'
    evidence=output/'module4'/'deployment'
    evidence.mkdir(parents=True,exist_ok=True)
    before=set((output/'results').glob('*.json')) if (output/'results').exists() else set()
    env={**os.environ,'OUTPUT_DIR':str(output)}
    command=['docker','compose','-p',project]
    # New project name means new services and empty named volumes; no stale workspace.
    up=subprocess.run(command+['up','--build','-d'],cwd=root,env=env,text=True,capture_output=True,timeout=600)
    (evidence/'startup.log').write_text(up.stdout+up.stderr)
    assert up.returncode==0,up.stdout+up.stderr
    wait=subprocess.run(command+['wait','agent'],cwd=root,env=env,text=True,capture_output=True,timeout=900)
    logs=subprocess.run(command+['logs','--no-color'],cwd=root,env=env,text=True,capture_output=True,timeout=30)
    (evidence/'compose.log').write_text(logs.stdout+logs.stderr)
    (evidence/'project-name.txt').write_text(project+'\n')
    assert wait.returncode==0,wait.stdout+wait.stderr
    results=set((output/'results').glob('*.json'))-before
    assert len(results)==1
    result=json.loads(next(iter(results)).read_text())
    assert result['approved'],result.get('error')
    assert result['team']['final_report']['approved']
    assert result['acceptance']['approved']
    assert result['acceptance']['execution']['exit_code']==0
    assert len(result['acceptance']['records'])==4
    code=result['team']['source']['bst.py']
    compile(code,'bst.py','exec')  # Syntax check only; execution already happened inside Docker.
    trace=json.loads((output/'traces'/(result['run_id']+'.json')).read_text())
    spans=trace['spans'];roots=[s for s in spans if s['parent_id'] is None]
    assert len(roots)==1 and len({s['trace_id'] for s in spans})==1
    agents=[s for s in spans if s['attributes'].get('openinference.span.kind')=='AGENT']
    assert {'pm','coder','qa'}<={s['attributes']['agent_name'] for s in agents}
    assert all(s['parent_id']==roots[0]['span_id'] for s in agents)
    assert all({'agent_name','token_count','tool_calls','duration_ms'}<=s['attributes'].keys() for s in agents)
    report=json.loads((output/'cost_reports'/(result['run_id']+'.json')).read_text())
    assert report['total_estimated_usd']==pytest.approx(sum(c['estimated_usd'] for c in report['calls']))
    assert report['unknown_usage_calls']==0
    assert all(report['per_agent'][role]['prompt_tokens']>0 for role in ['pm','coder','qa'])
    records=[json.loads(line) for line in (output/'run_logs'/(result['run_id']+'.jsonl')).read_text().splitlines()]
    events=[r['event'] for r in records]
    assert events.index('chroma_ready')<events.index('agent_started')
    # Assert actual Phoenix ingestion, not only our local exporter.
    dashboard_trace = None
    for _ in range(20):
        response = httpx.get('http://localhost:6006/v1/projects/module4/traces',
                             params={'include_spans':'true'}, timeout=10)
        if response.status_code == 200:
            dashboard_trace = next((t for t in response.json()['data']
                                    if t['trace_id'] == result['trace_id']), None)
            if dashboard_trace and len(dashboard_trace['spans']) == len(spans):
                break
        time.sleep(1)
    assert dashboard_trace is not None, 'Phoenix did not receive the workflow trace'
    assert {s['span_id'] for s in dashboard_trace['spans']} == {s['span_id'] for s in spans}
    (evidence/'phoenix-trace.json').write_text(json.dumps(dashboard_trace,indent=2)+'\n')
    dashboard_spans = []
    cursor = None
    while True:
        response = httpx.get('http://localhost:6006/v1/projects/module4/spans',
                             params={'cursor':cursor} if cursor else {}, timeout=10)
        response.raise_for_status()
        page = response.json()
        dashboard_spans.extend(s for s in page['data'] if s['context']['trace_id']==result['trace_id'])
        cursor = page.get('next_cursor')
        if not cursor: break
    dashboard_agents = [s for s in dashboard_spans if s['span_kind']=='AGENT']
    assert len(dashboard_agents)==len(agents)
    assert all({'agent_name','token_count','tool_calls','duration_ms'}<=s['attributes'].keys()
               for s in dashboard_agents)
    (evidence/'phoenix-spans.json').write_text(json.dumps(dashboard_spans,indent=2)+'\n')
    # Keep successful services up so the assessor can inspect the actual Phoenix dashboard.
