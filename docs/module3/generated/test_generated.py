import pytest
from linked_list import LinkedList

# Helper function to convert linked list to Python list for easy comparison
def linked_list_to_list(linked_list):
    result = []
    current = linked_list.head
    while current:
        result.append(current.data)
        current = current.next
    return result

# Test insert functionality
def test_insert():
    ll = LinkedList()
    ll.insert(1)
    assert linked_list_to_list(ll) == [1]
    ll.insert(2)
    assert linked_list_to_list(ll) == [1, 2]
    ll.insert(3)
    assert linked_list_to_list(ll) == [1, 2, 3]

# Test delete functionality
def test_delete():
    ll = LinkedList()
    assert not ll.delete(1)  # Deleting from empty list
    ll.insert(1)
    ll.insert(2)
    ll.insert(3)
    assert ll.delete(2)  # Delete middle element
    assert linked_list_to_list(ll) == [1, 3]
    assert ll.delete(1)  # Delete head
    assert linked_list_to_list(ll) == [3]
    assert ll.delete(3)  # Delete last element
    assert linked_list_to_list(ll) == []
    assert not ll.delete(4)  # Delete non-existent element

# Test search functionality
def test_search():
    ll = LinkedList()
    assert not ll.search(1)  # Search in empty list
    ll.insert(1)
    ll.insert(2)
    ll.insert(3)
    assert ll.search(2)  # Search existing element
    assert not ll.search(4)  # Search non-existent element

# Test reverse functionality
def test_reverse():
    ll = LinkedList()
    ll.reverse()  # Reverse empty list
    assert linked_list_to_list(ll) == []
    ll.insert(1)
    ll.reverse()  # Reverse single element list
    assert linked_list_to_list(ll) == [1]
    ll.insert(2)
    ll.insert(3)
    ll.reverse()  # Reverse multiple elements
    assert linked_list_to_list(ll) == [3, 2, 1]

# Test handling of duplicates
def test_duplicates():
    ll = LinkedList()
    ll.insert(1)
    ll.insert(2)
    ll.insert(2)
    ll.insert(3)
    assert linked_list_to_list(ll) == [1, 2, 2, 3]
    assert ll.delete(2)  # Only first occurrence should be deleted
    assert linked_list_to_list(ll) == [1, 2, 3]
    assert ll.search(2)  # Second occurrence should still be found
    ll.reverse()
    assert linked_list_to_list(ll) == [3, 2, 1]
