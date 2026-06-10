import React from "react";
import { Card, Col, Row, Statistic, Tag, Tooltip } from "antd";
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  LoadingOutlined,
  ClockCircleOutlined,
  ThunderboltOutlined,
  AuditOutlined,
  DollarOutlined,
} from "@ant-design/icons";
import type { DashboardStatsData } from "@/lib/api";

interface Props {
  stats: DashboardStatsData | null;
  loading?: boolean;
}

// DeepSeek 定价估算 (每 1M tokens)
const COST_PER_MILLION_TOKENS = 0.14; // DeepSeek-chat 价格

export default function DashboardStats({ stats, loading }: Props) {
  if (!stats) return null;

  // 估算费用 (基于 DeepSeek 定价)
  const estimatedCost = (stats.total_tokens_used / 1_000_000) * COST_PER_MILLION_TOKENS;

  return (
    <Row gutter={[16, 16]}>
      <Col xs={24} sm={12} md={6}>
        <Card hoverable>
          <Statistic
            title="总任务数"
            value={stats.total_tasks}
            prefix={<ThunderboltOutlined />}
          />
        </Card>
      </Col>
      <Col xs={24} sm={12} md={6}>
        <Card hoverable>
          <Statistic
            title="成功率"
            value={stats.success_rate}
            suffix="%"
            prefix={<CheckCircleOutlined />}
            valueStyle={{ color: stats.success_rate >= 60 ? "#3f8600" : "#cf1322" }}
          />
        </Card>
      </Col>
      <Col xs={24} sm={12} md={6}>
        <Card hoverable>
          <Statistic
            title="运行中"
            value={stats.running_tasks}
            prefix={<LoadingOutlined />}
            valueStyle={{ color: "#1677ff" }}
          />
        </Card>
      </Col>
      <Col xs={24} sm={12} md={6}>
        <Card hoverable>
          <Statistic
            title="待审批"
            value={stats.pending_approvals}
            prefix={<AuditOutlined />}
            valueStyle={{ color: stats.pending_approvals > 0 ? "#faad14" : undefined }}
          />
        </Card>
      </Col>
      <Col xs={24} sm={12} md={6}>
        <Card hoverable>
          <Statistic
            title="已完成"
            value={stats.completed_tasks}
            prefix={<CheckCircleOutlined />}
            valueStyle={{ color: "#3f8600" }}
          />
        </Card>
      </Col>
      <Col xs={24} sm={12} md={6}>
        <Card hoverable>
          <Statistic
            title="失败"
            value={stats.failed_tasks}
            prefix={<CloseCircleOutlined />}
            valueStyle={{ color: "#cf1322" }}
          />
        </Card>
      </Col>
      <Col xs={24} sm={12} md={6}>
        <Card hoverable>
          <Statistic
            title="Token 消耗"
            value={stats.total_tokens_used}
            prefix={<ThunderboltOutlined />}
            groupSeparator=","
          />
        </Card>
      </Col>
      <Col xs={24} sm={12} md={6}>
        <Card hoverable>
          <Tooltip title="基于 DeepSeek 定价估算">
            <Statistic
              title="预估费用"
              value={estimatedCost}
              prefix={<DollarOutlined />}
              precision={2}
              valueStyle={{ color: "#722ed1" }}
            />
          </Tooltip>
        </Card>
      </Col>
    </Row>
  );
}
