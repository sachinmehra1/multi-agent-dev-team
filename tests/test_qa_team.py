import json
import os
from uuid import uuid4
import pytest
from pydantic import ValidationError
from tests.conftest import ScriptedModel
from tests.module3_fixtures import (GOOD, BAD_REVERSE, INITIAL, TESTS, SUITE, CRITERIA,
                                   SeedProject, revision_model)
from agents.qa_agent import QAAgent, validate_suite
from agents.coder_agent import CoderReviser
from orchestration.qa_models import ReviewRequest, QAReport, source_digest
from orchestration.a2a import Message, Broker
from orchestration.team_graph import TeamWorkflow, qa_limit
from tools.files import FileTools
from tools.pytest_runner import PytestRunner


def request(code=GOOD, iteration=1):
    source = {'linked_list.py':code}
    return ReviewRequest(task_id='linked-list', requirement='Implement linked list',
                         acceptance_criteria=CRITERIA, source=source,
                         source_digest=source_digest(source), iteration=iteration)


def qa(backend='trusted-local', timeout=10):
    return QAAgent(ScriptedModel([SUITE]), PytestRunner(backend=backend, timeout=timeout))


def workflow(tmp_path, converge=True, limit=5):
    return TeamWorkflow(SeedProject(), CoderReviser(revision_model(converge), FileTools(tmp_path)),
                        qa(), max_iterations=limit, task_id='linked-list')


def test_qa_schema_links_failures_to_assertions():
    report = qa().review(request(BAD_REVERSE))
    QAReport.model_validate_json(report.model_dump_json())
    assert not report.approved and report.tests_run == 4
    issue = next(i for i in report.issues if 'test_reverse' in i.location)
    assert 'assert' in issue.description and issue.fix_instruction
    assert issue.acceptance_criteria == ['reverse changes order']
    assert report.execution.exit_code == 1
    assert report.timeout_seconds == 10
    assert 'pytest' in report.command


def test_successful_team_reflects_then_fixes_via_a2a(tmp_path):
    team = workflow(tmp_path)
    states = list(team.stream('Implement the four linked-list methods'))
    final = states[-1]
    assert final.final_report.approved and final.final_report.reason == 'all_tests_passed'
    assert final.qa_iterations == 2 and len(final.fixes) == 1
    assert final.reflection.before == {'linked_list.py':INITIAL}
    assert final.reflection.after == {'linked_list.py':BAD_REVERSE}
    assert next(s for s in states if s.reflection).qa_iterations == 0
    assert final.qa_reports[0].source_digest == source_digest(final.reflection.after)
    assert not final.qa_reports[0].approved and final.qa_reports[1].approved
    assert final.fixes[0].feedback == final.qa_reports[0]
    assert final.qa_reports[0].test_code == final.qa_reports[1].test_code == TESTS
    assert final.source == {'linked_list.py':GOOD}
    assert final.project.complete and final.project.code_output['linked_list.py'] == GOOD
    assert [m.intent for m in final.messages] == ['review_request','fix_instruction','review_request','approved']
    for i in (0,2):
        assert final.messages[i].correlation_id == final.messages[i+1].correlation_id
        assert final.messages[i].payload['task_id'] == final.messages[i+1].payload['task_id']
    assert all(s.qa_iterations <= 5 for s in states)


def test_maximum_iteration_exit_lists_unresolved_issues(tmp_path):
    final = workflow(tmp_path, converge=False, limit=3).run('Implement linked list')
    assert not final.final_report.approved and not final.project.complete
    assert final.final_report.reason == 'iteration_limit'
    assert final.qa_iterations == len(final.qa_reports) == 3
    assert len(final.fixes) == 2 and len(final.messages) == 6
    assert any('test_reverse' in i.location for i in final.final_report.unresolved_issues)
    assert all(not r.approved for r in final.qa_reports)


def test_limit_one_does_not_attempt_revision(tmp_path):
    final = workflow(tmp_path, limit=1).run('linked list')
    assert final.qa_iterations == 1 and not final.fixes
    assert final.final_report.unresolved_issues


def test_limit_environment(monkeypatch):
    monkeypatch.delenv('QA_MAX_ITERATIONS', raising=False)
    assert qa_limit() == 5
    monkeypatch.setenv('QA_MAX_ITERATIONS','2')
    assert qa_limit() == 2
    for value in ['0','21','abc']:
        monkeypatch.setenv('QA_MAX_ITERATIONS',value)
        with pytest.raises(ValueError): qa_limit()


def test_cannot_claim_approval_on_failures():
    data = qa().review(request(BAD_REVERSE)).model_dump()
    data['approved'] = True
    with pytest.raises(ValidationError): QAReport.model_validate(data)


