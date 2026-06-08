import React from "react";
import { Card, Button, Space, Tag, Descriptions, message, Popconfirm } from "antd";
import { CheckOutlined, CloseOutlined } from "@ant-design/icons";
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

  return (
    <Card
      size="small"
      title={
        <Space>
          <span>审批请求</span>
          <Tag color="warning">待处理</Tag>
        </Space>
      }
      extra={
        <Space>
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
        <Descriptions.Item label="创建时间">
          {new Date(approval.created_at).toLocaleString("zh-CN")}
        </Descriptions.Item>
      </Descriptions>
    </Card>
  );
}
