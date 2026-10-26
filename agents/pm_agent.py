"""PM plans once, validates its specification and consolidates without dropping work."""
import json
import math
from orchestration.project_state import CodingTask, TechnicalSpec, Handoff, Progress


def consolidate_tasks(tasks, limit=8):
    """Merge adjacent groups, preserving every source description and criterion."""
    if limit < 1:
        raise ValueError('limit must be positive')
    if len(tasks) <= limit:
        return [task.model_copy(update={'source_task_ids':[task.task_id]}) for task in tasks]
    size = math.ceil(len(tasks) / limit)
    groups = [tasks[i:i + size] for i in range(0, len(tasks), size)]
    return [CodingTask(
        task_id=f'group-{i+1}',
        description='\n'.join(f'[{t.task_id}] {t.description}' for t in group),
        acceptance_criteria=[f'[{t.task_id}] {criterion}' for t in group for criterion in t.acceptance_criteria],
        priority=min(t.priority for t in group),
        source_task_ids=[t.task_id for t in group],
    ) for i,group in enumerate(groups)]


class ProductManager:
    def __init__(self, model):
        self.model = model

    def __call__(self, state):
        prompt = (
            'You are the Product Manager. Convert the original requirement into a technical '
            'specification with name, description, acceptance_criteria and ordered tasks. '
            'Preserve every requested behavior. Each task has task_id, description, '
            'acceptance_criteria and priority (1 highest, 5 lowest); status is pending. '
            'Plan 2-4 discrete tasks for the REST API: implement health first, then echo '
            'and input validation, then tests only if necessary. Tasks execute in list order. '
            'Use Flask in app.py with a module-level app object for an API requirement. '
            'Each coding task must leave executable code with runnable assertions. '
            'For POST /echo accept JSON objects (including empty objects), return them unchanged; '
            'reject malformed JSON and non-object JSON with 400 and wrong content type with 415. '
            'These API conventions only apply to API requirements. Do not add unrelated features. '
            'Never execute code or request credentials. Return only JSON matching this schema:\n'
            + json.dumps(TechnicalSpec.model_json_schema())
        )
        try:
            reply = self.model.complete([{'role':'system','content':prompt},
                                         {'role':'user','content':state.original_requirement}])
            spec = TechnicalSpec.model_validate_json(reply.content)
            if all(endpoint in state.original_requirement for endpoint in ('/health','/echo')) and len(spec.tasks) < 2:
                raise ValueError('The published API task requires at least two discrete tasks')
            original = [t.model_copy(deep=True) for t in spec.tasks]
            tasks = consolidate_tasks(original)
            spec = spec.model_copy(update={'tasks':tasks})
            handoff = Handoff.for_task(tasks[0])
            return {'technical_spec':spec, 'original_tasks':original, 'tasks':tasks,
                    'handoff':handoff, 'handoff_history':[handoff],
                    'progress':[Progress(task_id=tasks[0].task_id, status='ready', message='PM specification validated; task ready')]}
        except Exception as exc:
            return {'error':'PM planning failed: '+type(exc).__name__}
