import React, { useEffect, useState, useCallback } from "react";
import {
  Typography, Card, Descriptions, Tag, Button, Space, message, Spin,
  Drawer, Divider, Modal, InputNumber, Popconfirm, Alert,
} from "antd";
import {
  ArrowLeftOutlined, RollbackOutlined, ReloadOutlined,
  PlayCircleOutlined,
} from "@ant-design/icons";
import { useRouter } from "next/router";
import { taskApi } from "@/lib/api";
import type { TaskItem, StepExecution } from "@/lib/api";
import TaskTimeline from "@/components/TaskTimeline";
import { connectWebSocket, disconnectWebSocket, onMessage } from "@/lib/ws";
import { statusColors } from "@/lib/constants";

const { Title, Text, Paragraph } = Typography;

export default function TaskDetailPage() {
  const router = useRouter();
  const { id } = router.query;
  const [task, setTask] = useState<TaskItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedStep, setSelectedStep] = useState<StepExecution | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [rollbackModalOpen, setRollbackModalOpen] = useState(false);
  const [rollbackStep, setRollbackStep] = useState(0);

  const load = useCallback(async () => {
    if (!id) return;
    try {
      const data = await taskApi.get(id as string);
      setTask(data);
    } catch (err) {
      message.error("加载失败");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (id) {
      connectWebSocket(id as string);
      const unsub = onMessage((data) => {
        if (data.type === "task_update" && data.task_id === id) {
          load();
        }
      });
      return () => {
        unsub();
        disconnectWebSocket();
      };
    }
  }, [id, load]);

  const handleRollback = async () => {
    if (!id) return;
    try {
      await taskApi.rollback(id as string, rollbackStep);
      message.success("已回滚");
      setRollbackModalOpen(false);
      load();
    } catch (err) {
      message.error((err as Error).message);
    }
  };

  const handleResume = async () => {
    if (!id) return;
    try {
      await taskApi.resume(id as string);
      message.success("已恢复执行");
      load();
    } catch (err) {
      message.error((err as Error).message);
    }
  };

  if (loading) return <Spin size="large" />;
  if (!task) return <Text>任务不存在</Text>;

  const isPaused = task.status === "paused";
  const canRollback = ["running", "paused", "failed", "completed"].includes(task.status);

  return (
    <div>
      <Button
        icon={<ArrowLeftOutlined />}
        onClick={() => router.push("/tasks")}
        style={{ marginBottom: 16 }}
      >
        返回列表
      </Button>

      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 24 }}>
        <Title level={3}>任务详情</Title>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={load}>
            刷新
          </Button>
          {isPaused && (
            <Button type="primary" icon={<PlayCircleOutlined />} onClick={handleResume}>
              恢复执行
            </Button>
          )}
          {canRollback && (
            <Button
              icon={<RollbackOutlined />}
              onClick={() => setRollbackModalOpen(true)}
            >
              回滚
            </Button>
          )}
        </Space>
      </div>

      {task.error_message && (
        <Alert
          message="执行错误"
          description={task.error_message}
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
        />
      )}

      <Card style={{ marginBottom: 24 }}>
        <Descriptions column={2}>
          <Descriptions.Item label="任务 ID">{task.id}</Descriptions.Item>
          <Descriptions.Item label="状态">
            <Tag color={statusColors[task.status]}>{task.status}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="工作流 ID">{task.workflow_id}</Descriptions.Item>
          <Descriptions.Item label="触发方式">{task.trigger_type || "手动"}</Descriptions.Item>
          <Descriptions.Item label="Git 仓库">{task.git_repo || "-"}</Descriptions.Item>
          <Descriptions.Item label="分支">{task.git_branch || "-"}</Descriptions.Item>
          <Descriptions.Item label="Token 消耗">
            {task.total_tokens_used.toLocaleString()}
          </Descriptions.Item>
          <Descriptions.Item label="当前步骤">
            {task.current_step_index + 1} / {task.step_executions.length}
          </Descriptions.Item>
          {task.pr_url && (
            <Descriptions.Item label="PR">
              <a href={task.pr_url} target="_blank" rel="noreferrer">
                {task.pr_url}
              </a>
            </Descriptions.Item>
          )}
          <Descriptions.Item label="创建时间">
            {new Date(task.created_at).toLocaleString("zh-CN")}
          </Descriptions.Item>
          {task.completed_at && (
            <Descriptions.Item label="完成时间">
              {new Date(task.completed_at).toLocaleString("zh-CN")}
            </Descriptions.Item>
          )}
        </Descriptions>
      </Card>

      <Card title="执行时间线">
        <TaskTimeline
          steps={task.step_executions}
          currentStepIndex={task.current_step_index}
          onStepClick={(step) => {
            setSelectedStep(step);
            setDrawerOpen(true);
          }}
        />
      </Card>

      <Drawer
        title={`步骤详情: ${selectedStep?.step_name}`}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        width={640}
      >
        {selectedStep && (
          <div>
            <Descriptions column={1} bordered size="small">
              <Descriptions.Item label="步骤名称">{selectedStep.step_name}</Descriptions.Item>
              <Descriptions.Item label="类型">{selectedStep.step_type}</Descriptions.Item>
              <Descriptions.Item label="状态">
                <Tag color={statusColors[selectedStep.status]}>{selectedStep.status}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="模型">{selectedStep.ai_model || "-"}</Descriptions.Item>
              <Descriptions.Item label="Token">
                {selectedStep.token_usage?.tokens?.toLocaleString() || "-"}
              </Descriptions.Item>
            </Descriptions>

            {selectedStep.output_data && (
              <>
                <Divider>输出</Divider>
                <pre style={{
                  background: "#f6f8fa",
                  padding: 16,
                  borderRadius: 8,
                  fontSize: 12,
                  overflow: "auto",
                  maxHeight: 400,
                }}>
                  {JSON.stringify(selectedStep.output_data, null, 2)}
                </pre>
              </>
            )}

            {selectedStep.error_message && (
              <>
                <Divider>错误信息</Divider>
                <Paragraph type="danger">{selectedStep.error_message}</Paragraph>
              </>
            )}
          </div>
        )}
      </Drawer>

      <Modal
        title="回滚到指定步骤"
        open={rollbackModalOpen}
        onOk={handleRollback}
        onCancel={() => setRollbackModalOpen(false)}
        okText="确认回滚"
        okButtonProps={{ danger: true }}
      >
        <Space direction="vertical" style={{ width: "100%" }}>
          <Text>选择要回滚到的步骤（从 0 开始）</Text>
          <InputNumber
            min={0}
            max={task.step_executions.length - 1}
            value={rollbackStep}
            onChange={(v) => setRollbackStep(v || 0)}
            style={{ width: "100%" }}
          />
          <Text type="secondary">
            将回滚到步骤 {rollbackStep}：
            {task.step_executions[rollbackStep]?.step_name}
          </Text>
        </Space>
      </Modal>
    </div>
  );
}
