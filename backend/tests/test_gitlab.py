"""GitLab 集成单元测试。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.integrations.gitlab import (
    _parse_repo,
    _validate_file_path,
    create_branch,
    create_file,
    create_merge_request,
    get_default_branch,
    get_project,
)


class TestParseRepo:
    def test_standard_url(self):
        assert _parse_repo("https://gitlab.com/mygroup/myproject") == "mygroup%2Fmyproject"

    def test_url_with_trailing_slash(self):
        assert _parse_repo("https://gitlab.com/mygroup/myproject/") == "mygroup%2Fmyproject"

    def test_url_with_dot_git(self):
        assert _parse_repo("https://gitlab.com/mygroup/myproject.git") == "mygroup%2Fmyproject"

    def test_url_with_subgroup(self):
        assert _parse_repo("https://gitlab.com/group/subgroup/project") == "group%2Fsubgroup%2Fproject"

    def test_path_only(self):
        assert _parse_repo("mygroup/myproject") == "mygroup%2Fmyproject"

    def test_path_only_with_subgroup(self):
        assert _parse_repo("group/sub/project") == "group%2Fsub%2Fproject"


class TestValidateFilePath:
    def test_valid_path(self):
        assert _validate_file_path("src/main.py") == "src/main.py"

    def test_reject_dot_dot(self):
        with pytest.raises(ValueError, match="不安全"):
            _validate_file_path("../etc/passwd")

    def test_reject_leading_slash(self):
        with pytest.raises(ValueError, match="不安全"):
            _validate_file_path("/etc/passwd")

    def test_reject_empty(self):
        with pytest.raises(ValueError, match="不安全"):
            _validate_file_path("")


class TestGitLabAPI:
    @patch("app.integrations.gitlab._get_client")
    @patch("app.integrations.gitlab._headers")
    async def test_get_project(self, mock_headers, mock_get_client):
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": 123, "default_branch": "main"}
        mock_resp.raise_for_status = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_get_client.return_value = mock_client
        mock_headers.return_value = {"Authorization": "Bearer test"}

        result = await get_project("https://gitlab.com/mygroup/myproject")
        assert result["id"] == 123
        mock_client.get.assert_called_once()

    @patch("app.integrations.gitlab._get_client")
    @patch("app.integrations.gitlab._headers")
    async def test_get_default_branch(self, mock_headers, mock_get_client):
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": 123, "default_branch": "develop"}
        mock_resp.raise_for_status = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_get_client.return_value = mock_client
        mock_headers.return_value = {"Authorization": "Bearer test"}

        result = await get_default_branch("https://gitlab.com/mygroup/myproject")
        assert result == "develop"

    @patch("app.integrations.gitlab._get_client")
    @patch("app.integrations.gitlab._headers")
    async def test_create_branch(self, mock_headers, mock_get_client):
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {"name": "feature/test"}
        mock_resp.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_get_client.return_value = mock_client
        mock_headers.return_value = {"Authorization": "Bearer test"}

        result = await create_branch("https://gitlab.com/mygroup/myproject", "feature/test", "main")
        assert result["name"] == "feature/test"
        mock_client.post.assert_called_once()

    @patch("app.integrations.gitlab._get_client")
    @patch("app.integrations.gitlab._headers")
    async def test_create_file_new(self, mock_headers, mock_get_client):
        mock_client = MagicMock()

        # get 返回 404（文件不存在）
        get_resp = MagicMock()
        get_resp.status_code = 404

        # post 创建成功
        post_resp = MagicMock()
        post_resp.status_code = 201
        post_resp.json.return_value = {"file_path": "src/new.py"}
        post_resp.raise_for_status = MagicMock()

        mock_client.get = AsyncMock(return_value=get_resp)
        mock_client.post = AsyncMock(return_value=post_resp)
        mock_get_client.return_value = mock_client
        mock_headers.return_value = {"Authorization": "Bearer test"}

        result = await create_file(
            "https://gitlab.com/mygroup/myproject",
            "main",
            "src/new.py",
            "print('hello')",
        )
        assert result["file_path"] == "src/new.py"
        mock_client.post.assert_called_once()

    @patch("app.integrations.gitlab._get_client")
    @patch("app.integrations.gitlab._headers")
    async def test_create_file_existing(self, mock_headers, mock_get_client):
        mock_client = MagicMock()

        # get 返回 200（文件存在）
        get_resp = MagicMock()
        get_resp.status_code = 200

        # put 更新成功
        put_resp = MagicMock()
        put_resp.status_code = 200
        put_resp.json.return_value = {"file_path": "src/existing.py"}
        put_resp.raise_for_status = MagicMock()

        mock_client.get = AsyncMock(return_value=get_resp)
        mock_client.put = AsyncMock(return_value=put_resp)
        mock_get_client.return_value = mock_client
        mock_headers.return_value = {"Authorization": "Bearer test"}

        result = await create_file(
            "https://gitlab.com/mygroup/myproject",
            "main",
            "src/existing.py",
            "print('updated')",
        )
        assert result["file_path"] == "src/existing.py"
        mock_client.put.assert_called_once()

    @patch("app.integrations.gitlab._get_client")
    @patch("app.integrations.gitlab._headers")
    async def test_create_merge_request(self, mock_headers, mock_get_client):
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {
            "iid": 1,
            "web_url": "https://gitlab.com/mygroup/myproject/-/merge_requests/1",
        }
        mock_resp.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_get_client.return_value = mock_client
        mock_headers.return_value = {"Authorization": "Bearer test"}

        result = await create_merge_request(
            "https://gitlab.com/mygroup/myproject",
            "feature/test",
            "main",
            "Test MR",
            "Description",
        )
        assert result["iid"] == 1
        assert "merge_requests" in result["web_url"]
        mock_client.post.assert_called_once()

    def test_create_file_rejects_unsafe_path(self):
        import asyncio
        with pytest.raises(ValueError, match="不安全"):
            asyncio.get_event_loop().run_until_complete(
                create_file("https://gitlab.com/group/proj", "main", "../hack", "bad")
            )
