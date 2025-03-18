import functools
import time
from typing import Callable, Dict

# Global registry to store all action data
action_registry = {}


def register_action(action_name: str):
    """
    Decorator to register agent actions with metadata.

    Args:
        action_name: The name of the action being performed (e.g., "query_rewrite")

    Returns:
        Decorated function that logs action metadata
    """

    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(self, query: str, *args, **kwargs):
            # Get start time
            start_time = time.time()

            # Extract the original function name and class name
            class_name = self.__class__.__name__
            function_name = func.__name__

            # Execute the function and capture the response
            response, usage_metadata = func(self, query, *args, **kwargs)

            # Calculate elapsed time
            elapsed_time = time.time() - start_time

            # Determine message and client type
            message = None
            if hasattr(self, "_message_format"):
                message = self._message_format().format(query=query)

            # Create action metadata
            action_data = {
                "timestamp": time.time(),
                "elapsed_time": elapsed_time,
                "action": action_name,
                "class": class_name,
                "function": function_name,
                "message": message,
                "response": response,
                "token_count": usage_metadata,
            }

            # Store in registry with query as key
            if query not in action_registry:
                action_registry[query] = []
            action_registry[query].append(action_data)

            # Print brief log (optional)
            print(f"[{action_name}] - Time: {elapsed_time:.2f}s")

            return response

        return wrapper

    return decorator


# Utility functions to work with the registry
def get_actions_for_query(query: str) -> list:
    """Get all actions performed for a specific query."""
    return action_registry.get(query, [])


def get_all_actions() -> Dict[str, list]:
    """Get all actions in the registry."""
    return action_registry


def clear_registry():
    """Clear the registry."""
    action_registry.clear()


def export_registry_to_json(filename: str):
    """Export the registry to a JSON file."""
    import json

    with open(filename, "w") as f:
        json.dump(action_registry, f, indent=2)
