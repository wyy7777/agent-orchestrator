import React, { useState } from "react";
import { Card, Form, Input, Button, Typography, message, Tabs, Space, Checkbox, Divider } from "antd";
import { UserOutlined, LockOutlined, MailOutlined, RocketOutlined, GithubOutlined } from "@ant-design/icons";
import { useRouter } from "next/router";

const { Title, Text, Paragraph } = Typography;

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export default function LoginPage() {
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState("login");
  const router = useRouter();

  const handleLogin = async (values: { username: string; password: string; remember_me?: boolean }) => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(values),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "登录失败");
      }
      const data = await res.json();
      localStorage.setItem("token", data.access_token);
      if (data.refresh_token) {
        localStorage.setItem("refresh_token", data.refresh_token);
      }
      message.success("登录成功");
      router.push("/");
    } catch (err) {
      message.error((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (values: { username: string; email: string; password: string }) => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(values),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "注册失败");
      }
      message.success("注册成功，请登录");
      setActiveTab("login");
    } catch (err) {
      message.error((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  // 跳过登录（单用户模式）
  const handleSkipLogin = async () => {
    setLoading(true);
    try {
      // 直接访问需要认证的接口，后端会自动创建默认用户
      const res = await fetch(`${API_BASE}/api/auth/me`);
      if (res.ok) {
        message.success("已进入本地模式");
        router.push("/");
      } else {
        throw new Error("初始化失败");
      }
    } catch (err) {
      message.error((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: "100vh",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)"
    }}>
      <Card style={{ width: 420, boxShadow: "0 8px 32px rgba(0,0,0,0.1)" }}>
        <div style={{ textAlign: "center", marginBottom: 24 }}>
          <Title level={2} style={{ margin: 0 }}>Agent Orchestrator</Title>
          <Text type="secondary">AI Agent 工作流编排平台</Text>
        </div>

        {/* 单用户模式入口 */}
        <Button
          type="primary"
          size="large"
          icon={<RocketOutlined />}
          block
          onClick={handleSkipLogin}
          loading={loading}
          style={{ marginBottom: 16, height: 48, fontSize: 16 }}
        >
          跳过登录，直接使用
        </Button>
        <Paragraph type="secondary" style={{ textAlign: "center", marginBottom: 16, fontSize: 12 }}>
          本地单用户模式，无需注册
        </Paragraph>

        <Divider plain>或</Divider>

        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          centered
          items={[
            {
              key: "login",
              label: "登录",
              children: (
                <Form onFinish={handleLogin} size="large">
                  <Form.Item name="username" rules={[{ required: true, message: "请输入用户名" }]}>
                    <Input prefix={<UserOutlined />} placeholder="用户名" />
                  </Form.Item>
                  <Form.Item name="password" rules={[{ required: true, message: "请输入密码" }]}>
                    <Input.Password prefix={<LockOutlined />} placeholder="密码" />
                  </Form.Item>
                  <Form.Item name="remember_me" valuePropName="checked">
                    <Checkbox>记住我</Checkbox>
                  </Form.Item>
                  <Form.Item>
                    <Button type="primary" htmlType="submit" loading={loading} block>
                      登录
                    </Button>
                  </Form.Item>
                </Form>
              )
            },
            {
              key: "register",
              label: "注册",
              children: (
                <Form onFinish={handleRegister} size="large">
                  <Form.Item name="username" rules={[{ required: true, message: "请输入用户名" }]}>
                    <Input prefix={<UserOutlined />} placeholder="用户名" />
                  </Form.Item>
                  <Form.Item name="email" rules={[{ required: true, type: "email", message: "请输入有效邮箱" }]}>
                    <Input prefix={<MailOutlined />} placeholder="邮箱" />
                  </Form.Item>
                  <Form.Item name="password" rules={[{ required: true, min: 8, message: "密码至少8位，包含大小写字母和数字" }]}>
                    <Input.Password prefix={<LockOutlined />} placeholder="密码" />
                  </Form.Item>
                  <Form.Item>
                    <Button type="primary" htmlType="submit" loading={loading} block>
                      注册
                    </Button>
                  </Form.Item>
                </Form>
              )
            }
          ]}
        />
      </Card>
    </div>
  );
}
