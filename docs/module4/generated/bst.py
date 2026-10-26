class Node:
    def __init__(self, value):
        self.value = value
        self.left = None
        self.right = None

class BinarySearchTree:
    def __init__(self):
        self.root = None

    def insert(self, value):
        if value is None:
            return False  # Ignore None values
        if self.root is None:
            self.root = Node(value)
            return True  # Insertion successful
        else:
            return self._insert_recursive(self.root, value)

    def _insert_recursive(self, node, value):
        if value is None:
            return False  # Ignore None values
        if value < node.value:
            if node.left is None:
                node.left = Node(value)
                return True  # Insertion successful
            else:
                return self._insert_recursive(node.left, value)
        elif value > node.value:
            if node.right is None:
                node.right = Node(value)
                return True  # Insertion successful
            else:
                return self._insert_recursive(node.right, value)
        return False  # Duplicate value ignored

    def search(self, value):
        if value is None:
            return False  # Return False for None values
        return self._search_recursive(self.root, value)

    def _search_recursive(self, node, value):
        if node is None:
            return False
        if node.value == value:
            return True
        elif value < node.value:
            return self._search_recursive(node.left, value)
        else:
            return self._search_recursive(node.right, value)

    def inorder(self):
        if self.root is None:
            return []  # Early return for empty tree
        result = []
        self._inorder_recursive(self.root, result)
        return result

    def _inorder_recursive(self, node, result):
        if node:
            self._inorder_recursive(node.left, result)
            result.append(node.value)
            self._inorder_recursive(node.right, result)