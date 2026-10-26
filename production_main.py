"""Module 4 production entry point; automatically persists traces, costs and results."""
import argparse
import json
import logging
import os
from pathlib import Path
from pydantic import Field
from dotenv import load_dotenv
from orchestration.models import StrictModel
from orchestration.llm import ChatModel
from orchestration.observability import Runtime, ROLE, agent_span
from orchestration.team_graph import build_team
from tools.pytest_runner import PytestRunner

BST_TASK = 'Build a Python module that implements a binary search tree with insert, search, and in-order traversal methods, with full test coverage.'
BST_CONTRACT = ('Use bst.py with BinarySearchTree(). insert(value) adds an integer and ignores duplicates; '
                'search(value) returns a bool; inorder() returns an ascending list of stored values. '
                'Cover empty trees, zero, negative values, duplicates, missing values and repeated traversal. '
                'Keep the module importable. Use a separate runnable assertion script for initial Coder execution.')


class RunInput(StrictModel):
    requirement: str = Field(min_length=1,max_length=20000)
    session_id: str = Field(default='module4',pattern=r'^[A-Za-z0-9_-]{1,64}$')


class RoleModels:
    def __init__(self, models, key, base_url):
        self.clients = {role:ChatModel(model,key,base_url) for role,model in models.items()}
    def complete(self, messages):
        return self.clients[ROLE.get()].complete(messages)


def configured_runtime(output):
    models = {r:os.getenv(r.upper()+'_MODEL',default) for r,default in
              [('pm','gpt-4o'),('coder','gpt-4o-mini'),('qa','gpt-4o-mini')]}
    rates = {r:(float(os.getenv(r.upper()+'_INPUT_USD_PER_MILLION',str(a))),
                float(os.getenv(r.upper()+'_OUTPUT_USD_PER_MILLION',str(b))))
             for r,a,b in [('pm',2.5,10),('coder',.15,.60),('qa',.15,.60)]}
    if any(rate < 0 for pair in rates.values() for rate in pair):raise ValueError('Rates cannot be negative')
    return Runtime(output, endpoint=os.getenv('PHOENIX_TRACES_ENDPOINT') or None, models=models, rates=rates,
                   cache_ttl=float(os.getenv('PROMPT_CACHE_TTL_SECONDS','300')),
                   retries=int(os.getenv('CALL_MAX_RETRIES','3')),
                   base_delay=float(os.getenv('RETRY_BASE_DELAY_SECONDS','.25')),
                   cooldown=float(os.getenv('CIRCUIT_COOLDOWN_SECONDS','30')))


@agent_span('qa')
def verify_bst(source, image):
    fixture = Path(__file__).parent/'tests/fixtures/test_bst_acceptance.py'
    execution, records = PytestRunner(image=image).run(source,fixture.read_text())
    passed = [r for r in records if r.get('phase')=='call' and r.get('outcome')=='passed']
    return {'approved':execution.status=='passed' and len(passed)==4,
            'execution':execution.model_dump(),'records':records,
            'fixture_origin':'Documented local fixture; no instructor fixture supplied'}


def run_pipeline(request, runtime, *, model=None, workspace=None, image=None):
    request = RunInput.model_validate(request)
    image = image or os.getenv('EXECUTION_IMAGE','saras-team:module4')
    result = {'approved':False,'run_id':runtime.run_id,'error':None}
    with runtime.run():
        try:
            if os.getenv('CHROMA_HOST'):
                import chromadb
                client=chromadb.HttpClient(host=os.environ['CHROMA_HOST'],port=int(os.getenv('CHROMA_PORT','8000')))
                heartbeat=runtime.tool('chroma.heartbeat',client.heartbeat)
                runtime.event('chroma_ready',heartbeat=heartbeat)
            model = model or RoleModels(runtime.models,os.environ['LLM_API_KEY'],
                                       os.getenv('LLM_BASE_URL','https://api.openai.com/v1'))
            workspace = Path(workspace or os.getenv('WORKSPACE_DIR','workspace'))/request.session_id
            team=build_team(model,workspace,os.getenv('CHROMA_DIR','.chroma'),session_id=request.session_id)
            team.project.coder.tools.runner.image=image
            team.qa.runner.image=image
            state=team.run(request.requirement)
            result['team']=state.model_dump()
            result['approved']=state.final_report.approved
            if result['approved'] and 'BinarySearchTree' in request.requirement:
                result['acceptance']=verify_bst(state.source,image)
                result['approved']=result['acceptance']['approved']
                if not result['approved']:result['error']='Local BST acceptance fixture failed'
            if not state.final_report.approved: result['error']=state.error or state.final_report.reason
        except Exception as exc:
            # No exception messages or credentials in public artifacts.
            result['error']='Pipeline failed: '+type(exc).__name__
            runtime.event('pipeline_error',error_type=type(exc).__name__)
        result['trace_id']=runtime.trace_id
        runtime.event('pipeline_result',approved=result['approved'])
    folder=runtime.output/'results';folder.mkdir(parents=True,exist_ok=True)
    (folder/(runtime.run_id+'.json')).write_text(json.dumps(result,indent=2)+'\n')
    return result


def main():
    load_dotenv()
    logging.basicConfig(level=logging.INFO,format='%(message)s')
    parser=argparse.ArgumentParser()
    parser.add_argument('requirement',nargs='?',default=BST_TASK+'\nLocal contract: '+BST_CONTRACT)
    parser.add_argument('--session',default='module4')
    args=parser.parse_args()
    try:
        request=RunInput(requirement=args.requirement,session_id=args.session)
        runtime=configured_runtime(os.getenv('OUTPUT_ROOT','docs'))
    except Exception as exc:
        print(json.dumps({'approved':False,'error':'Invalid configuration: '+type(exc).__name__}))
        return 1
    result=run_pipeline(request,runtime)
    print(json.dumps({'approved':result['approved'],'run_id':result['run_id'],
                      'trace_id':result.get('trace_id'),'error':result['error']}))
    return 0 if result['approved'] else 1


if __name__=='__main__':raise SystemExit(main())
