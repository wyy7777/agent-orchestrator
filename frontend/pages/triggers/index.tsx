import React, { useEffect, useState, useCallback } from "react";
import {
  Typography, Tabs, Table, Button, Space, Tag, Form, Input, Select,
  Modal, message, Popconfirm, Switch, Card, Tooltip, Empty, Spin,
} from "antd";
import {
  PlusOutlined, DeleteOutlined, CopyOutlined, ReloadOutlined,
  LinkOutlined, ClockCircleOutlined, CheckCircleOutlined,
  PauseCircleOutlined, ApiOutlined,
} from "@ant-design/icons";
import { workflowApi } from "@/lib/api";
import type { WorkflowItem } from "@/lib/api";

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;

// ==================== 类型定义 ====================

interface WebhookItem {
  id: string;
  name: string;
  url: string;
  secret: string | null;
  workflow_id: string;
  events: string[];
  enabled: boolean;
  created_at: string;
}

interface ScheduleItem {
  id: string;
  name: string;
  workflow_id: string;
  cron: string;
  payload: Record<string, unknown>;
  enabled: boolean;
  last_run_at: string | null;
  next_run_at: string | null;
  created_at: string;
}

// ==================== API 封装 ====================

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:18000";

async function apiRequest<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `请求失败: ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

const webhookApi = {
  list: () => apiRequest<WebhookItem[]>("/api/webhooks"),
  create: (data: Omit<WebhookItem, "id" | "url" | "created_at">) =>
    apiRequest<WebhookItem>("/api/webhooks", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  delete: (id: string) =>
    apiRequest<void>(`/api/webhooks/${id}`, { method: "DELETE" }),
};

const scheduleApi = {
  list: () => apiRequest<ScheduleItem[]>("/api/schedules"),
  create: (data: Omit<ScheduleItem, "id" | "last_run_at" | "next_run_at" | "created_at">) =>
    apiRequest<ScheduleItem>("/api/schedules", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  toggle: (id: string, enabled: boolean) =>
    apiRequest<ScheduleItem>(`/api/schedules/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ enabled }),
    }),
  delete: (id: string) =>
    apiRequest<void>(`/api/schedules/${id}`, { method: "DELETE" }),
};

// ==================== Webhook 标签页 ====================

