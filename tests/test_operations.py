import json
from types import SimpleNamespace
import pytest
from pydantic import ValidationError
from orchestration.recovery import CallPolicy, CircuitBreaker, CircuitOpen
from orchestration.observability import Runtime, agent_span, tool_call
from orchestration.llm import ModelReply
from production_main import RunInput, configured_runtime


class Clock:
    value=0.0
    def __call__(self):return self.value
    def advance(self,seconds):self.value+=seconds


def test_transient_retry_is_per_call_with_exponential_jitter():
    events,delays=[],[]
    policy=CallPolicy(base_delay=.25,sleep=delays.append,jitter=lambda low,high:high/2,
                      event=lambda name,**fields:events.append({'event':name,**fields}))
    attempts=[]
    def operation():
        attempts.append(1)
        if len(attempts)<3:raise ConnectionError('temporary')
        return 'ok'
    assert policy.call(operation)=='ok'
    assert len(attempts)==3 and delays==[.375,.625]
    assert [e['retry_number'] for e in events if e['event']=='call_attempt']==[0,1,2]
    assert policy.breaker.state=='closed' and policy.breaker.failures==0


def test_persistent_failure_opens_breaker_without_extra_calls():
    attempts=[]
    policy=CallPolicy(sleep=lambda delay:None)
    def operation():attempts.append(1);raise ConnectionError('down')
    with pytest.raises(ConnectionError):policy.call(operation)
    assert len(attempts)==3 and policy.breaker.state=='open'
    with pytest.raises(CircuitOpen):policy.call(operation)
    assert len(attempts)==3


def test_cooldown_failed_probe_reopens_successful_probe_closes():
    clock=Clock();events=[]
    breaker=CircuitBreaker(10,clock,lambda name,**fields:events.append(fields))
    for _ in range(3):breaker.before();breaker.failure()
    with pytest.raises(CircuitOpen):breaker.before()
    clock.advance(10);breaker.before();assert breaker.state=='half_open'
    breaker.failure();assert breaker.state=='open'
    clock.advance(10);breaker.before();breaker.success()
    assert breaker.state=='closed' and breaker.failures==0
    assert [e['state'] for e in events]==['open','half_open','open','half_open','closed']
    assert all(e['level']=='WARNING' for e in events)


@pytest.mark.parametrize('retries',[-1,4,8])
def test_retry_count_cannot_exceed_three(retries):
    with pytest.raises(ValueError):CallPolicy(retries=retries)


def test_validation_errors_not_retried():
    calls=[];policy=CallPolicy(sleep=lambda _:None)
    def invalid():calls.append(1);raise ValueError('invalid input')
    with pytest.raises(ValueError):policy.call(invalid)
    assert len(calls)==1 and policy.breaker.failures==0


def test_cache_hit_expiry_and_exact_cost_reconciliation(tmp_path):
    clock=Clock();provider_calls=[]
    runtime=Runtime(tmp_path,cache_ttl=5,clock=clock)
    client=SimpleNamespace(model='gpt-4o',base_url='https://example.invalid/v1')
    def provider():provider_calls.append(1);return ModelReply('{}',150,100,50,True)
    with runtime.run():
        with runtime.agent('pm','pm.probe'):
            first=runtime.llm(client,[{'role':'user','content':'task'}],provider)
            second=runtime.llm(client,[{'role':'user','content':'task'}],provider)
            clock.advance(5)
            third=runtime.llm(client,[{'role':'user','content':'task'}],provider)
    assert len(provider_calls)==2 and first.total_tokens==third.total_tokens==150
    assert second.total_tokens==0
    report=json.loads((tmp_path/'cost_reports'/f'{runtime.run_id}.json').read_text())
    assert report['per_agent']['pm']['prompt_tokens']==200
    assert report['per_agent']['pm']['completion_tokens']==100
    assert report['per_agent']['pm']['cache_hits']==1
    assert report['total_estimated_usd']==pytest.approx(.0015)
    assert report['total_estimated_usd']==sum(c['estimated_usd'] for c in report['calls'])
    assert set(report['per_agent'])=={'pm','coder','qa'}


