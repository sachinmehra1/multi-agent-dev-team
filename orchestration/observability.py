"""One OpenTelemetry root, Phoenix export, JSON logs and reconciled usage reports."""
import contextvars
import hashlib
import json
import logging
import os
import time
from contextlib import contextmanager
from dataclasses import replace
from functools import wraps
from pathlib import Path
from uuid import uuid4
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult
from opentelemetry.sdk.resources import Resource
from orchestration.recovery import CallPolicy, PromptCache, TransientToolError

ACTIVE = contextvars.ContextVar('run_runtime', default=None)
ROLE = contextvars.ContextVar('agent_role', default='pipeline')
STATS = contextvars.ContextVar('span_stats', default=None)


class RecordingExporter(SpanExporter):
    def __init__(self): self.spans = []
    def export(self, spans):
        for span in spans:
            self.spans.append({'name':span.name, 'trace_id':format(span.context.trace_id,'032x'),
                'span_id':format(span.context.span_id,'016x'),
                'parent_id':format(span.parent.span_id,'016x') if span.parent else None,
                'attributes':dict(span.attributes), 'status':span.status.status_code.name})
        return SpanExportResult.SUCCESS
    def shutdown(self): pass


class Runtime:
    def __init__(self, output='docs', *, endpoint=None, cache_ttl=300, retries=3,
                 base_delay=.25, cooldown=30, rates=None, models=None,
                 clock=time.monotonic, sleep=time.sleep, jitter=None):
        self.output, self.run_id = Path(output), uuid4().hex
        self.clock, self.started = clock, clock()
        self.logs, self.calls, self.policies = [], [], {}
        self.settings = dict(retries=retries, base_delay=base_delay,cooldown=cooldown,clock=clock,sleep=sleep)
        if jitter is not None: self.settings['jitter'] = jitter
        self.cache = PromptCache(cache_ttl,clock)
        self.rates = rates or {'pm':(2.5,10.0),'coder':(.15,.60),'qa':(.15,.60)}
        self.models = models or {'pm':'gpt-4o','coder':'gpt-4o-mini','qa':'gpt-4o-mini'}
        self.exporter = RecordingExporter()
        self.provider = TracerProvider(resource=Resource.create({'service.name':'saras-team','openinference.project.name':'module4'}))
        self.provider.add_span_processor(SimpleSpanProcessor(self.exporter))
        if endpoint:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            self.provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter(endpoint=endpoint, timeout=5)))
        self.tracer = self.provider.get_tracer('saras.module4')
        self.trace_id = None

    def event(self, name, level='INFO', **fields):
        record = {'event':name,'level':level,'run_id':self.run_id,'trace_id':self.trace_id,
                  'agent_name':ROLE.get(),**fields}
        self.logs.append(record)
        logging.getLogger('pipeline').log(getattr(logging,level),json.dumps(record))

    def policy(self, key):
        if key not in self.policies:
            self.policies[key] = CallPolicy(**self.settings,
                event=lambda name,**fields:self.event(name,call_boundary=key,**fields))
        return self.policies[key]

    @contextmanager
    def run(self):
        token = ACTIVE.set(self)
        try:
            with self.tracer.start_as_current_span('pipeline',record_exception=False,set_status_on_exception=False) as span:
                self.trace_id = format(span.get_span_context().trace_id,'032x')
                span.set_attribute('agent_name','pipeline')
                span.set_attribute('openinference.span.kind','CHAIN')
                span.set_attribute('run_id',self.run_id)
                self.event('pipeline_started')
                try: yield self
                finally:
                    span.set_attribute('duration_ms',(self.clock()-self.started)*1000)
                    span.set_attribute('token_count',sum(c['prompt_tokens']+c['completion_tokens'] for c in self.calls))
                    span.set_attribute('tool_calls',sum(r['event']=='tool_call' for r in self.logs))
                    self.event('pipeline_finished')
        finally:
            self.provider.force_flush()
            self.write_reports()
            self.provider.shutdown()
            ACTIVE.reset(token)

    @contextmanager
    def agent(self, role, name):
        role_token = ROLE.set(role)
        stats = {'token_count':0,'tool_calls':0}
        stats_token = STATS.set(stats)
        started = self.clock()
        try:
            with self.tracer.start_as_current_span(name,record_exception=False,set_status_on_exception=False) as span:
                span.set_attribute('openinference.span.kind','AGENT')
                span.set_attribute('agent_name',role)
                self.event('agent_started',invocation=name)
                try: yield
                finally:
                    for key,value in stats.items(): span.set_attribute(key,value)
                    span.set_attribute('duration_ms',(self.clock()-started)*1000)
                    self.event('agent_finished',invocation=name,**stats,duration_ms=(self.clock()-started)*1000)
        finally:
            STATS.reset(stats_token)
            ROLE.reset(role_token)

    def tool(self, name, operation):
        stats = STATS.get()
        if stats is not None: stats['tool_calls'] += 1
        self.event('tool_call',tool=name)
        with self.tracer.start_as_current_span('tool.'+name,record_exception=False,set_status_on_exception=False) as span:
            span.set_attribute('openinference.span.kind','TOOL')
            span.set_attribute('agent_name',ROLE.get())
            span.set_attribute('tool_calls',1)
            span.set_attribute('token_count',0)
            start = self.clock()
            def invoke():
                result = operation()
                if getattr(result,'status',None) == 'unavailable':
                    raise TransientToolError('Execution service unavailable')
                return result
            try: return self.policy('tool.'+name).call(invoke)
            finally: span.set_attribute('duration_ms',(self.clock()-start)*1000)

    def llm(self, client, messages, operation):
        role = ROLE.get()
        if role not in self.rates: raise ValueError('LLM call outside an agent invocation')
        key = hashlib.sha256(json.dumps([role,client.model,client.base_url,messages],sort_keys=True).encode()).hexdigest()
        cached = self.cache.get(key)
        if cached is not None:
            reply = replace(cached,total_tokens=0,prompt_tokens=0,completion_tokens=0)
            self.record_usage(role,client.model,reply,'cache_hit')
            self.event('cache_hit',model=client.model)
            return reply
        self.event('cache_miss',model=client.model)
        def invoke():
            with self.tracer.start_as_current_span('llm.'+client.model,record_exception=False,set_status_on_exception=False) as span:
                span.set_attribute('openinference.span.kind','LLM')
                span.set_attribute('agent_name',role)
                span.set_attribute('llm.model_name',client.model)
                start = self.clock()
                try:
                    reply = operation()
                    self.record_usage(role,client.model,reply,'provider_call')
                    span.set_attribute('token_count',reply.prompt_tokens+reply.completion_tokens)
                    span.set_attribute('llm.token_count.prompt',reply.prompt_tokens)
                    span.set_attribute('llm.token_count.completion',reply.completion_tokens)
                    return reply
                except Exception as exc:
                    self.calls.append({'agent_name':role,'model':client.model,'status':'error',
                        'prompt_tokens':0,'completion_tokens':0,'estimated_usd':0.0,'usage_known':False,
                        'error_type':type(exc).__name__})
                    self.event('llm_usage',**self.calls[-1])
                    raise
                finally:
                    span.set_attribute('tool_calls',0)
                    span.set_attribute('duration_ms',(self.clock()-start)*1000)
        reply = self.policy('llm.'+client.base_url+'.'+client.model).call(invoke)
        # Cache only syntactically valid JSON; consumer schemas still gate every action.
        try:
            json.loads(reply.content)
            self.cache.put(key,reply)
        except (ValueError,TypeError): pass
        return reply

    def record_usage(self, role, model, reply, status):
        input_rate,output_rate = self.rates[role]
        cost = (reply.prompt_tokens*input_rate+reply.completion_tokens*output_rate)/1_000_000
        entry = {'agent_name':role,'model':model,'status':status,'prompt_tokens':reply.prompt_tokens,
                 'completion_tokens':reply.completion_tokens,'estimated_usd':cost,'usage_known':reply.usage_known}
        self.calls.append(entry)
        if STATS.get() is not None: STATS.get()['token_count'] += reply.prompt_tokens+reply.completion_tokens
        self.event('llm_usage',**entry)

    def write_reports(self):
        agents = {role:{'prompt_tokens':0,'completion_tokens':0,'estimated_usd':0.0,'calls':0,'cache_hits':0} for role in self.rates}
        for call in self.calls:
            row = agents[call['agent_name']]
            for key in ('prompt_tokens','completion_tokens','estimated_usd'): row[key] += call[key]
            row['calls'] += 1
            row['cache_hits'] += call['status'] == 'cache_hit'
        report = {'run_id':self.run_id,'trace_id':self.trace_id,'models':self.models,
                  'rates_usd_per_million_tokens':{r:{'prompt':v[0],'completion':v[1]} for r,v in self.rates.items()},
                  'per_agent':agents,'total_estimated_usd':sum(a['estimated_usd'] for a in agents.values()),
                  'unknown_usage_calls':sum(not c['usage_known'] for c in self.calls),'calls':self.calls}
        for folder,content in [('cost_reports',report),('traces',{'run_id':self.run_id,'spans':self.exporter.spans})]:
            path=self.output/folder;path.mkdir(parents=True,exist_ok=True)
            (path/(self.run_id+'.json')).write_text(json.dumps(content,indent=2)+'\n')
        path=self.output/'run_logs';path.mkdir(parents=True,exist_ok=True)
        (path/(self.run_id+'.jsonl')).write_text(''.join(json.dumps(r)+'\n' for r in self.logs))


def agent_span(role):
    def decorate(function):
        @wraps(function)
        def wrapped(*args,**kwargs):
            runtime = ACTIVE.get()
            if runtime is None: return function(*args,**kwargs)
            with runtime.agent(role,role+'.'+function.__qualname__): return function(*args,**kwargs)
        return wrapped
    return decorate


def tool_call(name):
    def decorate(function):
        @wraps(function)
        def wrapped(*args,**kwargs):
            runtime=ACTIVE.get()
            if runtime is None:return function(*args,**kwargs)
            return runtime.tool(name,lambda:function(*args,**kwargs))
        return wrapped
    return decorate