function WebhookTab({ workflows }: { workflows: WorkflowItem[] }) {
  const [webhooks, setWebhooks] = useState<WebhookItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [form] = Form.useForm();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await webhookApi.list() as any;
      setWebhooks(data.items ?? data);
    } catch {
      message.error("加载 Webhook 列表失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleCreate = async () => {
    try {
      const values = await form.validateFields();
      await webhookApi.create({
        name: values.name,
        secret: values.secret || null,
        workflow_id: values.workflow_id,
        events: values.events || [],
        enabled: true,
      });
      message.success("Webhook 创建成功");
      setModalOpen(false);
      form.resetFields();
      load();
    } catch {
      // 校验失败不处理
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await webhookApi.delete(id);
      message.success("已删除");
      load();
    } catch {
      message.error("删除失败");
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text).then(
      () => message.success("已复制到剪贴板"),
      () => message.error("复制失败"),
    );
  };

  const columns = [
    {
      title: "名称",
      dataIndex: "name",
    },
    {
      title: "Webhook URL",
      dataIndex: "url",
      render: (url: string) => (
        <Space>
          <Text code copyable={false} style={{ maxWidth: 360, overflow: "hidden", textOverflow: "ellipsis" }}>
            {url}
          </Text>
          <Tooltip title="复制 URL">
            <Button type="text" size="small" icon={<CopyOutlined />} onClick={() => copyToClipboard(url)} />
          </Tooltip>
        </Space>
      ),
    },
    {
      title: "关联工作流",
      dataIndex: "workflow_id",
      render: (wfId: string) => {
        const wf = workflows.find((w) => w.id === wfId);
        return wf?.name || wfId.substring(0, 8);
      },
    },
    {
      title: "事件",
      dataIndex: "events",
      render: (events: string[]) =>
        events?.length > 0
          ? events.map((e) => <Tag key={e} color="blue">{e}</Tag>)
          : <Text type="secondary">全部</Text>,
    },
    {
      title: "状态",
      dataIndex: "enabled",
      render: (enabled: boolean) => (
        <Tag color={enabled ? "success" : "default"} icon={enabled ? <CheckCircleOutlined /> : <PauseCircleOutlined />}>
          {enabled ? "启用" : "禁用"}
        </Tag>
      ),
    },
    {
      title: "创建时间",
      dataIndex: "created_at",
      render: (v: string) => new Date(v).toLocaleString("zh-CN"),
    },
    {
      title: "操作",
      width: 100,
      render: (_: unknown, record: WebhookItem) => (
        <Popconfirm title="确定删除此 Webhook？" onConfirm={() => handleDelete(record.id)}>
          <Button size="small" danger icon={<DeleteOutlined />}>删除</Button>
        </Popconfirm>
      ),
    },
  ];

  return (
    <div>
      {/* Webhook 使用说明 */}
      <Card size="small" style={{ marginBottom: 16, background: "#f6ffed", border: "1px solid #b7eb8f" }}>
        <Space direction="vertical" size={4}>
          <Text strong>
            <ApiOutlined /> Webhook 使用说明
          </Text>
          <Text type="secondary">
            创建 Webhook 后会生成唯一 URL，将其配置到 GitHub、GitLab 等平台的 Webhook 设置中，
            当对应事件触发时将自动创建工作流任务。
          </Text>
        </Space>
      </Card>

      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
        <Button icon={<ReloadOutlined />} onClick={load}>刷新</Button>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
          添加 Webhook
        </Button>
      </div>

      <Table
        dataSource={webhooks}
        columns={columns}
        rowKey="id"
        loading={loading}
        pagination={false}
        locale={{ emptyText: <Empty description="还没有配置 Webhook" /> }}
      />

      {/* 创建 Webhook 弹窗 */}
      <Modal
        title="添加 Webhook"
        open={modalOpen}
        onOk={handleCreate}
        onCancel={() => { setModalOpen(false); form.resetFields(); }}
        okText="创建"
        cancelText="取消"
        destroyOnClose
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item name="name" label="名称" rules={[{ required: true, message: "请输入 Webhook 名称" }]}>
            <Input placeholder="例如：GitHub PR 触发" />
          </Form.Item>
          <Form.Item name="workflow_id" label="关联工作流" rules={[{ required: true, message: "请选择工作流" }]}>
            <Select placeholder="选择要触发的工作流">
              {workflows.map((wf) => (
                <Select.Option key={wf.id} value={wf.id}>{wf.name}</Select.Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item name="events" label="监听事件">
            <Select
              mode="multiple"
              placeholder="留空则监听所有事件"
              options={[
                { label: "push", value: "push" },
                { label: "pull_request", value: "pull_request" },
                { label: "issues", value: "issues" },
                { label: "release", value: "release" },
                { label: "tag", value: "tag" },
              ]}
            />
          </Form.Item>
          <Form.Item name="secret" label="Secret（可选）">
            <Input.Password placeholder="用于验证 Webhook 请求的签名" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}

// ==================== 定时任务标签页 ====================

function ScheduleTab({ workflows }: { workflows: WorkflowItem[] }) {
  const [schedules, setSchedules] = useState<ScheduleItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [form] = Form.useForm();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await scheduleApi.list() as any;
      setSchedules(data.items ?? data);
    } catch {
      message.error("加载定时任务列表失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleCreate = async () => {
    try {
      const values = await form.validateFields();
      let payload: Record<string, unknown> = {};
      if (values.payload) {
        try {
          payload = JSON.parse(values.payload);
        } catch {
          message.error("Payload JSON 格式不正确");
          return;
        }
      }
      await scheduleApi.create({
        name: values.name,
        workflow_id: values.workflow_id,
        cron: values.cron,
        payload,
        enabled: true,
      });
      message.success("定时任务创建成功");
      setModalOpen(false);
      form.resetFields();
      load();
    } catch {
      // 校验失败不处理
    }
  };

  const handleToggle = async (id: string, enabled: boolean) => {
    try {
      await scheduleApi.toggle(id, enabled);
      message.success(enabled ? "已启用" : "已禁用");
      load();
    } catch {
      message.error("操作失败");
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await scheduleApi.delete(id);
      message.success("已删除");
      load();
    } catch {
      message.error("删除失败");
    }
  };

  const columns = [
    {
      title: "名称",
      dataIndex: "name",
    },
    {
      title: "关联工作流",
      dataIndex: "workflow_id",
      render: (wfId: string) => {
        const wf = workflows.find((w) => w.id === wfId);
        return wf?.name || wfId.substring(0, 8);
      },
    },
    {
      title: "Cron 表达式",
      dataIndex: "cron",
      render: (cron: string) => <Tag color="purple">{cron}</Tag>,
    },
    {
      title: "启用",
      dataIndex: "enabled",
      width: 80,
      render: (enabled: boolean, record: ScheduleItem) => (
        <Switch checked={enabled} onChange={(checked) => handleToggle(record.id, checked)} />
      ),
    },
    {
      title: "上次运行",
      dataIndex: "last_run_at",
      render: (v: string | null) => v ? new Date(v).toLocaleString("zh-CN") : <Text type="secondary">-</Text>,
    },
    {
      title: "下次运行",
      dataIndex: "next_run_at",
      render: (v: string | null) => v ? new Date(v).toLocaleString("zh-CN") : <Text type="secondary">-</Text>,
    },
    {
      title: "创建时间",
      dataIndex: "created_at",
      render: (v: string) => new Date(v).toLocaleString("zh-CN"),
    },
    {
      title: "操作",
      width: 100,
      render: (_: unknown, record: ScheduleItem) => (
        <Popconfirm title="确定删除此定时任务？" onConfirm={() => handleDelete(record.id)}>
          <Button size="small" danger icon={<DeleteOutlined />}>删除</Button>
        </Popconfirm>
      ),
    },
  ];

  const cronPresets = [
    { label: "每分钟", value: "* * * * *" },
    { label: "每小时", value: "0 * * * *" },
    { label: "每天 0 点", value: "0 0 * * *" },
    { label: "每天 9 点", value: "0 9 * * *" },
    { label: "每周一 9 点", value: "0 9 * * 1" },
    { label: "每月 1 号 0 点", value: "0 0 1 * *" },
  ];

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
        <Button icon={<ReloadOutlined />} onClick={load}>刷新</Button>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
          创建定时任务
        </Button>
      </div>

      <Table
        dataSource={schedules}
        columns={columns}
        rowKey="id"
        loading={loading}
        pagination={false}
        locale={{ emptyText: <Empty description="还没有定时任务" /> }}
      />

      {/* 创建定时任务弹窗 */}
      <Modal
        title="创建定时任务"
        open={modalOpen}
        onOk={handleCreate}
        onCancel={() => { setModalOpen(false); form.resetFields(); }}
        okText="创建"
        cancelText="取消"
        width={600}
        destroyOnClose
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item name="name" label="名称" rules={[{ required: true, message: "请输入任务名称" }]}>
            <Input placeholder="例如：每日代码质量检查" />
          </Form.Item>
          <Form.Item name="workflow_id" label="关联工作流" rules={[{ required: true, message: "请选择工作流" }]}>
            <Select placeholder="选择要调度的工作流">
              {workflows.map((wf) => (
                <Select.Option key={wf.id} value={wf.id}>{wf.name}</Select.Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item
            name="cron"
            label="Cron 表达式"
            rules={[{ required: true, message: "请输入 Cron 表达式" }]}
            extra="格式：分 时 日 月 周（例如 0 9 * * * 表示每天 9 点）"
          >
            <Input
              placeholder="0 9 * * *"
              addonAfter={
                <Select
                  style={{ width: 140 }}
                  placeholder="快速选择"
                  onChange={(val) => form.setFieldsValue({ cron: val })}
                  options={cronPresets}
                />
              }
            />
          </Form.Item>
          <Form.Item
            name="payload"
            label="Payload（可选）"
            extra="JSON 格式，作为工作流的输入参数"
          >
            <TextArea
              rows={4}
              placeholder={'{\n  "branch": "main",\n  "env": "production"\n}'}
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}

// ==================== 主页面 ====================

export default function TriggersPage() {
  const [workflows, setWorkflows] = useState<WorkflowItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const res = await workflowApi.list(0, 100);
        setWorkflows(res.items);
      } catch {
        message.error("加载工作流列表失败");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) {
    return (
      <div style={{ textAlign: "center", padding: 80 }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 24 }}>
        <Title level={3}>
          <LinkOutlined style={{ marginRight: 8 }} />
          触发器管理
        </Title>
      </div>

      <Tabs
        defaultActiveKey="webhook"
        items={[
          {
            key: "webhook",
            label: (
              <span>
                <ApiOutlined />
                Webhook
              </span>
            ),
            children: <WebhookTab workflows={workflows} />,
          },
          {
            key: "schedule",
            label: (
              <span>
                <ClockCircleOutlined />
                定时任务
              </span>
            ),
            children: <ScheduleTab workflows={workflows} />,
          },
        ]}
      />
    </div>
  );
}
