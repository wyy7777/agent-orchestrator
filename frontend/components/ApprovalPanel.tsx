import React from "react";
import { Card, Button, Space, Tag, Descriptions, message, Popconfirm } from "antd";
import { CheckOutlined, CloseOutlined, UndoOutlined } from "@ant-design/icons";
import type { ApprovalItem, StepExecution, TaskItem } from "@/lib/api";
import { approvalApi } from "@/lib/api";

interface Props {
  approval: ApprovalItem;
  stepExecution?: StepExecution;
  task?: TaskItem;
  onDecided?: () => void;
}

export default function ApprovalCard({ approval, stepExecution, task, onDecided }: Props) {
  const handleDecide = async (status: "approved" | "rejected") => {
    try {
      await approvalApi.decide(approval.id, { status });
      message.success(status === "approved" ? "已批准" : "已拒绝");
      onDecided?.();
    } catch (err: unknown) {
      message.error((err as Error).message);
    }
  };

  const handleRevoke = async () => {
    try {
      await approvalApi.revoke(approval.id, "管理员撤销");
      message.success("审批已撤销，任务已恢复为待处理");
      onDecided?.();
    } catch (err: unknown) {
      message.error((err as Error).message);
    }
  };

  const isPending = approval.status === "pending";
  const isRevoked = !!approval.revoked_at;
  const isDecided = !isPending && !isRevoked;

  const statusColor = isPending
    ? "warning"
    : approval.status === "approved"
    ? "success"
    : approval.status === "revoked"
    ? "default"
    : "error";

  const statusLabel = isPending
    ? "待处理"
    : approval.status === "approved"
    ? "已批准"
    : approval.status === "revoked"
    ? "已撤销"
    : "已拒绝";

  return (
    <Card
      size="small"
      title={
        <Space>
          <span>审批请求</span>
          <Tag color={statusColor}>{statusLabel}</Tag>
        </Space>
      }
      extra={
        <Space>
          {isPending && (
            <>
              <Popconfirm
                title="确认批准？"
                onConfirm={() => handleDecide("approved")}
                okText="批准"
                cancelText="取消"
              >
                <Button type="primary" icon={<CheckOutlined />} size="small">
                  批准
                </Button>
              </Popconfirm>
              <Popconfirm
                title="确认拒绝？"
                onConfirm={() => handleDecide("rejected")}
                okText="拒绝"
                cancelText="取消"
                okButtonProps={{ danger: true }}
              >
                <Button danger icon={<CloseOutlined />} size="small">
                  拒绝
                </Button>
              </Popconfirm>
            </>
          )}
          {isDecided && (
            <Popconfirm
              title="确认撤销此审批？任务将恢复为待处理状态。"
              onConfirm={handleRevoke}
              okText="撤销"
              cancelText="取消"
              okButtonProps={{ danger: true }}
            >
              <Button icon={<UndoOutlined />} size="small">
                撤销
              </Button>
            </Popconfirm>
          )}
        </Space>
      }
    >
      <Descriptions column={1} size="small">
        <Descriptions.Item label="审批 ID">{approval.id}</Descriptions.Item>
        {stepExecution && (
          <>
            <Descriptions.Item label="步骤名称">{stepExecution.step_name}</Descriptions.Item>
            <Descriptions.Item label="步骤类型">{stepExecution.step_type}</Descriptions.Item>
          </>
        )}
        {task && (
          <Descriptions.Item label="关联任务">{task.id.substring(0, 8)}...</Descriptions.Item>
        )}
        {approval.approver && (
          <Descriptions.Item label="审批人">{approval.approver}</Descriptions.Item>
        )}
        {approval.comment && (
          <Descriptions.Item label="备注">{approval.comment}</Descriptions.Item>
        )}
        {isRevoked && (
          <Descriptions.Item label="撤销原因">{approval.revoke_reason}</Descriptions.Item>
        )}
        <Descriptions.Item label="创建时间">
          {new Date(approval.created_at).toLocaleString("zh-CN")}
        </Descriptions.Item>
      </Descriptions>
    </Card>
  );
}