def test_broker_serializes_and_routes():
    broker = Broker()
    message = Message(sender='coder',receiver='qa',intent='review_request',payload=request().model_dump())
    broker.send(message)
    message.payload['requirement'] = 'mutated'
    delivered = broker.receive('qa')
    assert delivered.payload['requirement'] != 'mutated'
    assert broker.log[0]['intent'] == 'review_request'
    with pytest.raises(TimeoutError): broker.receive('coder',timeout=.01)


@pytest.mark.parametrize('changes',[{'sender':'pm'}, {'receiver':'coder'}, {'intent':'delete'},
                                    {'correlation_id':'not-a-uuid'}, {'sender':'qa'}])
def test_invalid_protocol_messages_rejected(changes):
    data = dict(sender='coder',receiver='qa',intent='review_request',payload=request().model_dump())
    data.update(changes)
    with pytest.raises(ValidationError): Message(**data)


def test_broker_rejects_stale_source_and_unknown_correlation():
    agent = qa()
    broker = Broker()
    message = Message(sender='coder',receiver='qa',intent='review_request',payload=request(BAD_REVERSE).model_dump())
    broker.send(message)
    response = agent.handle(broker.receive('qa'))
    wrong = response.model_copy(update={'correlation_id':str(uuid4())})
    with pytest.raises(ValueError): broker.send(wrong)
    response.payload['source_digest'] = 'wrong'
    with pytest.raises(ValueError): broker.send(response)


def test_qa_does_not_regenerate_tests_to_hide_failures():
    agent = qa()
    assert not agent.review(request(BAD_REVERSE)).approved
    assert agent.review(request(GOOD,2)).approved
    assert len(agent.model.messages) == 1


def test_invalid_test_suite_is_reported_not_approved():
    agent = QAAgent(ScriptedModel([{'code':'def test_nothing(): pass', 'coverage':SUITE['coverage']}]),
                    PytestRunner(backend='trusted-local'))
    report = agent.review(request())
    assert not report.approved and report.tests_run == 0 and report.issues


def test_missing_pytest_results_cannot_pass():
    execution, records = PytestRunner(backend='trusted-local').run(
        {'linked_list.py':'raise SystemExit(0)'}, TESTS)
    assert execution.status == 'failed' and not any(r.get('outcome') == 'passed' for r in records)


def test_qa_timeout_reports_unresolved_failure():
    agent = QAAgent(ScriptedModel([SUITE]),PytestRunner(backend='trusted-local',timeout=.2))
    report = agent.review(request('while True: pass'))
    assert not report.approved and report.execution.status == 'timeout' and report.issues


def test_reflection_requires_substantive_revision(tmp_path):
    from tests.module3_fixtures import CRITIQUE
    model = ScriptedModel([CRITIQUE, {'explanation':'Only a comment','files':{'linked_list.py':GOOD+'\n# same\n'}}])
    reviser = CoderReviser(model,FileTools(tmp_path))
    with pytest.raises(ValueError): reviser.reflect({'linked_list.py':GOOD},'linked list')


@pytest.mark.skipif(os.getenv('RUN_MODULE3_DOCKER_TESTS') != '1',reason='Build QA image and opt into Docker')
def test_real_qa_docker_execution_and_timeout():
    agent = qa(backend='docker')
    assert not agent.review(request(BAD_REVERSE)).approved
    assert agent.review(request(GOOD,2)).approved
    timeout_agent = qa(backend='docker',timeout=1)
    report = timeout_agent.review(request('while True: pass'))
    assert report.execution.status == 'timeout' and not report.approved


def test_docstring_only_reflection_is_not_a_revision(tmp_path):
    from tests.module3_fixtures import CRITIQUE
    changed = GOOD.replace('class LinkedList:\n', 'class LinkedList:\n    """A linked list."""\n')
    model = ScriptedModel([CRITIQUE, {'explanation':'Only documentation','files':{'linked_list.py':changed}}])
    with pytest.raises(ValueError):
        CoderReviser(model,FileTools(tmp_path)).reflect({'linked_list.py':GOOD},'linked list')


def test_forged_approval_intent_rejected():
    report = qa().review(request(BAD_REVERSE))
    with pytest.raises(ValidationError):
        Message(sender='qa',receiver='coder',intent='approved',payload=report.model_dump())


def test_coder_rejects_feedback_for_a_different_source(tmp_path):
    agent = qa()
    message = Message(sender='coder',receiver='qa',intent='review_request',payload=request(BAD_REVERSE).model_dump())
    feedback = agent.handle(message)
    model = ScriptedModel([])
    with pytest.raises(ValueError):
        CoderReviser(model,FileTools(tmp_path)).fix({'linked_list.py':GOOD},'linked list',feedback)
    assert not model.messages
