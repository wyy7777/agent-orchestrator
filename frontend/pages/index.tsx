import React, { useEffect, useState, useMemo, useCallback } from "react";
import { Typography, Spin, message, Card, Table, Tag, Button, Space, Row, Col, Empty, Alert, List, Modal } from "antd";
import {
  PlusOutlined,
  ReloadOutlined,
  RocketOutlined,
  DownloadOutlined,
  BugOutlined,
  EyeOutlined,
  SafetyOutlined,
  ThunderboltOutlined,
  ImportOutlined,
  BellOutlined,
} from "@ant-design/icons";
import { useRouter } from "next/router";
import { Line, Pie, Column } from "@ant-design/charts";
import DashboardStats from "@/components/DashboardStats";
import { dashboardApi, taskApi, workflowApi } from "@/lib/api";
import type { DashboardStatsData, TaskItem, WorkflowItem } from "@/lib/api";
import { statusColors } from "@/lib/constants";
import { useI18n } from "@/lib/i18n";

const { Title, Text } = Typography;

/** 用例卡片数据 */
const USE_CASES = [
  {
    icon: <BugOutlined style={{ fontSize: 32, color: "#ff4d4f" }} />,
    title: "自动修 Bug",
    titleEn: "Auto Fix Bugs",
    desc: "贴 Issue 链接 → AI 分析 → 你审批 → AI 修复 → 自动发 PR",
    descEn: "Paste Issue link → AI analyzes → You approve → AI fixes → Auto PR",
    time: "5 min",
    color: "#fff1f0",
  },
  {
    icon: <EyeOutlined style={{ fontSize: 32, color: "#1677ff" }} />,
    title: "代码审查",
    titleEn: "Code Review",
    desc: "贴 PR 链接 → AI 审查 → 生成质量报告 → 发评论",
    descEn: "Paste PR link → AI reviews → Quality report → Post comments",
    time: "3 min",
    color: "#e6f4ff",
  },
  {
    icon: <SafetyOutlined style={{ fontSize: 32, color: "#52c41a" }} />,
    title: "安全扫描",
    titleEn: "Security Scan",
    desc: "一键扫描代码 → 发现漏洞 → 生成报告 → 告警通知",
    descEn: "One-click scan → Find vulnerabilities → Report → Alert",
    time: "2 min",
    color: "#f6ffed",
  },
];

