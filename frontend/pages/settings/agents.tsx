import React, { useEffect, useState } from "react";
import {
  Typography,
  Card,
  Table,
  Button,
  Space,
  Modal,
  Form,
  Input,
  InputNumber,
  Select,
  Switch,
  Tag,
  message,
  Popconfirm,
  Spin,
  Slider,
  Tooltip,
  Row,
  Col,
} from "antd";
import {
  RobotOutlined,
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  ReloadOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
} from "@ant-design/icons";
import { agentApi } from "@/lib/api";
import type { AgentConfigItem, AgentCreatePayload } from "@/lib/api";

const { Title, Text } = Typography;

const PROVIDER_OPTIONS = [
  { value: "deepseek", label: "DeepSeek" },
  { value: "openai", label: "OpenAI" },
  { value: "claude", label: "Claude" },
  { value: "ollama", label: "Ollama (本地)" },
];

const CAPABILITY_OPTIONS = [
  { value: "analyze", label: "分析 (analyze)" },
  { value: "execute", label: "执行 (execute)" },
  { value: "review", label: "审查 (review)" },
  { value: "security", label: "安全 (security)" },
  { value: "docs", label: "文档 (docs)" },
  { value: "script", label: "脚本 (script)" },
  { value: "merge", label: "合并 (merge)" },
];

