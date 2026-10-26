import pytest
from bst import BinarySearchTree


def test_insert_adds_integer():
    bst = BinarySearchTree()
    assert bst.insert(10) is True
    assert bst.inorder() == [10]


def test_insert_ignores_duplicates():
    bst = BinarySearchTree()
    bst.insert(10)
    assert bst.insert(10) is False
    assert bst.inorder() == [10]


def test_insert_allows_negative_values():
    bst = BinarySearchTree()
    assert bst.insert(-5) is True
    assert bst.insert(-10) is True
    assert bst.inorder() == [-10, -5]


def test_insert_ignores_none():
    bst = BinarySearchTree()
    assert bst.insert(None) is False
    assert bst.inorder() == []


def test_search_returns_true_for_present_value():
    bst = BinarySearchTree()
    bst.insert(10)
    assert bst.search(10) is True


def test_search_returns_false_for_missing_value():
    bst = BinarySearchTree()
    bst.insert(10)
    assert bst.search(5) is False


def test_search_returns_false_for_none():
    bst = BinarySearchTree()
    assert bst.search(None) is False


def test_inorder_returns_empty_list_for_empty_tree():
    bst = BinarySearchTree()
    assert bst.inorder() == []


def test_inorder_returns_sorted_list():
    bst = BinarySearchTree()
    bst.insert(10)
    bst.insert(5)
    bst.insert(15)
    assert bst.inorder() == [5, 10, 15]


def test_inorder_with_negative_values():
    bst = BinarySearchTree()
    bst.insert(-5)
    bst.insert(-10)
    bst.insert(0)
    assert bst.inorder() == [-10, -5, 0]


def test_inorder_with_duplicates():
    bst = BinarySearchTree()
    bst.insert(10)
    bst.insert(5)
    bst.insert(10)  # Duplicate
    assert bst.inorder() == [5, 10]


def test_repeated_traversal():
    bst = BinarySearchTree()
    bst.insert(10)
    bst.insert(5)
    bst.insert(15)
    assert bst.inorder() == [5, 10, 15]
    assert bst.inorder() == [5, 10, 15]  # Repeated traversal
