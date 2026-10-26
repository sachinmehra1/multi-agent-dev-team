"""Trusted deterministic inputs for testing QA and feedback, not live-agent evidence."""
from orchestration.project_state import ProjectState, TechnicalSpec, CodingTask
from tests.conftest import ScriptedModel

CRITERIA = ['insert appends values', 'delete removes first match', 'search finds values', 'reverse changes order']
GOOD = '''class Node:
    def __init__(self, data):
        self.data, self.next = data, None

class LinkedList:
    def __init__(self):
        self.head = None

    def insert(self, value):
        node = Node(value)
        if self.head is None:
            self.head = node
            return
        current = self.head
        while current.next is not None:
            current = current.next
        current.next = node

    def delete(self, value):
        previous, current = None, self.head
        while current is not None:
            if current.data == value:
                if previous is None:
                    self.head = current.next
                else:
                    previous.next = current.next
                return True
            previous, current = current, current.next
        return False

    def search(self, value):
        current = self.head
        while current is not None:
            if current.data == value:
                return True
            current = current.next
        return False

    def reverse(self):
        previous, current = None, self.head
        while current is not None:
            following = current.next
            current.next = previous
            previous, current = current, following
        self.head = previous
'''
BAD_REVERSE = GOOD[:GOOD.index('    def reverse(self):')] + '    def reverse(self):\n        return None\n'
INITIAL = BAD_REVERSE.replace('    def search(self, value):\n', '    def search(self, value):\n        if not value:\n            return False\n')
TESTS = '''from linked_list import LinkedList

def values(linked):
    result = []
    node = linked.head
    while node is not None:
        assert len(result) < 20, 'cycle detected'
        result.append(node.data)
        node = node.next
    return result

def test_insert():
    linked = LinkedList()
    assert values(linked) == []
    for value in [0, 2, 2]: linked.insert(value)
    assert values(linked) == [0, 2, 2]

def test_delete():
    linked = LinkedList()
    assert linked.delete(8) is False
    for value in [1, 2, 2, 3]: linked.insert(value)
    assert linked.delete(1) is True
    assert linked.delete(2) is True
    assert values(linked) == [2, 3]
    assert linked.delete(3) is True
    assert linked.delete(2) is True
    assert linked.head is None
    assert linked.delete(2) is False

def test_search():
    linked = LinkedList()
    assert linked.search(0) is False
    linked.insert(0)
    assert linked.search(0) is True
    assert linked.search(99) is False

def test_reverse():
    linked = LinkedList()
    assert linked.reverse() is None
    assert values(linked) == []
    linked.insert(1)
    linked.reverse()
    assert values(linked) == [1]
    linked.insert(2)
    linked.insert(3)
    linked.reverse()
    assert values(linked) == [3, 2, 1]
    linked.reverse()
    assert values(linked) == [1, 2, 3]
'''
SUITE = {'code':TESTS, 'coverage':dict(zip(CRITERIA, [[n] for n in ['test_insert','test_delete','test_search','test_reverse']]))}
CRITIQUE = {'items':[{'location':'linked_list.py:LinkedList.search',
                      'concern':'Falsey values such as zero are incorrectly rejected.',
                      'proposed_revision':'Compare stored values for equality even when they are falsey.'}]}


class SeedProject:
    """Inject a declared faulty Coder output to exercise downstream control flow."""
    def run(self, requirement):
        task = CodingTask(task_id='linked-list', description='Implement linked list', acceptance_criteria=CRITERIA, priority=1)
        spec = TechnicalSpec(name='Linked list', description=requirement, acceptance_criteria=CRITERIA, tasks=[task])
        return ProjectState(original_requirement=requirement, technical_spec=spec,
                            tasks=[task.model_copy(update={'status':'completed'})],
                            code_output={'linked_list.py':INITIAL}, complete=True)


def revision_model(converge=True):
    outputs = [CRITIQUE, {'explanation':'Correct zero-value lookup before QA', 'files':{'linked_list.py':BAD_REVERSE}}]
    if converge:
        outputs.append({'explanation':'Implement pointer reversal in response to failing test_reverse',
                        'files':{'linked_list.py':GOOD}})
    else:
        # Real AST changes leave the reverse defect unresolved; bound must stop it.
        outputs.extend({'explanation':'Attempt an ineffective correction',
                        'files':{'linked_list.py':BAD_REVERSE + f'\nATTEMPT = {i}\n'}} for i in range(20))
    return ScriptedModel(outputs)
