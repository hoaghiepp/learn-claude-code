import json
from typing import List, Dict, Any


def get_active_users(file_path: str) -> List[Dict[str, Any]]:
    """Read a JSON file and return a list of active users.

    Args:
        file_path: Path to the JSON file containing user data.

    Returns:
        A list of user dictionaries where the 'active' field is True.

    Raises:
        FileNotFoundError: If the specified file does not exist.
        json.JSONDecodeError: If the file contains invalid JSON.
    """
    with open(file_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    users = data if isinstance(data, list) else data.get("users", [])

    active_users = [user for user in users if user.get("active") is True]

    return active_users


if __name__ == "__main__":
    # Example usage
    active_users = get_active_users("users.json")
    print(f"Found {len(active_users)} active user(s):")
    for user in active_users:
        print(f"  - {user.get('name', 'Unknown')} ({user.get('email', 'No email')})")