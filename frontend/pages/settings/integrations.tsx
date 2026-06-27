import React, { useEffect, useState } from "react";
import {
  Typography,
  Card,
  Form,
  Input,
  Button,
  Space,
  message,
  Spin,
  Tag,
  Divider,
  Alert,
  Descriptions,
  Collapse,
} from "antd";
import {
  GlobalOutlined,
  LinkOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  SendOutlined,
  ApiOutlined,
} from "@ant-design/icons";

const { Title, Text } = Typography;

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

interface IntegrationStatus {
  jira: { configured: boolean };
  linear: { configured: boolean };
  confluence: { configured: boolean };
  github: { configured: boolean };
  gitlab: { configured: boolean };
}

async function fetchIntegrationStatus(): Promise<IntegrationStatus> {
  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${API_BASE}/api/integrations/status`, { headers });
  if (!res.ok) throw new Error("获取集成状态失败");
  return res.json();
}

async function testJiraSync(config: { base_url: string; api_token: string; project_key: string }) {
  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${API_BASE}/api/integrations/jira/sync`, {
    method: "POST",
    headers,
    body: JSON.stringify({ provider: "jira", ...config }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Jira 连接测试失败");
  }
  return res.json();
}

async function testLinearSync(config: { base_url: string; api_token: string }) {
  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${API_BASE}/api/integrations/linear/sync`, {
    method: "POST",
    headers,
    body: JSON.stringify({ provider: "linear", ...config }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Linear 连接测试失败");
  }
  return res.json();
}

const StatusIcon = ({ configured }: { configured: boolean }) =>
  configured ? (
    <Tag icon={<CheckCircleOutlined />} color="success">已配置</Tag>
  ) : (
    <Tag icon={<CloseCircleOutlined />} color="default">未配置</Tag>
  );

export default function IntegrationsPage() {
  const [status, setStatus] = useState<IntegrationStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [testingJira, setTestingJira] = useState(false);
  const [testingLinear, setTestingLinear] = useState(false);
  const [jiraForm] = Form.useForm();
  const [linearForm] = Form.useForm();

  useEffect(() => {
    (async () => {
      try {
        const s = await fetchIntegrationStatus();
        setStatus(s);
      } catch {
        message.error("加载集成状态失败");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const handleTestJira = async (values: { base_url: string; api_token: string; project_key: string }) => {
    setTestingJira(true);
    try {
      const result = await testJiraSync(values);
      message.success(`Jira 连接成功！同步了 ${result.synced} 个 Issue`);
    } catch (err) {
      message.error((err as Error).message);
    } finally {
      setTestingJira(false);
    }
  };

  const handleTestLinear = async (values: { base_url: string; api_token: string }) => {
    setTestingLinear(true);
    try {
      const result = await testLinearSync(values);
      message.success(`Linear 连接成功！同步了 ${result.synced} 个 Issue`);
    } catch (err) {
      message.error((err as Error).message);
    } finally {
      setTestingLinear(false);
    }
  };

  if (loading) {
    return <div style={{ textAlign: "center", padding: 80 }}><Spin size="large" /></div>;
  }

  return (
    <div>
      <Title level={3}>
        <GlobalOutlined style={{ marginRight: 8 }} />
        集成设置
      </Title>

      {/* 集成状态概览 */}
      <Card title="集成状态" style={{ marginBottom: 24 }}>
        <Descriptions column={{ xs: 1, sm: 2, md: 3 }}>
          <Descriptions.Item label="GitHub">
            <StatusIcon configured={status?.github?.configured || false} />
          </Descriptions.Item>
          <Descriptions.Item label="GitLab">
            <StatusIcon configured={status?.gitlab?.configured || false} />
          </Descriptions.Item>
          <Descriptions.Item label="Jira">
            <StatusIcon configured={status?.jira?.configured || false} />
          </Descriptions.Item>
          <Descriptions.Item label="Linear">
            <StatusIcon configured={status?.linear?.configured || false} />
          </Descriptions.Item>
          <Descriptions.Item label="Confluence">
            <StatusIcon configured={status?.confluence?.configured || false} />
          </Descriptions.Item>
        </Descriptions>
        <Alert
          type="info"
          message="集成配置通过环境变量或 .env 文件设置。以下表单用于测试连接。"
          style={{ marginTop: 16 }}
          showIcon
        />
      </Card>

      {/* Jira 配置 */}
      <Card
        title={
          <Space>
            <LinkOutlined />
            Jira 集成
          </Space>
        }
        style={{ marginBottom: 24 }}
      >
        <Text type="secondary" style={{ display: "block", marginBottom: 16 }}>
          配置 Jira 连接后，可通过 Webhook 自动将 Issue 创建为任务。
          工作流 YAML 中设置 <Text code>settings.jira_project</Text> 可指定关联的 Jira 项目。
        </Text>
        <Form form={jiraForm} onFinish={handleTestJira} layout="vertical">
          <Form.Item name="base_url" label="Jira URL" rules={[{ required: true }]}>
            <Input placeholder="https://your-domain.atlassian.net" />
          </Form.Item>
          <Form.Item name="api_token" label="API Token" rules={[{ required: true }]}>
            <Input.Password placeholder="Jira API Token" />
          </Form.Item>
          <Form.Item name="project_key" label="项目 Key" rules={[{ required: true }]}>
            <Input placeholder="PROJ" />
          </Form.Item>
          <Form.Item>
            <Button icon={<SendOutlined />} loading={testingJira} htmlType="submit">
              测试 Jira 连接
            </Button>
          </Form.Item>
        </Form>
      </Card>

      {/* Linear 配置 */}
      <Card
        title={
          <Space>
            <LinkOutlined />
            Linear 集成
          </Space>
        }
        style={{ marginBottom: 24 }}
      >
        <Text type="secondary" style={{ display: "block", marginBottom: 16 }}>
          配置 Linear 连接后，可通过 Webhook 自动将 Issue 创建为任务。
          工作流 YAML 中设置 <Text code>settings.linear_team</Text> 可指定关联的 Linear 团队。
        </Text>
        <Form form={linearForm} onFinish={handleTestLinear} layout="vertical">
          <Form.Item name="api_token" label="API Token" rules={[{ required: true }]}>
            <Input.Password placeholder="Linear API Token (lin_api_...)" />
          </Form.Item>
          <Form.Item>
            <Button icon={<SendOutlined />} loading={testingLinear} htmlType="submit">
              测试 Linear 连接
            </Button>
          </Form.Item>
        </Form>
      </Card>

      {/* Webhook 说明 */}
      <Card title="Webhook 配置指南" style={{ marginBottom: 24 }}>
        <Collapse
          items={[
            {
              key: "jira",
              label: "Jira Webhook 配置",
              children: (
                <div>
                  <Text>在 Jira 项目设置 → Webhooks 中添加：</Text>
                  <div style={{ background: "#f5f5f5", padding: 12, borderRadius: 8, margin: "8px 0" }}>
                    <Text code>{API_BASE}/api/integrations/jira/webhook</Text>
                  </div>
                  <Text type="secondary">事件：Issue Created, Issue Updated</Text>
                </div>
              ),
            },
            {
              key: "linear",
              label: "Linear Webhook 配置",
              children: (
                <div>
                  <Text>在 Linear 团队设置 → Webhooks 中添加：</Text>
                  <div style={{ background: "#f5f5f5", padding: 12, borderRadius: 8, margin: "8px 0" }}>
                    <Text code>{API_BASE}/api/integrations/linear/webhook</Text>
                  </div>
                  <Text type="secondary">事件：Issue Created</Text>
                </div>
              ),
            },
          ]}
        />
      </Card>
    </div>
  );
}
