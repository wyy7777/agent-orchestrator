import React, { useEffect, useState, useCallback } from "react";
import {
  Typography,
  Card,
  Table,
  Button,
  Space,
  Modal,
  Form,
  Input,
  Select,
  Tag,
  message,
  Spin,
  Tooltip,
  Row,
  Col,
  Divider,
  Alert,
} from "antd";
import {
  KeyOutlined,
  EditOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ApiOutlined,
  ThunderboltOutlined,
  SettingOutlined,
} from "@ant-design/icons";
import { settingsApi } from "@/lib/api";
import type { ApiProviderInfo } from "@/lib/api";

const { Title, Text, Paragraph } = Typography;

const PROVIDER_MODELS: Record<string, string[]> = {
  deepseek: ["deepseek-chat", "deepseek-coder", "deepseek-reasoner"],
  openai: ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
  claude: ["claude-sonnet-4-20250514", "claude-3-5-haiku-20241022"],
};

export default function ApiSettingsPage() {
  const [providers, setProviders] = useState<ApiProviderInfo[]>([]);
  const [defaultProvider, setDefaultProvider] = useState("deepseek");
  const [defaultModel, setDefaultModel] = useState("deepseek-chat");
  const [loading, setLoading] = useState(true);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editingProvider, setEditingProvider] = useState<ApiProviderInfo | null>(null);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<Record<string, { success: boolean; message: string }>>({});
  const [form] = Form.useForm();
  const [defaultsForm] = Form.useForm();

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const data = await settingsApi.getApiKeys();
      setProviders(data.providers);
      setDefaultProvider(data.default_provider);
      setDefaultModel(data.default_model);
      defaultsForm.setFieldsValue({
        default_provider: data.default_provider,
        default_model: data.default_model,
      });
    } catch {
      message.error("加载 API 配置失败");
    } finally {
      setLoading(false);
    }
  }, [defaultsForm]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleEdit = (provider: ApiProviderInfo) => {
    setEditingProvider(provider);
    form.setFieldsValue({
      api_key: "",
      base_url: provider.base_url,
    });
    setEditModalOpen(true);
  };

  const handleSaveKey = async (values: { api_key: string; base_url: string }) => {
    if (!editingProvider) return;
    setSaving(true);
    try {
      await settingsApi.updateApiKey({
        provider: editingProvider.name,
        api_key: values.api_key,
        base_url: values.base_url,
      });
      message.success(`${editingProvider.display_name} API Key 已保存`);
      setEditModalOpen(false);
      loadData();
    } catch (err) {
      message.error((err as Error).message || "保存失败");
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async (provider: ApiProviderInfo) => {
    setTesting(provider.name);
    try {
      const result = await settingsApi.testConnection({ provider: provider.name });
      setTestResults((prev) => ({ ...prev, [provider.name]: result }));
      if (result.success) {
        message.success(result.message);
      } else {
        message.warning(result.message);
      }
    } catch (err) {
      message.error((err as Error).message || "测试失败");
    } finally {
      setTesting(null);
    }
  };

  const handleUpdateDefaults = async (values: { default_provider: string; default_model: string }) => {
    try {
      await settingsApi.updateDefaults(values);
      setDefaultProvider(values.default_provider);
      setDefaultModel(values.default_model);
      message.success("默认模型已更新");
    } catch (err) {
      message.error((err as Error).message || "更新失败");
    }
  };

  const availableModels = PROVIDER_MODELS[defaultProvider] || [];

  const columns = [
    {
      title: "Provider",
      key: "provider",
      render: (_: unknown, record: ApiProviderInfo) => (
        <Space>
          <ApiOutlined style={{ color: record.key_configured ? "#52c41a" : "#d9d9d9" }} />
          <Text strong>{record.display_name}</Text>
        </Space>
      ),
    },
    {
      title: "API Key",
      key: "key",
      render: (_: unknown, record: ApiProviderInfo) => (
        <Space>
          {record.key_configured ? (
            <>
              <Tag color="success">已配置</Tag>
              <Text type="secondary" code>{record.key_preview}</Text>
            </>
          ) : (
            <Tag color="warning">未配置</Tag>
          )}
        </Space>
      ),
    },
    {
      title: "Base URL",
      dataIndex: "base_url",
      key: "base_url",
      render: (url: string) => (
        <Text type="secondary" style={{ fontSize: 12 }} copyable={!!url}>
          {url || "—"}
        </Text>
      ),
    },
    {
      title: "连接状态",
      key: "status",
      width: 120,
      render: (_: unknown, record: ApiProviderInfo) => {
        const result = testResults[record.name];
        if (!result) return <Text type="secondary">未测试</Text>;
        return result.success ? (
          <Tag icon={<CheckCircleOutlined />} color="success">正常</Tag>
        ) : (
          <Tooltip title={result.message}>
            <Tag icon={<CloseCircleOutlined />} color="error">失败</Tag>
          </Tooltip>
        );
      },
    },
    {
      title: "操作",
      key: "actions",
      width: 200,
      render: (_: unknown, record: ApiProviderInfo) => (
        <Space>
          <Button
            type="link"
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
          >
            {record.key_configured ? "修改" : "设置"}
          </Button>
          <Button
            type="link"
            icon={<ThunderboltOutlined />}
            loading={testing === record.name}
            onClick={() => handleTest(record)}
            disabled={!record.key_configured}
          >
            测试
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Title level={3}>
        <KeyOutlined style={{ marginRight: 8 }} />
        API 配置
      </Title>

      {/* 默认模型切换 */}
      <Card title="默认模型（全站通用）" style={{ marginBottom: 24 }}>
        <Paragraph type="secondary">
          设置全局默认的 AI Provider 和 Model。所有工作流步骤若未指定 config.provider，将使用此默认值。
        </Paragraph>
        <Form
          form={defaultsForm}
          layout="inline"
          onFinish={handleUpdateDefaults}
          initialValues={{ default_provider: defaultProvider, default_model: defaultModel }}
        >
          <Form.Item name="default_provider" label="Provider">
            <Select
              style={{ width: 160 }}
              onChange={(val: string) => {
                const models = PROVIDER_MODELS[val] || [];
                defaultsForm.setFieldsValue({ default_model: models[0] || "" });
              }}
              options={[
                { value: "deepseek", label: "DeepSeek" },
                { value: "openai", label: "OpenAI" },
                { value: "claude", label: "Claude" },
              ]}
            />
          </Form.Item>
          <Form.Item name="default_model" label="Model">
            <Select
              style={{ width: 200 }}
              options={availableModels.map((m) => ({ value: m, label: m }))}
            />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" icon={<SettingOutlined />}>
              保存默认设置
            </Button>
          </Form.Item>
        </Form>
      </Card>

      {/* API Key 管理 */}
      <Card title="API Key 管理">
        <Alert
          type="info"
          message="API Key 存储在服务器 .env 文件中，重启后仍然生效。修改后会立即生效，无需重启服务。"
          style={{ marginBottom: 16 }}
          showIcon
        />
        <Table
          dataSource={providers}
          columns={columns}
          rowKey="name"
          loading={loading}
          pagination={false}
        />
      </Card>

      {/* 编辑 API Key Modal */}
      <Modal
        title={`设置 ${editingProvider?.display_name || ""} API Key`}
        open={editModalOpen}
        onCancel={() => setEditModalOpen(false)}
        footer={null}
        width={520}
        destroyOnClose
      >
        <Form form={form} layout="vertical" onFinish={handleSaveKey}>
          <Form.Item
            name="api_key"
            label="API Key"
            rules={[{ required: true, message: "请输入 API Key" }]}
          >
            <Input.Password
              placeholder="sk-..."
              autoComplete="off"
            />
          </Form.Item>
          <Form.Item name="base_url" label="Base URL">
            <Input placeholder="https://api.deepseek.com" />
          </Form.Item>
          <Form.Item style={{ marginBottom: 0, textAlign: "right" }}>
            <Space>
              <Button onClick={() => setEditModalOpen(false)}>取消</Button>
              <Button type="primary" htmlType="submit" loading={saving}>
                保存
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
