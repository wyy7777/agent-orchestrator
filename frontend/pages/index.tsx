import React, { useEffect, useState } from "react";
import { Typography, Spin, message, Card, Table, Tag, Button, Space, Empty } from "antd";
import { PlusOutlined, ReloadOutlined, RocketOutlined } from "@ant-design/icons";
import { useRouter } from "next/router";
import DashboardStats from "@/components/DashboardStats";
import { dashboardApi, taskApi, workflowApi } from "@/lib/api";
import type { DashboardStatsData, TaskItem, WorkflowItem } from "@/lib/api";

const { Title, Text, Paragraph } = Typography;

const statusColors: Record<string, string> = {
  pending: "default",
  running: "processing",
  paused: "warning",
  completed: "success",
  failed: "error",
  rolled_back: "orange",
};

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStatsData | null>(null);
  const [recentTasks, setRecentTasks] = useState<TaskItem[]>([]);
  const [workflows, setWorkflows] = useState<Record<string, WorkflowItem>>({});
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  const loadData = async () => {
    setLoading(true);
    try {
      const [statsData, tasksData, wfData] = await Promise.all([
        dashboardApi.stats(),
        taskApi.list({ limit: 10 }),
        workflowApi.list(0, 100),
      ]);
      setStats(statsData);
      setRecentTasks(tasksData.items);

      const wfMap: Record<string, WorkflowItem> = {};
      wfData.items.forEach((w) => (wfMap[w.id] = w));
      setWorkflows(wfMap);
    } catch (err) {
      message.error("加载数据失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 24 }}>
        <Title level={3}>仪表盘</Title>
        <Button icon={<ReloadOutlined />} onClick={loadData}>
          刷新
        </Button>
      </div>

      <Spin spinning={loading}>
        <DashboardStats stats={stats} />

        <Card
          title="最近任务"
          style={{ marginTop: 24 }}
          extra={
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => router.push("/tasks")}
            >
              查看全部
            </Button>
          }
        >
          {recentTasks.length === 0 && !loading ? (
            <Empty description="还没有执行过任务">
              <Button
                type="primary"
                icon={<RocketOutlined />}
                onClick={() => router.push("/workflows")}
              >
                去创建工作流
              </Button>
            </Empty>
          ) : (
            <Table
            dataSource={recentTasks}
            rowKey="id"
            pagination={false}
            size="small"
            columns={[
              {
                title: "任务 ID",
                dataIndex: "id",
                render: (id: string) => (
                  <Button
                    type="link"
                    size="small"
                    onClick={() => router.push(`/tasks/detail?id=${id}`)}
                  >
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
                render: (status: string) => (
                  <Tag color={statusColors[status]}>{status}</Tag>
                ),
              },
              {
                title: "Token",
                dataIndex: "total_tokens_used",
                render: (v: number) => v.toLocaleString(),
              },
              {
                title: "触发方式",
                dataIndex: "trigger_type",
                render: (v: string) => v || "手动",
              },
              {
                title: "创建时间",
                dataIndex: "created_at",
                render: (v: string) => new Date(v).toLocaleString("zh-CN"),
              },
            ]}
          />
          )}
        </Card>
      </Spin>
    </div>
  );
}

