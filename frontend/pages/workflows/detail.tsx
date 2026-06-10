import React, { useEffect, useState } from "react";
import {
  Typography, Card, Descriptions, Tag, Button, Space, message, Spin,
  Modal, Table, Tooltip,
} from "antd";
import { EditOutlined, PlayCircleOutlined, ArrowLeftOutlined, ShareAltOutlined, DownloadOutlined, CopyOutlined } from "@ant-design/icons";
import { useRouter } from "next/router";
import { workflowApi, taskApi } from "@/lib/api";
import type { WorkflowItem, TaskItem } from "@/lib/api";
import { statusColors } from "@/lib/constants";
import dynamic from "next/dynamic";

const MonacoEditor = dynamic(() => import("@monaco-editor/react"), { ssr: false });

const { Title, Text } = Typography;

export default function WorkflowDetailPage() {
  const router = useRouter();
  const id = typeof router.query.id === "string" ? router.query.id : undefined;
  const [workflow, setWorkflow] = useState<WorkflowItem | null>(null);
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editYaml, setEditYaml] = useState("");
  const [saving, setSaving] = useState(false);
  const [triggering, setTriggering] = useState(false);

  const load = async (signal?: AbortSignal) => {
    if (!id) return;
    setLoading(true);
    try {
      const [wf, tasksRes] = await Promise.all([
        workflowApi.get(id, signal),
        taskApi.list({ workflow_id: id, page_size: 20, signal }),
      ]);
      if (signal?.aborted) return;
      setWorkflow(wf);
      setTasks(tasksRes.items);
    } catch (err) {
      if (!signal?.aborted) {
        message.error("加载失败");
      }
    } finally {
      if (!signal?.aborted) {
        setLoading(false);
      }
    }
  };

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, [id]);

  const handleSaveYaml = async () => {
    if (!id) return;
    setSaving(true);
    try {
      await workflowApi.update(id, { yaml_definition: editYaml });
      message.success("已更新");
      setEditModalOpen(false);
      load();
    } catch (err) {
      message.error((err as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const handleTrigger = async () => {
    if (!id) return;
    setTriggering(true);
    try {
      const task = await taskApi.create({ workflow_id: id, trigger_type: "manual" });
      await taskApi.start(task.id);
      message.success("任务已创建");
      router.push(`/tasks/detail?id=${task.id}`);
    } catch (err) {
      message.error((err as Error).message);
    } finally {
      setTriggering(false);
    }
  };

  // 分享工作流
  const handleShare = async () => {
    if (!id) return;
    try {
      const result = await workflowApi.share(id);
      const shareUrl = `${window.location.origin}${result.share_url}`;
      await navigator.clipboard.writeText(shareUrl);
      message.success("分享链接已复制到剪贴板！");
    } catch (err) {
      message.error("分享失败");
    }
  };

  // 导出 YAML
  const handleExport = async () => {
    if (!id) return;
    try {
      const result = await workflowApi.export(id);
      const blob = new Blob([result.yaml], { type: "text/yaml" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = result.filename;
      a.click();
      URL.revokeObjectURL(url);
      message.success("导出成功");
    } catch (err) {
      message.error("导出失败");
    }
  };

  if (loading) return <Spin size="large" />;
  if (!workflow) return <Text>工作流不存在</Text>;

  return (
    <div>
      <Button
        icon={<ArrowLeftOutlined />}
        onClick={() => router.push("/workflows")}
        style={{ marginBottom: 16 }}
      >
        返回列表
      </Button>

      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 24 }}>
        <Title level={3}>{workflow.name}</Title>
        <Space>
          <Tooltip title="分享工作流">
            <Button icon={<ShareAltOutlined />} onClick={handleShare}>
              分享
            </Button>
          </Tooltip>
          <Tooltip title="导出 YAML 文件">
            <Button icon={<DownloadOutlined />} onClick={handleExport}>
              导出
            </Button>
          </Tooltip>
          <Button
            icon={<EditOutlined />}
            onClick={() => { setEditYaml(workflow.yaml_definition); setEditModalOpen(true); }}
          >
            编辑 YAML
          </Button>
          <Button
            type="primary"
            icon={<PlayCircleOutlined />}
            loading={triggering}
            onClick={handleTrigger}
          >
            立即执行
          </Button>
        </Space>
      </div>

      <Card style={{ marginBottom: 24 }}>
        <Descriptions column={2}>
          <Descriptions.Item label="ID">{workflow.id}</Descriptions.Item>
          <Descriptions.Item label="版本">v{workflow.version}</Descriptions.Item>
          <Descriptions.Item label="描述">{workflow.description || "-"}</Descriptions.Item>
          <Descriptions.Item label="创建时间">
            {new Date(workflow.created_at).toLocaleString("zh-CN")}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      <Card title="执行历史" style={{ marginBottom: 24 }}>
        <Table
          dataSource={tasks}
          rowKey="id"
          size="small"
          pagination={false}
          columns={[
            {
              title: "任务 ID",
              dataIndex: "id",
              render: (id: string) => (
                <Button type="link" size="small" onClick={() => router.push(`/tasks/detail?id=${id}`)}>
                  {id.substring(0, 8)}...
                </Button>
              ),
            },
            {
              title: "状态",
              dataIndex: "status",
              render: (s: string) => <Tag color={statusColors[s]}>{s}</Tag>,
            },
            { title: "Token", dataIndex: "total_tokens_used" },
            {
              title: "创建时间",
              dataIndex: "created_at",
              render: (v: string) => new Date(v).toLocaleString("zh-CN"),
            },
          ]}
        />
      </Card>

      <Modal
        title="编辑 YAML"
        open={editModalOpen}
        onOk={handleSaveYaml}
        onCancel={() => setEditModalOpen(false)}
        confirmLoading={saving}
        width={800}
      >
        <MonacoEditor
          height="500px"
          language="yaml"
          value={editYaml}
          onChange={(v) => setEditYaml(v || "")}
          options={{ minimap: { enabled: false }, fontSize: 14 }}
        />
      </Modal>
    </div>
  );
}