/** 最近 N 天的日期标签 */
function recentDays(n: number): string[] {
  const days: string[] = [];
  for (let i = n - 1; i >= 0; i--) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    days.push(d.toISOString().slice(0, 10));
  }
  return days;
}

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStatsData | null>(null);
  const [recentTasks, setRecentTasks] = useState<TaskItem[]>([]);
  const [workflows, setWorkflows] = useState<Record<string, WorkflowItem>>({});
  const [allTasks, setAllTasks] = useState<TaskItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [pendingApprovals, setPendingApprovals] = useState(0);
  const [showWelcome, setShowWelcome] = useState(false);
  const router = useRouter();
  const { t, locale } = useI18n();

  const loadData = async (signal?: AbortSignal) => {
    setLoading(true);
    try {
      const [statsData, tasksData, wfData, allTasksData] = await Promise.all([
        dashboardApi.stats(signal),
        taskApi.list({ page_size: 10, signal }),
        workflowApi.list(0, 100, signal),
        taskApi.list({ page_size: 200, signal }),
      ]);
      if (signal?.aborted) return;
      setStats(statsData);
      setRecentTasks(tasksData.items);
      setAllTasks(allTasksData.items);

      const wfMap: Record<string, WorkflowItem> = {};
      wfData.items.forEach((w) => (wfMap[w.id] = w));
      setWorkflows(wfMap);
    } catch (err) {
      if (!signal?.aborted) {
        message.error(t("common.error"));
      }
    } finally {
      if (!signal?.aborted) {
        setLoading(false);
      }
    }
  };

  useEffect(() => {
    const controller = new AbortController();
    loadData(controller.signal);
    return () => controller.abort();
  }, []);

  // 检查待审批任务数量
  useEffect(() => {
    if (stats && stats.pending_approvals > 0) {
      setPendingApprovals(stats.pending_approvals);
      // 浏览器通知
      if ("Notification" in window && Notification.permission === "granted") {
        new Notification("Agent Orchestrator", {
          body: `有 ${stats.pending_approvals} 个任务等待你的审批`,
          icon: "/favicon.ico",
        });
      }
    }
  }, [stats]);

  // 首次访问显示欢迎弹窗
  useEffect(() => {
    const hasVisited = localStorage.getItem("hasVisited");
    if (!hasVisited && !loading) {
      setShowWelcome(true);
      localStorage.setItem("hasVisited", "true");
    }
  }, [loading]);

  const handleRefresh = () => {
    loadData();
  };

  // ---- 图表数据计算 ----

  /** 最近 7 天任务趋势 */
  const trendData = useMemo(() => {
    const days = recentDays(7);
    const dayMap: Record<string, number> = {};
    days.forEach((d) => (dayMap[d] = 0));
    allTasks.forEach((t) => {
      const day = t.created_at.slice(0, 10);
      if (day in dayMap) dayMap[day]++;
    });
    return days.map((d) => ({ date: d.slice(5), count: dayMap[d] }));
  }, [allTasks]);

  /** 成功率饼图 */
  const pieData = useMemo(() => {
    if (!stats) return [];
    return [
      { type: "已完成", value: stats.completed_tasks },
      { type: "失败", value: stats.failed_tasks },
      { type: "运行中", value: stats.running_tasks },
      { type: "其他", value: Math.max(0, stats.total_tasks - stats.completed_tasks - stats.failed_tasks - stats.running_tasks) },
    ].filter((d) => d.value > 0);
  }, [stats]);

  /** Token 消耗柱状图（按工作流聚合） */
  const tokenBarData = useMemo(() => {
    const wfTokens: Record<string, number> = {};
    allTasks.forEach((t) => {
      const name = workflows[t.workflow_id]?.name || t.workflow_id.slice(0, 8);
      wfTokens[name] = (wfTokens[name] || 0) + t.total_tokens_used;
    });
    return Object.entries(wfTokens)
      .map(([workflow, tokens]) => ({ workflow, tokens }))
      .sort((a, b) => b.tokens - a.tokens)
      .slice(0, 8);
  }, [allTasks, workflows]);

  /** 热门工作流 TOP 5 */
  const topWorkflows = useMemo(() => {
    const wfCount: Record<string, { name: string; count: number }> = {};
    allTasks.forEach((t) => {
      const wfId = t.workflow_id;
      if (!wfCount[wfId]) {
        wfCount[wfId] = { name: workflows[wfId]?.name || wfId.slice(0, 8), count: 0 };
      }
      wfCount[wfId].count++;
    });
    return Object.values(wfCount)
      .sort((a, b) => b.count - a.count)
      .slice(0, 5);
  }, [allTasks, workflows]);

  // ---- 导出 CSV ----
  const exportCSV = useCallback(() => {
    if (allTasks.length === 0) {
      message.warning("没有可导出的数据");
      return;
    }
    const header = "任务ID,工作流,状态,Token消耗,触发方式,创建时间\n";
    const rows = allTasks
      .map(
        (t) =>
          `${t.id},${workflows[t.workflow_id]?.name || ""},${t.status},${t.total_tokens_used},${t.trigger_type || "手动"},${t.created_at}`
      )
      .join("\n");
    const blob = new Blob(["﻿" + header + rows], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `tasks_export_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    message.success("导出成功");
  }, [allTasks, workflows]);

  // 一键导入示例工作流
  const importDemo = async () => {
    try {
      await workflowApi.importTemplate(0);
      message.success(locale === "zh" ? "导入成功！" : "Imported successfully!");
      loadData();
    } catch {
      message.error(locale === "zh" ? "导入失败" : "Import failed");
    }
  };

  return (
    <div>
      {/* 待审批提醒横幅 */}
      {pendingApprovals > 0 && (
        <Alert
          message={
            <span>
              <BellOutlined />{" "}
              {locale === "zh"
                ? `有 ${pendingApprovals} 个任务等待你的审批`
                : `${pendingApprovals} tasks waiting for your approval`}
            </span>
          }
          type="warning"
          showIcon={false}
          banner
          style={{ marginBottom: 16 }}
          action={
            <Button size="small" type="primary" onClick={() => router.push("/approvals")}>
              {locale === "zh" ? "去审批" : "Review Now"}
            </Button>
          }
        />
      )}

      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 24 }}>
        <Title level={3}>{t("dashboard.title")}</Title>
        <Space>
          <Button icon={<DownloadOutlined />} onClick={exportCSV}>
            {t("common.export")} CSV
          </Button>
          <Button icon={<ReloadOutlined />} onClick={handleRefresh}>
            {t("common.refresh")}
          </Button>
        </Space>
      </div>

      <Spin spinning={loading}>
        {/* 基础统计卡片 */}
        <DashboardStats stats={stats} />

        {/* 图表区域 */}
        <Row gutter={[16, 16]} style={{ marginTop: 24 }}>
          {/* 任务趋势折线图 */}
          <Col xs={24} lg={12}>
            <Card title={t("dashboard.task_trend")}>
              <Line
                data={trendData}
                xField="date"
                yField="count"
                point={{ size: 4 }}
                smooth
                height={260}
                yAxis={{ min: 0 }}
              />
            </Card>
          </Col>

          {/* 成功率饼图 */}
          <Col xs={24} lg={12}>
            <Card title={locale === "zh" ? "任务状态分布" : "Task Status"}>
              <Pie
                data={pieData}
                angleField="value"
                colorField="type"
                radius={0.85}
                innerRadius={0.55}
                height={260}
                label={{ text: "type", position: "outside" }}
                legend={{ position: "bottom" }}
                style={{ stroke: "#fff", lineWidth: 2 }}
                color={["#52c41a", "#ff4d4f", "#1677ff", "#d9d9d9"]}
              />
            </Card>
          </Col>

          {/* Token 消耗柱状图 */}
          <Col xs={24} lg={12}>
            <Card title={t("dashboard.token_usage")}>
              {tokenBarData.length === 0 ? (
                <div style={{ height: 260, display: "flex", alignItems: "center", justifyContent: "center", color: "#999" }}>
                  暂无数据
                </div>
              ) : (
                <Column
                  data={tokenBarData}
                  xField="workflow"
                  yField="tokens"
                  height={260}
                  color="#1677ff"
                  label={{ position: "top", formatter: (v: { tokens: number }) => v.tokens.toLocaleString() }}
                  xAxis={{ label: { autoRotate: true } }}
                />
              )}
            </Card>
          </Col>

          {/* 热门工作流 TOP 5 */}
          <Col xs={24} lg={12}>
            <Card title={t("dashboard.top_workflows")}>
              <Table
                dataSource={topWorkflows}
                rowKey="name"
                pagination={false}
                size="small"
                columns={[
                  {
                    title: "排名",
                    render: (_: unknown, __: unknown, index: number) => index + 1,
                    width: 60,
                  },
                  { title: "工作流名称", dataIndex: "name" },
                  {
                    title: "执行次数",
                    dataIndex: "count",
                    sorter: (a: { count: number }, b: { count: number }) => a.count - b.count,
                    defaultSortOrder: "descend" as const,
                  },
                ]}
              />
            </Card>
          </Col>
        </Row>

        {/* 最近任务 */}
        <Card
          title={t("dashboard.recent_tasks")}
          style={{ marginTop: 24 }}
          extra={
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => router.push("/tasks")}
            >
              {locale === "zh" ? "查看全部" : "View All"}
            </Button>
          }
        >
          {recentTasks.length === 0 && !loading ? (
            <Empty description={locale === "zh" ? "还没有执行过任务" : "No tasks yet"}>
              <Button
                type="primary"
                icon={<RocketOutlined />}
                onClick={() => router.push("/workflows")}
              >
                {locale === "zh" ? "去创建工作流" : "Create Workflow"}
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

      {/* 欢迎弹窗 - 首次访问 */}
      <Modal
        title={
          <span>
            <RocketOutlined />{" "}
            {locale === "zh" ? "欢迎使用 Agent Orchestrator" : "Welcome to Agent Orchestrator"}
          </span>
        }
        open={showWelcome}
        onCancel={() => setShowWelcome(false)}
        footer={null}
        width={640}
      >
        <div style={{ marginBottom: 16 }}>
          <Text>
            {locale === "zh"
              ? "AI Agent 工作流编排平台 — 让 AI 可靠、可控、可审计。"
              : "AI Agent workflow orchestration platform — make AI reliable, controllable, and auditable."}
          </Text>
        </div>

        <Title level={5}>{locale === "zh" ? "快速开始" : "Quick Start"}</Title>
        <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
          {USE_CASES.map((uc, i) => (
            <Col span={8} key={i}>
              <Card
                hoverable
                style={{ background: uc.color, textAlign: "center" }}
                onClick={() => {
                  setShowWelcome(false);
                  router.push("/workflows");
                }}
              >
                <div>{uc.icon}</div>
                <div style={{ fontWeight: 600, marginTop: 8 }}>
                  {locale === "zh" ? uc.title : uc.titleEn}
                </div>
                <div style={{ fontSize: 12, color: "#666", marginTop: 4 }}>
                  {locale === "zh" ? uc.desc : uc.descEn}
                </div>
                <Tag color="blue" style={{ marginTop: 8 }}>
                  {uc.time}
                </Tag>
              </Card>
            </Col>
          ))}
        </Row>

        <Space>
          <Button type="primary" icon={<ImportOutlined />} onClick={() => { setShowWelcome(false); importDemo(); }}>
            {locale === "zh" ? "一键导入示例工作流" : "Import Demo Workflow"}
          </Button>
          <Button icon={<PlusOutlined />} onClick={() => { setShowWelcome(false); router.push("/workflows/new"); }}>
            {locale === "zh" ? "创建第一个工作流" : "Create First Workflow"}
          </Button>
        </Space>
      </Modal>
    </div>
  );
}
