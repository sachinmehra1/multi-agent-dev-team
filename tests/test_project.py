import json
from unittest.mock import Mock
import pytest
from pydantic import ValidationError
from agents.pm_agent import ProductManager, consolidate_tasks
from orchestration.project_state import CodingTask, TechnicalSpec, ProjectState, Handoff
from orchestration.project_graph import ProjectWorkflow
from orchestration.models import AgentOutput, ExecutionResult
from tests.conftest import ScriptedModel


def task(i):
    return CodingTask(task_id=f't{i}', description=f'Implement requirement {i}',
                      acceptance_criteria=[f'Behavior {i} works'], priority=1 + i % 5)


def spec(count=2):
    return TechnicalSpec(name='Health and echo API', description='Validated JSON API',
                         acceptance_criteria=['health works', 'echo validates inputs'],
                         tasks=[task(i) for i in range(count)])


class FakeCoder:
    def __init__(self, files, fail_at=None):
        self.tools = Mock(files=files)
        self.prompts = []
        self.fail_at = fail_at

    def run(self, prompt, session_id):
        self.prompts.append(prompt)
        index = len(self.prompts)
        failed = index == self.fail_at
        source = f'print({index})\n'
        name = f'task{index}.py'
        self.tools.files.write_file(name, source)
        return AgentOutput(task_complete=not failed, code=source,
                           explanation='Implemented requested task', plan=['write','run'],
                           result=ExecutionResult(status='failed' if failed else 'passed',
                                                  stdout=str(index), exit_code=1 if failed else 0),
                           files_written=[name], iterations_used=3, total_tokens=20,
                           error='Task failed' if failed else None)


def make_workflow(tmp_path, count=2, fail_at=None):
    from tools.files import FileTools
    coder = FakeCoder(FileTools(tmp_path/'workspace'), fail_at)
    model = ScriptedModel([spec(count).model_dump()])
    return ProjectWorkflow(model, coder), coder, model


def test_pm_handoff_integration_through_graph(tmp_path):
    workflow, coder, model = make_workflow(tmp_path)
    states = list(workflow.stream('Build health and echo API with input validation'))
    pm_state = states[1]
    assert pm_state.original_requirement == states[0].original_requirement
    assert pm_state.technical_spec.name and pm_state.technical_spec.description
    assert pm_state.technical_spec.acceptance_criteria
    assert len(pm_state.tasks) == 2
    assert all(isinstance(t, CodingTask) and t.acceptance_criteria for t in pm_state.tasks)
    assert Handoff.model_validate_json(pm_state.handoff.model_dump_json()) == Handoff.for_task(pm_state.tasks[0])
    assert pm_state.handoff.ready
    assert len(model.messages) == 1
    assert states[-1].complete
    for index,prompt in enumerate(coder.prompts):
        assert states[-1].handoff_history[index].model_dump_json() in prompt
        assert pm_state.original_requirement in prompt
    assert 'task1.py' in coder.prompts[1]


def test_status_updates_and_accumulated_code_after_each_task(tmp_path):
    workflow, _, _ = make_workflow(tmp_path, 3)
    states = list(workflow.stream('requirement'))
    completed = [s for s in states if s.progress and s.progress[-1].status == 'completed']
    first = next(s for s in completed if s.current_task_index == 1)
    assert [t.status for t in first.tasks] == ['completed','pending','pending']
    assert list(first.code_output) == ['task1.py']
    final = states[-1]
    assert [t.status for t in final.tasks] == ['completed']*3
    assert list(final.code_output) == ['task1.py','task2.py','task3.py']
    assert [a.task_id for a in final.artifacts] == ['t0','t1','t2']
    assert [e.task_id for e in final.progress if e.status=='completed'] == ['t0','t1','t2']
    assert not final.handoff.ready
    ProjectState.model_validate_json(final.model_dump_json())


@pytest.mark.parametrize('count',[9,17,64])
def test_more_than_eight_consolidates_without_losing_coverage(tmp_path,count):
    workflow, coder, _ = make_workflow(tmp_path,count)
    final = workflow.run('many requirements')
    assert final.complete and 1 <= len(final.tasks) <= 8
    assert len(coder.prompts) == len(final.tasks)
    assert [source for t in final.tasks for source in t.source_task_ids] == [f't{i}' for i in range(count)]
    for original in final.original_tasks:
        merged = next(t for t in final.tasks if original.task_id in t.source_task_ids)
        assert original.description in merged.description
        assert all(c in '\n'.join(merged.acceptance_criteria) for c in original.acceptance_criteria)


def test_failed_task_stops_and_preserves_previous_context(tmp_path):
    workflow,coder,_ = make_workflow(tmp_path,3,fail_at=2)
    final = workflow.run('requirement')
    assert not final.complete and final.error
    assert [t.status for t in final.tasks] == ['completed','failed','pending']
    assert len(coder.prompts)==2 and 'task1.py' in final.code_output
    assert final.original_requirement=='requirement' and final.technical_spec


@pytest.mark.parametrize('response',['{}','not JSON'])
def test_invalid_pm_does_not_call_coder(tmp_path,response):
    from tools.files import FileTools
    coder=FakeCoder(FileTools(tmp_path/'workspace'))
    workflow=ProjectWorkflow(ScriptedModel([response]),coder)
    final=workflow.run('requirement')
    assert final.error and not final.complete and not coder.prompts


def test_duplicate_task_ids_rejected():
    data=spec().model_dump()
    data['tasks'][1]['task_id']=data['tasks'][0]['task_id']
    with pytest.raises(ValidationError):TechnicalSpec.model_validate(data)


def test_state_rejects_more_than_eight_tasks():
    with pytest.raises(ValidationError):ProjectState(original_requirement='x',tasks=[task(i) for i in range(9)])


def test_coder_consumes_only_matching_ready_handoff(tmp_path):
    from agents.coder_agent import execute_project_task
    workflow,coder,_=make_workflow(tmp_path)
    state=ProjectState(original_requirement='x',technical_spec=spec(),tasks=spec().tasks,
                       handoff=Handoff.for_task(task(8)))
    state.tasks[0].status='running'
    with pytest.raises(ValueError):execute_project_task(state,coder,'s')
    assert not coder.prompts


def test_failed_acceptance_prevents_project_completion(tmp_path):
    workflow,_,_=make_workflow(tmp_path)
    workflow.verifier=lambda source:ExecutionResult(status='failed',stderr='wrong endpoint',exit_code=1)
    final=workflow.run('x')
    assert not final.complete and final.error=='API acceptance fixture failed'
    assert all(t.status=='completed' for t in final.tasks)


def test_pm_exception_redacts_provider_details():
    model=Mock()
    model.complete.side_effect=RuntimeError('secret-never-display')
    result=ProductManager(model)(ProjectState(original_requirement='x'))
    assert 'secret-never-display' not in json.dumps(result)


def test_published_api_requires_multiple_tasks():
    model = ScriptedModel([spec(1).model_dump()])
    state = ProjectState(original_requirement='Build /health and /echo')
    result = ProductManager(model)(state)
    assert result['error'] == 'PM planning failed: ValueError'
