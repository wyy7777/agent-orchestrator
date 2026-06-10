import React from "react";
import { Steps, Tag, Typography, Descriptions, Timeline } from "antd";
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  LoadingOutlined,
  ClockCircleOutlined,
  PauseCircleOutlined,
  StopOutlined,
} from "@ant-design/icons";
import type { StepExecution } from "@/lib/api";

const { Text, Paragraph } = Typography;

const statusConfig: Record<string, { color: string; icon: React.ReactNode; label: string }> = {
  pending: { color: "default", icon: <ClockCircleOutlined />, label: "等待中" },
  running: { color: "processing", icon: <LoadingOutlined />, label: "执行中" },
  waiting_approval: { color: "warning", icon: <PauseCircleOutlined />, label: "待审批" },
  completed: { color: "success", icon: <CheckCircleOutlined />, label: "已完成" },
  failed: { color: "error", icon: <CloseCircleOutlined />, label: "失败" },
  skipped: { color: "default", icon: <StopOutlined />, label: "已跳过" },
};

const typeLabels: Record<string, string> = {
  analyze: "分析",
  execute: "执行",
  review: "审查",
  approval: "审批",
  merge: "合并",
  script: "脚本",
  condition: "条件",
  loop: "循环",
  subtask: "子任务",
};

interface Props {
  steps: StepExecution[];
  currentStepIndex?: number;
  onStepClick?: (step: StepExecution) => void;
}

export default function TaskTimeline({ steps, currentStepIndex, onStepClick }: Props) {
  if (!steps || steps.length === 0) {
    return <Text type="secondary">暂无步骤执行记录</Text>;
  }

  const sortedSteps = [...steps].sort((a, b) => a.step_index - b.step_index);

  return (
    <Timeline
      items={sortedSteps.map((step) => {
        const cfg = statusConfig[step.status] || statusConfig.pending;
        const isActive = step.step_index === currentStepIndex;

        return {
          key: step.id,
          color: cfg.color === "success" ? "green" : cfg.color === "error" ? "red" : cfg.color === "warning" ? "orange" : cfg.color === "processing" ? "blue" : "gray",
          dot: isActive ? <LoadingOutlined spin style={{ fontSize: 16 }} /> : undefined,
          children: (
            <div
              style={{
                cursor: onStepClick ? "pointer" : undefined,
                padding: "8px 12px",
                borderRadius: 8,
                border: isActive ? "1px solid #1677ff" : "1px solid transparent",
                background: isActive ? "#f0f5ff" : "transparent",
              }}
              onClick={() => onStepClick?.(step)}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                {cfg.icon}
                <Text strong>{step.step_name}</Text>
                <Tag color="blue">{typeLabels[step.step_type] || step.step_type}</Tag>
                <Tag color={cfg.color}>{cfg.label}</Tag>
              </div>

              {step.started_at && (
                <Text type="secondary" style={{ fontSize: 12 }}>
                  开始: {new Date(step.started_at).toLocaleString("zh-CN")}
                  {step.completed_at &&
                    ` → 完成: ${new Date(step.completed_at).toLocaleString("zh-CN")}`}
                </Text>
              )}

              {step.token_usage?.tokens && (
                <Text type="secondary" style={{ fontSize: 12, marginLeft: 16 }}>
                  Tokens: {step.token_usage.tokens.toLocaleString()}
                </Text>
              )}

              {step.error_message && (
                <Paragraph
                  type="danger"
                  style={{ marginTop: 4, fontSize: 12 }}
                  ellipsis={{ rows: 2, expandable: true }}
                >
                  {step.error_message}
                </Paragraph>
              )}

              {step.output_data && (
                <Paragraph
                  type="secondary"
                  style={{ marginTop: 4, fontSize: 12 }}
                  ellipsis={{ rows: 3, expandable: true, symbol: "展开" }}
                  code
                >
                  {JSON.stringify(step.output_data, null, 2).substring(0, 500)}
                </Paragraph>
              )}
            </div>
          ),
        };
      })}
    />
  );
}
