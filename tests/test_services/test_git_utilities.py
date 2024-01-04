"""Unit tests for git utility methods."""

from readmeai.services.git_utilities import get_remote_file_url


def test_get_remote_file_url():
    """Test method for getting the remote file URL."""
    file_path = "readmeai/main.py"
    full_name = "eli64s/readme-ai"
    repo_url = "https://github.com/eli64s/readme-ai"
    file_url = get_remote_file_url(file_path, full_name, repo_url)
    expected_url = (
        "https://github.com/eli64s/readme-ai/blob/main/readmeai/main.py"
    )
    assert file_url == expected_url
