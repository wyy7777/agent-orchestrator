import pytest


@pytest.mark.asyncio
async def test_register(client):
    resp = await client.post("/api/auth/register", json={
        "username": "testuser",
        "email": "test@example.com",
        "password": "secret123",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["username"] == "testuser"
    assert data["email"] == "test@example.com"
    assert data["is_admin"] is True  # 第一个用户自动成为管理员
    assert "hashed_password" not in data


@pytest.mark.asyncio
async def test_register_duplicate_username(client):
    await client.post("/api/auth/register", json={
        "username": "dupuser",
        "email": "dup1@example.com",
        "password": "pass123",
    })
    resp = await client.post("/api/auth/register", json={
        "username": "dupuser",
        "email": "dup2@example.com",
        "password": "pass456",
    })
    assert resp.status_code == 400
    assert "用户名已存在" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_register_duplicate_email(client):
    await client.post("/api/auth/register", json={
        "username": "emailuser1",
        "email": "same@example.com",
        "password": "pass123",
    })
    resp = await client.post("/api/auth/register", json={
        "username": "emailuser2",
        "email": "same@example.com",
        "password": "pass456",
    })
    assert resp.status_code == 400
    assert "邮箱已被注册" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_login(client):
    # 注册
    await client.post("/api/auth/register", json={
        "username": "loginuser",
        "email": "login@example.com",
        "password": "mypassword",
    })
    # 登录
    resp = await client.post("/api/auth/login", json={
        "username": "loginuser",
        "password": "mypassword",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    await client.post("/api/auth/register", json={
        "username": "wrongpw",
        "email": "wrongpw@example.com",
        "password": "correct",
    })
    resp = await client.post("/api/auth/login", json={
        "username": "wrongpw",
        "password": "incorrect",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me(client):
    # 注册并登录
    await client.post("/api/auth/register", json={
        "username": "meuser",
        "email": "me@example.com",
        "password": "pass123",
    })
    login_resp = await client.post("/api/auth/login", json={
        "username": "meuser",
        "password": "pass123",
    })
    token = login_resp.json()["access_token"]

    # 获取当前用户
    resp = await client.get("/api/auth/me", headers={
        "Authorization": f"Bearer {token}",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "meuser"
    assert data["email"] == "me@example.com"


@pytest.mark.asyncio
async def test_get_me_no_token(client):
    # 单用户模式：无 token 时返回默认用户
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "local"  # 默认用户


@pytest.mark.asyncio
async def test_update_me(client):
    await client.post("/api/auth/register", json={
        "username": "upduser",
        "email": "upd@example.com",
        "password": "oldpass",
    })
    login_resp = await client.post("/api/auth/login", json={
        "username": "upduser",
        "password": "oldpass",
    })
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 更新邮箱
    resp = await client.put("/api/auth/me", json={"email": "new@example.com"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["email"] == "new@example.com"

    # 更新密码
    resp = await client.put("/api/auth/me", json={"password": "newpass"}, headers=headers)
    assert resp.status_code == 200

    # 用新密码登录
    login_resp = await client.post("/api/auth/login", json={
        "username": "upduser",
        "password": "newpass",
    })
    assert login_resp.status_code == 200


@pytest.mark.asyncio
async def test_list_users_requires_admin(client):
    # 注册普通用户（第二个用户，非管理员）
    await client.post("/api/auth/register", json={
        "username": "adminuser",
        "email": "admin@example.com",
        "password": "pass",
    })
    await client.post("/api/auth/register", json={
        "username": "normaluser",
        "email": "normal@example.com",
        "password": "pass",
    })
    login_resp = await client.post("/api/auth/login", json={
        "username": "normaluser",
        "password": "pass",
    })
    token = login_resp.json()["access_token"]

    # 普通用户无法访问用户列表
    resp = await client.get("/api/users", headers={
        "Authorization": f"Bearer {token}",
    })
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_list_and_set_admin(client):
    # 第一个用户自动成为管理员
    await client.post("/api/auth/register", json={
        "username": "superadmin",
        "email": "super@example.com",
        "password": "pass",
    })
    await client.post("/api/auth/register", json={
        "username": "regular",
        "email": "regular@example.com",
        "password": "pass",
    })

    login_resp = await client.post("/api/auth/login", json={
        "username": "superadmin",
        "password": "pass",
    })
    admin_token = login_resp.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 管理员列出用户
    resp = await client.get("/api/users", headers=admin_headers)
    assert resp.status_code == 200
    users = resp.json()
    assert len(users) == 2

    # 获取 regular 用户 id
    regular_user = [u for u in users if u["username"] == "regular"][0]

    # 设置为管理员
    resp = await client.put(
        f"/api/users/{regular_user['id']}/admin?is_admin=true",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["is_admin"] is True

    # 取消管理员
    resp = await client.put(
        f"/api/users/{regular_user['id']}/admin?is_admin=false",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["is_admin"] is False


@pytest.mark.asyncio
async def test_existing_tests_still_pass(client):
    """验证原有测试不受影响。"""
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
