import React, { useEffect, useState } from "react";
import { Typography, Table, Tag, Button, message, Space, Select, Empty } from "antd";
import { ReloadOutlined, RocketOutlined } from "@ant-design/icons";
import { useRouter } from "next/router";
import { taskApi, workflowApi } from "@/lib/api";
import type { TaskItem, WorkflowItem } from "@/lib/api";
import { statusColors } from "@/lib/constants";

const { Title } = Typography;

export default function TaskListPage() {
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<string | undefined>();
  const [workflows, setWorkflows] = useState<Record<string, WorkflowItem>>({});
  const router = useRouter();

  const load = async (p = page) => {
    setLoading(true);
    try {
      const [tasksRes, wfRes] = await Promise.all([
        taskApi.list({ skip: (p - 1) * 10, limit: 10, status: statusFilter }),
        workflowApi.list(0, 100),
      ]);
      setTasks(tasksRes.items);
      setTotal(tasksRes.total);
      const wfMap: Record<string, WorkflowItem> = {};
      wfRes.items.forEach((w) => (wfMap[w.id] = w));
      setWorkflows(wfMap);
    } catch (err) {
      message.error("加载失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load(1);
  }, [statusFilter]);

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 24 }}>
        <Title level={3}>任务列表</Title>
        <Space>
          <Select
            placeholder="筛选状态"
            allowClear
            style={{ width: 140 }}
            onChange={(v) => setStatusFilter(v)}
            options={[
              { label: "全部", value: undefined },
              { label: "等待中", value: "pending" },
              { label: "运行中", value: "running" },
              { label: "暂停", value: "paused" },
              { label: "已完成", value: "completed" },
              { label: "失败", value: "failed" },
            ]}
          />
          <Button icon={<ReloadOutlined />} onClick={() => load()}>
            刷新
          </Button>
        </Space>
      </div>

      {tasks.length === 0 && !loading ? (
        <Empty description="还没有任务">
          <Button
            type="primary"
            icon={<RocketOutlined />}
            onClick={() => router.push("/workflows")}
          >
            去创建任务
          </Button>
        </Empty>
      ) : (
      <Table
        dataSource={tasks}
        rowKey="id"
        loading={loading}
        pagination={{
          current: page,
          total,
          pageSize: 10,
          onChange: (p) => { setPage(p); load(p); },
        }}
        columns={[
          {
            title: "任务 ID",
            dataIndex: "id",
            render: (id: string) => (
              <Button type="link" onClick={() => router.push(`/tasks/detail?id=${id}`)}>
                {id.substring(0, 8)}...
              </Button>
            ),
          },
          {
            title: "工作流",
            dataIndex: "workflow_id",
            render: (wfId: string) => workflows[wfId]?.name || wfId.substring(0, 8),
          },
          {
            title: "状态",
            dataIndex: "status",
            render: (status: string) => <Tag color={statusColors[status]}>{status}</Tag>,
          },
          {
            title: "当前步骤",
            dataIndex: "current_step_index",
            render: (v: number, record: TaskItem) =>
              `${v + 1} / ${record.step_executions?.length || 0}`,
          },
          {
            title: "Token 消耗",
            dataIndex: "total_tokens_used",
            render: (v: number) => v.toLocaleString(),
          },
          {
            title: "创建时间",
            dataIndex: "created_at",
            render: (v: string) => new Date(v).toLocaleString("zh-CN"),
          },
          {
            title: "操作",
            render: (_: unknown, record: TaskItem) => (
              <Button
                size="small"
                onClick={() => router.push(`/tasks/detail?id=${record.id}`)}
              >
                详情
              </Button>
            ),
          },
        ]}
      />
      )}
    </div>
  );
}
