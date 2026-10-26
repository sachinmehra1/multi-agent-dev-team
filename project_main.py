"""Module 2 CLI; Module 1 main.py remains available unchanged."""
import argparse
import os
import re
from pathlib import Path
from dotenv import load_dotenv
from orchestration.llm import ChatModel
from orchestration.project_graph import build_project

GRADING_TASK = ('Build a REST API with two endpoints: GET /health (returns {status: ok}) '
                'and POST /echo (returns the JSON body it receives). Include basic input validation.')


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description='Module 2 PM + Coder')
    parser.add_argument('requirement', nargs='?', default=GRADING_TASK)
    parser.add_argument('--session', default='module2')
    parser.add_argument('--verify-api', action='store_true', help='Apply our documented local Flask request fixture')
    parser.add_argument('--output', type=Path, help='Save final typed state as JSON')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', args.session):
        parser.error('Invalid session name')
    model = ChatModel(os.getenv('LLM_MODEL','gpt-4o'), os.environ['LLM_API_KEY'],
                      os.getenv('LLM_BASE_URL','https://api.openai.com/v1'))
    workflow = build_project(model, Path('workspace')/args.session, '.chroma',
                             session_id=args.session, verify_api=args.verify_api)
    state = workflow.run(args.requirement)
    output = state.model_dump_json(indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output+'\n')
    print(output)
    return 0 if state.complete else 1


if __name__ == '__main__':
    raise SystemExit(main())
