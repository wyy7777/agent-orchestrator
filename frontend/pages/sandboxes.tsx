import React, { useEffect, useState } from "react";
import {
  Typography, Table, Button, Space, Tag, message, Card, Modal, Input, Form, Popconfirm, Empty,
} from "antd";
import {
  PlusOutlined, DeleteOutlined, PlayCircleOutlined, ReloadOutlined, CloudServerOutlined,
} from "@ant-design/icons";
import { useRouter } from "next/router";

const { Title, Text } = Typography;
const { TextArea } = Input;

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:18000";

interface Sandbox {
  task_id: string;
  type: "docker" | "local";
  container_id?: string;
  sandbox_id?: string;
  workspace?: string;
}

export default function SandboxesPage() {
  const [sandboxes, setSandboxes] = useState<Sandbox[]>([]);
  const [loading, setLoading] = useState(false);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [execModalOpen, setExecModalOpen] = useState(false);
  const [selectedSandbox, setSelectedSandbox] = useState<Sandbox | null>(null);
  const [execResult, setExecResult] = useState<{ exit_code: number; output: string } | null>(null);
  const [executing, setExecuting] = useState(false);
  const [form] = Form.useForm();
  const [execForm] = Form.useForm();
  const router = useRouter();

  const load = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem("token");
      const res = await fetch(`${API_BASE}/api/sandboxes`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) throw new Error("加载失败");
      const data = await res.json();
      setSandboxes(data.items ?? data);
    } catch (err) {
      message.error("加载沙箱列表失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleCreate = async (values: { task_id: string }) => {
    try {
      const token = localStorage.getItem("token");
      const res = await fetch(`${API_BASE}/api/sandboxes`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(values),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "创建失败");
      }
      message.success("沙箱已创建");
      setCreateModalOpen(false);
      form.resetFields();
      load();
    } catch (err) {
      message.error((err as Error).message);
    }
  };

  const handleDestroy = async (taskId: string) => {
    try {
      const token = localStorage.getItem("token");
      const res = await fetch(`${API_BASE}/api/sandboxes/${taskId}`, {
        method: "DELETE",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) throw new Error("销毁失败");
      message.success("沙箱已销毁");
      load();
    } catch (err) {
      message.error((err as Error).message);
    }
  };

  const handleExecute = async (values: { command: string }) => {
    if (!selectedSandbox) return;
    setExecuting(true);
    setExecResult(null);
    try {
      const token = localStorage.getItem("token");
      const res = await fetch(`${API_BASE}/api/sandboxes/${selectedSandbox.task_id}/execute`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(values),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "执行失败");
      }
      const data = await res.json();
      setExecResult(data);
    } catch (err) {
      message.error((err as Error).message);
    } finally {
      setExecuting(false);
    }
  };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 24 }}>
        <Title level={3}>沙箱管理</Title>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={load}>刷新</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateModalOpen(true)}>
            创建沙箱
          </Button>
        </Space>
      </div>

      <Card>
        {sandboxes.length === 0 && !loading ? (
          <Empty description="暂无沙箱">
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateModalOpen(true)}>
              创建第一个沙箱
            </Button>
          </Empty>
        ) : (
          <Table
            dataSource={sandboxes}
            rowKey="task_id"
            loading={loading}
            columns={[
              {
                title: "任务 ID",
                dataIndex: "task_id",
                render: (id: string) => <Text code>{id.substring(0, 12)}...</Text>,
              },
              {
                title: "类型",
                dataIndex: "type",
                render: (type: string) => (
                  <Tag color={type === "docker" ? "blue" : "green"}>
                    {type === "docker" ? "Docker" : "本地"}
                  </Tag>
                ),
              },
              {
                title: "标识",
                render: (_: unknown, record: Sandbox) => (
                  <Text code>
                    {record.type === "docker"
                      ? record.container_id?.substring(0, 12)
                      : record.sandbox_id}
                  </Text>
                ),
              },
              {
                title: "工作目录",
                dataIndex: "workspace",
                ellipsis: true,
                render: (path: string) => path || "-",
              },
              {
                title: "状态",
                render: () => <Tag color="green">运行中</Tag>,
              },
              {
                title: "操作",
                render: (_: unknown, record: Sandbox) => (
                  <Space>
                    <Button
                      size="small"
                      icon={<PlayCircleOutlined />}
                      onClick={() => {
                        setSelectedSandbox(record);
                        setExecModalOpen(true);
                        setExecResult(null);
                        execForm.resetFields();
                      }}
                    >
                      执行命令
                    </Button>
                    <Popconfirm
                      title="确定销毁此沙箱？"
                      onConfirm={() => handleDestroy(record.task_id)}
                    >
                      <Button size="small" danger icon={<DeleteOutlined />}>销毁</Button>
                    </Popconfirm>
                  </Space>
                ),
              },
            ]}
          />
        )}
      </Card>

      {/* 创建沙箱 Modal */}
      <Modal
        title="创建沙箱"
        open={createModalOpen}
        onCancel={() => setCreateModalOpen(false)}
        footer={null}
      >
        <Form form={form} onFinish={handleCreate} layout="vertical">
          <Form.Item
            name="task_id"
            label="任务 ID"
            rules={[{ required: true, message: "请输入任务 ID" }]}
          >
            <Input placeholder="输入关联的任务 ID" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" block>创建</Button>
          </Form.Item>
        </Form>
      </Modal>

      {/* 执行命令 Modal */}
      <Modal
        title={`执行命令 - ${selectedSandbox?.task_id?.substring(0, 8)}...`}
        open={execModalOpen}
        onCancel={() => setExecModalOpen(false)}
        footer={null}
        width={700}
      >
        <Form form={execForm} onFinish={handleExecute} layout="vertical">
          <Form.Item
            name="command"
            label="命令"
            rules={[{ required: true, message: "请输入要执行的命令" }]}
          >
            <TextArea rows={2} placeholder="例如: ls -la /workspace" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={executing} block>
              执行
            </Button>
          </Form.Item>
        </Form>

        {execResult && (
          <Card
            title="执行结果"
            style={{ marginTop: 16 }}
            extra={<Tag color={execResult.exit_code === 0 ? "green" : "red"}>
              退出码: {execResult.exit_code}
            </Tag>}
          >
            <pre style={{
              background: "#f5f5f5",
              padding: 12,
              borderRadius: 8,
              maxHeight: 300,
              overflow: "auto",
              fontSize: 13,
              fontFamily: "monospace",
            }}>
              {execResult.output || "(无输出)"}
            </pre>
          </Card>
        )}
      </Modal>
    </div>
  );
}