export default function AgentsPage() {
  const [agents, setAgents] = useState<AgentConfigItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<AgentConfigItem | null>(null);
  const [saving, setSaving] = useState(false);
  const [form] = Form.useForm();

  const loadAgents = async () => {
    setLoading(true);
    try {
      const data = await agentApi.list();
      setAgents(data);
    } catch {
      message.error("加载 Agent 列表失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAgents();
  }, []);

  const handleAdd = () => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({
      provider: "deepseek",
      model: "deepseek-chat",
      max_tokens: 4096,
      temperature: 0.7,
      timeout_seconds: 300,
      token_budget: 0,
      enabled: true,
      capabilities: [],
    });
    setModalOpen(true);
  };

  const handleEdit = (agent: AgentConfigItem) => {
    setEditing(agent);
    form.setFieldsValue({
      name: agent.name,
      display_name: agent.display_name,
      description: agent.description,
      capabilities: agent.capabilities,
      provider: agent.provider,
      model: agent.model,
      max_tokens: agent.max_tokens,
      temperature: agent.temperature,
      timeout_seconds: agent.timeout_seconds,
      token_budget: agent.token_budget,
      enabled: agent.enabled,
    });
    setModalOpen(true);
  };

  const handleSave = async (values: AgentCreatePayload) => {
    setSaving(true);
    try {
      if (editing) {
        await agentApi.update(editing.id, values);
        message.success("Agent 已更新");
      } else {
        await agentApi.create(values);
        message.success("Agent 已创建");
      }
      setModalOpen(false);
      loadAgents();
    } catch (err) {
      message.error((err as Error).message || "保存失败");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await agentApi.delete(id);
      message.success("Agent 已删除");
      loadAgents();
    } catch {
      message.error("删除失败");
    }
  };

  const handleToggleEnabled = async (agent: AgentConfigItem) => {
    try {
      await agentApi.update(agent.id, {
        ...agent,
        enabled: !agent.enabled,
      });
      message.success(agent.enabled ? "已禁用" : "已启用");
      loadAgents();
    } catch {
      message.error("操作失败");
    }
  };

  const columns = [
    {
      title: "名称",
      dataIndex: "display_name",
      key: "display_name",
      render: (text: string, record: AgentConfigItem) => (
        <Space>
          <RobotOutlined style={{ color: record.enabled ? "#1677ff" : "#d9d9d9" }} />
          <Text strong>{text}</Text>
          <Text type="secondary" style={{ fontSize: 12 }}>({record.name})</Text>
        </Space>
      ),
    },
    {
      title: "能力",
      dataIndex: "capabilities",
      key: "capabilities",
      render: (caps: string[]) =>
        caps && caps.length > 0 ? (
          <Space size={[0, 4]} wrap>
            {caps.map((c) => (
              <Tag key={c} color="blue">{c}</Tag>
            ))}
          </Space>
        ) : (
          <Tag color="default">通用</Tag>
        ),
    },
    {
      title: "模型",
      key: "model",
      render: (_: unknown, record: AgentConfigItem) => (
        <Space>
          <Tag>{record.provider}</Tag>
          <Text>{record.model}</Text>
        </Space>
      ),
    },
    {
      title: "Token 预算",
      dataIndex: "token_budget",
      key: "token_budget",
      width: 120,
      render: (v: number) => (v > 0 ? v.toLocaleString() : "无限制"),
    },
    {
      title: "状态",
      dataIndex: "enabled",
      key: "enabled",
      width: 100,
      render: (enabled: boolean, record: AgentConfigItem) => (
        <Tooltip title={enabled ? "点击禁用" : "点击启用"}>
          <Switch
            checked={enabled}
            checkedChildren={<CheckCircleOutlined />}
            unCheckedChildren={<CloseCircleOutlined />}
            onChange={() => handleToggleEnabled(record)}
          />
        </Tooltip>
      ),
    },
    {
      title: "操作",
      key: "actions",
      width: 150,
      render: (_: unknown, record: AgentConfigItem) => (
        <Space>
          <Button
            type="link"
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
          >
            编辑
          </Button>
          <Popconfirm
            title="确认删除此 Agent？"
            onConfirm={() => handleDelete(record.id)}
          >
            <Button type="link" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 24 }}>
        <Title level={3} style={{ margin: 0 }}>
          <RobotOutlined style={{ marginRight: 8 }} />
          Agent 管理
        </Title>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={loadAgents}>
            刷新
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>
            新建 Agent
          </Button>
        </Space>
      </div>

      <Card>
        <Table
          dataSource={agents}
          columns={columns}
          rowKey="id"
          loading={loading}
          pagination={false}
          locale={{ emptyText: "暂无已注册的 Agent，点击「新建 Agent」开始" }}
        />
      </Card>

      <Modal
        title={editing ? "编辑 Agent" : "新建 Agent"}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        footer={null}
        width={640}
        destroyOnClose
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSave}
        >
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="name"
                label="标识名称"
                rules={[{ required: true, message: "请输入标识名称" }]}
                tooltip="用于 YAML 中 config.agent 引用，不可修改"
              >
                <Input placeholder="如: code-analyst" disabled={!!editing} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="display_name"
                label="显示名称"
                rules={[{ required: true, message: "请输入显示名称" }]}
              >
                <Input placeholder="如: 代码分析专家" />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} placeholder="Agent 的职责描述..." />
          </Form.Item>

          <Form.Item name="capabilities" label="能力标签">
            <Select
              mode="multiple"
              options={CAPABILITY_OPTIONS}
              placeholder="选择能力（留空表示通用）"
              allowClear
            />
          </Form.Item>

          <Row gutter={16}>
            <Col span={8}>
              <Form.Item name="provider" label="AI 提供商" rules={[{ required: true }]}>
                <Select options={PROVIDER_OPTIONS} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="model" label="模型" rules={[{ required: true }]}>
                <Input placeholder="deepseek-chat" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="max_tokens" label="最大 Token">
                <InputNumber min={256} max={128000} style={{ width: "100%" }} />
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={8}>
              <Form.Item name="temperature" label="Temperature">
                <Slider min={0} max={2} step={0.1} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="timeout_seconds" label="超时（秒）">
                <InputNumber min={10} max={3600} style={{ width: "100%" }} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="token_budget" label="Token 预算" tooltip="0 表示无限制">
                <InputNumber min={0} style={{ width: "100%" }} />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item name="enabled" label="启用" valuePropName="checked">
            <Switch checkedChildren="启用" unCheckedChildren="禁用" />
          </Form.Item>

          <Form.Item style={{ marginBottom: 0, textAlign: "right" }}>
            <Space>
              <Button onClick={() => setModalOpen(false)}>取消</Button>
              <Button type="primary" htmlType="submit" loading={saving}>
                {editing ? "保存" : "创建"}
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
