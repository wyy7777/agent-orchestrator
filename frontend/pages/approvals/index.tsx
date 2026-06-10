import React, { useEffect, useState } from "react";
import { Typography, Card, Space, Tag, Button, message, Empty, Descriptions, Popconfirm, Row, Col } from "antd";
import { ReloadOutlined, CheckOutlined, CloseOutlined, ClockCircleOutlined } from "@ant-design/icons";
import { approvalApi } from "@/lib/api";
import type { ApprovalItem } from "@/lib/api";

const { Title, Text } = Typography;

export default function ApprovalsPage() {
  const [approvals, setApprovals] = useState<ApprovalItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [isMobile, setIsMobile] = useState(false);

  // 检测是否为移动设备
  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 768);
    };
    checkMobile();
    window.addEventListener("resize", checkMobile);
    return () => window.removeEventListener("resize", checkMobile);
  }, []);

  const load = async (signal?: AbortSignal) => {
    setLoading(true);
    try {
      const res = await approvalApi.list("pending", 0, 20, signal);
      if (signal?.aborted) return;
      setApprovals(res.items);
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
  }, []);

  const handleRefresh = () => {
    load();
  };

  const handleDecide = async (id: string, status: "approved" | "rejected") => {
    try {
      await approvalApi.decide(id, { status });
      message.success(status === "approved" ? "已批准" : "已拒绝");
      load();
    } catch (err) {
      message.error((err as Error).message);
    }
  };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 24 }}>
        <Title level={3}>待审批列表</Title>
        <Button icon={<ReloadOutlined />} onClick={handleRefresh}>
          刷新
        </Button>
      </div>

      {loading ? (
        <Card loading />
      ) : approvals.length === 0 ? (
        <Empty description="暂无待审批" />
      ) : (
        <Space direction="vertical" style={{ width: "100%" }} size="middle">
          {approvals.map((approval) => (
            <Card
              key={approval.id}
              size="small"
              title={
                <Space>
                  <Tag color="warning">待审批</Tag>
                  <Text>审批 ID: {approval.id.substring(0, 8)}...</Text>
                </Space>
              }
            >
              <Descriptions column={isMobile ? 1 : 2} size="small">
                <Descriptions.Item label="审批 ID">{approval.id}</Descriptions.Item>
                <Descriptions.Item label="步骤执行 ID">{approval.step_execution_id}</Descriptions.Item>
                <Descriptions.Item label="创建时间">
                  <ClockCircleOutlined /> {new Date(approval.created_at).toLocaleString("zh-CN")}
                </Descriptions.Item>
              </Descriptions>

              {/* 移动端大按钮 */}
              <Row gutter={12} style={{ marginTop: 16 }}>
                <Col span={12}>
                  <Popconfirm
                    title="确定批准吗？"
                    onConfirm={() => handleDecide(approval.id, "approved")}
                    okText="批准"
                    cancelText="取消"
                  >
                    <Button
                      type="primary"
                      icon={<CheckOutlined />}
                      block
                      size={isMobile ? "large" : "middle"}
                    >
                      批准
                    </Button>
                  </Popconfirm>
                </Col>
                <Col span={12}>
                  <Popconfirm
                    title="确定拒绝吗？"
                    onConfirm={() => handleDecide(approval.id, "rejected")}
                    okText="拒绝"
                    cancelText="取消"
                    okButtonProps={{ danger: true }}
                  >
                    <Button
                      danger
                      icon={<CloseOutlined />}
                      block
                      size={isMobile ? "large" : "middle"}
                    >
                      拒绝
                    </Button>
                  </Popconfirm>
                </Col>
              </Row>
            </Card>
          ))}
        </Space>
      )}
    </div>
  );
}
