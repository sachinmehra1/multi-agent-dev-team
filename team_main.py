"""Module 3 CLI: PM → Coder → reflection → QA ↔ Coder."""
import argparse
import os
import re
from pathlib import Path
from dotenv import load_dotenv
from orchestration.llm import ChatModel
from orchestration.team_graph import build_team

GRADING_TASK = ('Implement a Python module that contains a linked list class with insert, delete, '
                'search, and reverse methods. All methods must be covered by tests.')
# Public method semantics are not specified by the course; keep our local contract explicit.
LOCAL_CONTRACT = ('Use linked_list.py with LinkedList() and head nodes exposing data and next. '
                  'insert(value) appends; delete(value) removes the first matching item and returns a bool; '
                  'search(value) returns a bool; reverse() reverses in place and returns None. '
                  'Support empty lists, singletons, duplicates and missing values. '
                  'Use runnable assertion scripts for the initial Coder checks; QA will generate pytest tests separately.')


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description='Three-agent team with A2A QA')
    parser.add_argument('requirement', nargs='?', default=GRADING_TASK+'\nLocal interface contract: '+LOCAL_CONTRACT)
    parser.add_argument('--session', default='module3')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', args.session):
        parser.error('Invalid session name')
    model = ChatModel(os.getenv('LLM_MODEL','gpt-4o'), os.environ['LLM_API_KEY'],
                      os.getenv('LLM_BASE_URL','https://api.openai.com/v1'))
    team = build_team(model, Path('workspace')/args.session, '.chroma', session_id=args.session)
    state = team.run(args.requirement)
    output = state.model_dump_json(indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output+'\n')
    print(output)
    return 0 if state.final_report.approved else 1


if __name__ == '__main__':
    raise SystemExit(main())