def test_single_trace_all_agents_and_metadata(tmp_path):
    runtime=Runtime(tmp_path)
    @tool_call('probe')
    def tool():return 'ok'
    @agent_span('pm')
    def pm():return tool()
    @agent_span('coder')
    def coder():return tool()
    @agent_span('qa')
    def qa():return tool()
    with runtime.run():pm();coder();qa()
    spans=runtime.exporter.spans
    roots=[s for s in spans if s['parent_id'] is None]
    assert len(roots)==1 and roots[0]['name']=='pipeline'
    assert len({s['trace_id'] for s in spans})==1
    agents=[s for s in spans if s['attributes'].get('openinference.span.kind')=='AGENT']
    assert {s['attributes']['agent_name'] for s in agents}=={'pm','coder','qa'}
    for span in agents:
        assert span['parent_id']==roots[0]['span_id']
        assert {'agent_name','token_count','tool_calls','duration_ms'}<=span['attributes'].keys()
        assert span['attributes']['tool_calls']==1


def test_tool_retry_and_structured_error_leave_cost_report(tmp_path):
    runtime=Runtime(tmp_path,sleep=lambda _:None)
    calls=[]
    @tool_call('broken')
    def tool():calls.append(1);raise OSError('secret-should-not-appear')
    with runtime.run():
        with runtime.agent('coder','coder.probe'):
            with pytest.raises(OSError):tool()
            with pytest.raises(CircuitOpen):tool()
    assert len(calls)==3
    assert (tmp_path/'cost_reports'/f'{runtime.run_id}.json').exists()
    assert 'secret-should-not-appear' not in json.dumps(runtime.logs)
    assert any(r['event']=='circuit_transition' and r['level']=='WARNING' for r in runtime.logs)


def test_role_models_have_required_defaults(tmp_path,monkeypatch):
    for name in ['PM_MODEL','CODER_MODEL','QA_MODEL','PHOENIX_TRACES_ENDPOINT']:monkeypatch.delenv(name,raising=False)
    runtime=configured_runtime(tmp_path)
    assert runtime.models=={'pm':'gpt-4o','coder':'gpt-4o-mini','qa':'gpt-4o-mini'}
    runtime.provider.shutdown()


@pytest.mark.parametrize('payload',[{'requirement':''},{'requirement':'x','session_id':'../secret'},
                                    {'requirement':'x','extra':'ignored?'},{'requirement':12}])
def test_external_input_validation(payload):
    with pytest.raises(ValidationError):RunInput.model_validate(payload)


def test_chat_model_boundary_retries_and_records_every_attempt(tmp_path,monkeypatch):
    from orchestration.llm import ChatModel
    client=ChatModel('gpt-4o-mini','not-a-real-key','https://example.invalid')
    attempts=[]
    def provider(messages):
        attempts.append(1)
        if len(attempts)<3:raise ConnectionError('temporary')
        return ModelReply('{}',15,10,5,True)
    monkeypatch.setattr(client,'_complete_once',provider)
    runtime=Runtime(tmp_path,sleep=lambda _:None)
    with runtime.run():
        with runtime.agent('coder','coder.probe'):
            assert client.complete([]).content=='{}'
    assert len(attempts)==3
    assert [c['status'] for c in runtime.calls]==['error','error','provider_call']
    assert runtime.calls[-1]['prompt_tokens']==10 and runtime.calls[-1]['completion_tokens']==5


def test_open_circuit_serves_only_unexpired_cached_result(tmp_path):
    clock=Clock();runtime=Runtime(tmp_path,cache_ttl=5,clock=clock)
    client=SimpleNamespace(model='gpt-4o',base_url='https://example.invalid')
    calls=[]
    def provider():calls.append(1);return ModelReply('{}',3,2,1,True)
    with runtime.run():
        with runtime.agent('pm','pm.probe'):
            runtime.llm(client,[],provider)
            breaker=runtime.policy('llm.'+client.base_url+'.'+client.model).breaker
            for _ in range(3):breaker.failure()
            assert runtime.llm(client,[],provider).content=='{}'
            clock.advance(5)
            with pytest.raises(CircuitOpen):runtime.llm(client,[],provider)
    assert len(calls)==1
