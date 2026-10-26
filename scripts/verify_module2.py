"""Run the published task through the real PM/Coder workflow and save state evidence."""
import json
import os
import tempfile
import shutil
from pathlib import Path
from dotenv import load_dotenv
from orchestration.llm import ChatModel
from orchestration.project_graph import build_project
from project_main import GRADING_TASK


def main():
    load_dotenv()
    model = ChatModel(os.getenv('LLM_MODEL','gpt-4o'), os.environ['LLM_API_KEY'],
                      os.getenv('LLM_BASE_URL','https://api.openai.com/v1'))
    destination = Path('docs/module2')
    destination.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='module2-live-') as folder:
        root = Path(folder)
        workflow = build_project(model, root/'work', root/'chroma', verify_api=True,
                                 session_id='module2-evidence')
        snapshots = []
        for state in workflow.stream(GRADING_TASK):
            snapshots.append(state.model_dump())
            print(json.dumps({'tasks':[(t.task_id,t.status) for t in state.tasks],
                              'complete':state.complete,'error':state.error}),flush=True)
        # Preserve real failure evidence too; do not invent a passing run.
        (destination/'live-state-trace.json').write_text(json.dumps(snapshots,indent=2)+'\n')
        (destination/'live-final-state.json').write_text(state.model_dump_json(indent=2)+'\n')
        generated = destination/'generated'
        if generated.exists():
            shutil.rmtree(generated)
        generated.mkdir(exist_ok=True)
        for name, content in state.code_output.items():
            path = generated/name
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(content)
        assert state.complete, state.error
        assert len(state.tasks)>=2
        assert state.verification and state.verification.status=='passed'
        assert len(state.artifacts)==len(state.tasks)
        assert [h.task_id for h in state.handoff_history]==[t.task_id for t in state.tasks]
    print('PASS: PM specification, typed handoffs, ordered progress, generated API and local request fixture')


if __name__=='__main__':
    main()
