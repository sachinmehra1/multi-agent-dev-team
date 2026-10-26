"""Local acceptance contract, independent from QA-generated tests."""
from bst import BinarySearchTree


def test_empty_and_missing():
    tree=BinarySearchTree()
    assert tree.inorder()==[]
    assert tree.search(0) is False
    assert tree.search(-10) is False


def test_insert_search_and_sorted_traversal():
    tree=BinarySearchTree()
    values=[5,3,7,1,4,6,9,0,-2]
    for value in values:tree.insert(value)
    assert tree.inorder()==sorted(values)
    assert all(tree.search(value) is True for value in values)
    assert tree.search(99) is False
    assert tree.inorder()==sorted(values)


def test_duplicates_are_ignored():
    tree=BinarySearchTree()
    for value in [2,2,2,0,0,-1,-1]:tree.insert(value)
    assert tree.inorder()==[-1,0,2]
    assert tree.search(2) is True


def test_ordered_insertions_and_independent_instances():
    tree,other=BinarySearchTree(),BinarySearchTree()
    for value in range(20):tree.insert(value)
    assert tree.inorder()==list(range(20))
    assert other.inorder()==[]
    assert other.search(4) is False
