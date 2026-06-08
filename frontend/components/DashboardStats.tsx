import React from "react";
import { Card, Col, Row, Statistic, Tag } from "antd";
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  LoadingOutlined,
  ClockCircleOutlined,
  ThunderboltOutlined,
  AuditOutlined,
} from "@ant-design/icons";
import type { DashboardStatsData } from "@/lib/api";

interface Props {
  stats: DashboardStatsData | null;
  loading?: boolean;
}

export default function DashboardStats({ stats, loading }: Props) {
  if (!stats) return null;

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
          <Statistic
            title="审批通过率"
            value={stats.avg_approval_pass_rate}
            suffix="%"
            prefix={<AuditOutlined />}
          />
        </Card>
      </Col>
    </Row>
  );
}
