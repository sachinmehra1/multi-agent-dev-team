"""Record real linked-list QA plus explicitly labeled deterministic convergence probes."""
import argparse
import json
import os
import shutil
import tempfile
from pathlib import Path
from dotenv import load_dotenv
from orchestration.llm import ChatModel
from orchestration.team_graph import build_team, TeamWorkflow
from agents.coder_agent import CoderReviser
from agents.qa_agent import QAAgent
from tools.files import FileTools
from tools.pytest_runner import PytestRunner
from team_main import GRADING_TASK, LOCAL_CONTRACT


def controlled(destination):
    from tests.module3_fixtures import SeedProject, revision_model, SUITE
    from tests.conftest import ScriptedModel
    for converge, name, limit in [(True,'controlled-repair',5), (False,'controlled-limit',3)]:
        with tempfile.TemporaryDirectory(prefix='module3-probe-') as folder:
            team = TeamWorkflow(SeedProject(), CoderReviser(revision_model(converge),FileTools(folder)),
                                QAAgent(ScriptedModel([SUITE]), PytestRunner()),
                                max_iterations=limit, task_id=name)
            state = team.run(GRADING_TASK+'\n'+LOCAL_CONTRACT)
            record = {'evidence_type':'Controlled fixture: scripted model outputs, real Docker pytest execution',
                      'state':state.model_dump()}
            (destination/(name+'.json')).write_text(json.dumps(record,indent=2)+'\n')
            assert state.final_report.approved == converge
            assert state.qa_iterations == (2 if converge else limit)
            assert len(state.fixes) == (1 if converge else limit-1)
            assert not state.qa_reports[0].approved
            print(name+': '+state.final_report.reason,flush=True)


def live(destination):
    load_dotenv()
    model = ChatModel(os.getenv('LLM_MODEL','gpt-4o'), os.environ['LLM_API_KEY'],
                      os.getenv('LLM_BASE_URL','https://api.openai.com/v1'))
    with tempfile.TemporaryDirectory(prefix='module3-live-') as folder:
        root = Path(folder)
        team = build_team(model,root/'work',root/'chroma',session_id='linked-list-demo')
        trace = []
        for state in team.stream(GRADING_TASK+'\nLocal interface contract: '+LOCAL_CONTRACT):
            trace.append(state.model_dump())
            print(json.dumps({'source_files':list(state.source), 'reflection':state.reflection is not None,
                              'qa_iterations':state.qa_iterations,'error':state.error,
                              'final':state.final_report.model_dump() if state.final_report else None}),flush=True)
        (destination/'live-state-trace.json').write_text(json.dumps(trace,indent=2)+'\n')
        (destination/'live-final-state.json').write_text(state.model_dump_json(indent=2)+'\n')
        generated = destination/'generated'
        if generated.exists(): shutil.rmtree(generated)
        generated.mkdir()
        for name,code in state.source.items():
            path = generated/name
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(code)
        if state.qa_reports:
            (generated/'test_generated.py').write_text(state.qa_reports[-1].test_code)
        (destination/'a2a-messages.json').write_text(json.dumps([m.model_dump() for m in state.messages],indent=2)+'\n')
        assert state.final_report.approved, state.final_report
        assert state.reflection and state.reflection.before != state.reflection.after
        report = state.qa_reports[-1]
        assert report.tests_run >= 4 and report.execution.status == 'passed'
        # The saved QA suite must actually call each of the four public methods.
        import ast
        calls = {n.func.attr for n in ast.walk(ast.parse(report.test_code))
                 if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)}
        assert {'insert','delete','search','reverse'} <= calls
        print('PASS: live PM/Coder/reflection/QA, four methods, actual A2A messages',flush=True)
        live_feedback(destination, model, report)


def live_feedback(destination, model, prior_report):
    """Known faulty fixture, previously live-generated QA suite, actual model repair."""
    from tests.module3_fixtures import BAD_REVERSE
    from tests.conftest import ScriptedModel
    from orchestration.a2a import Broker, Message
    from orchestration.qa_models import ReviewRequest, QAReport, source_digest
    suite = {'code':prior_report.test_code, 'coverage':prior_report.coverage}
    qa = QAAgent(ScriptedModel([suite]), PytestRunner())
    broker = Broker()
    criteria = list(prior_report.coverage)
    source = {'linked_list.py':BAD_REVERSE}
    requirement = GRADING_TASK+'\nLocal interface contract: '+LOCAL_CONTRACT
    with tempfile.TemporaryDirectory(prefix='module3-live-fix-') as folder:
        reviser = CoderReviser(model, FileTools(folder))
        def review(code, iteration):
            request = ReviewRequest(task_id='live-seeded-repair', requirement=requirement,
                acceptance_criteria=criteria, source=code, source_digest=source_digest(code), iteration=iteration)
            return broker.review(Message(sender='coder', receiver='qa', intent='review_request',
                                         payload=request.model_dump()), qa)
        failure = review(source, 1)
        assert failure.intent == 'fix_instruction'
        fix = reviser.fix(source, requirement, failure)
        response = review(fix.after, 2)
        result = QAReport.model_validate(response.payload)
        record = {'evidence_type':'Seeded faulty fixture; unchanged live-generated QA tests; real model Coder repair and Docker retest',
                  'fix':fix.model_dump(), 'result':result.model_dump(), 'messages':broker.log}
        (destination/'live-seeded-repair.json').write_text(json.dumps(record,indent=2)+'\n')
        assert result.approved, result
        print('PASS: seeded failure -> real model Coder repair -> same QA tests pass',flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--controlled-only',action='store_true')
    args = parser.parse_args()
    destination = Path('docs/module3')
    destination.mkdir(parents=True,exist_ok=True)
    controlled(destination)
    if not args.controlled_only:
        live(destination)


if __name__ == '__main__':
    main()
