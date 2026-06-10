import React, { useEffect, useState } from "react";
import { Typography, Card, Space, Tag, Button, message, Empty, Descriptions, Popconfirm } from "antd";
import { ReloadOutlined, CheckOutlined, CloseOutlined } from "@ant-design/icons";
import { approvalApi } from "@/lib/api";
import type { ApprovalItem } from "@/lib/api";

const { Title, Text } = Typography;

export default function ApprovalsPage() {
  const [approvals, setApprovals] = useState<ApprovalItem[]>([]);
  const [loading, setLoading] = useState(false);

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
              extra={
                <Space>
                  <Popconfirm
                    title="确定批准吗？"
                    onConfirm={() => handleDecide(approval.id, "approved")}
                    okText="批准"
                    cancelText="取消"
                  >
                    <Button type="primary" icon={<CheckOutlined />} size="small">
                      批准
                    </Button>
                  </Popconfirm>
                  <Popconfirm
                    title="确定拒绝吗？"
                    onConfirm={() => handleDecide(approval.id, "rejected")}
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
              <Descriptions column={2} size="small">
                <Descriptions.Item label="审批 ID">{approval.id}</Descriptions.Item>
                <Descriptions.Item label="步骤执行 ID">{approval.step_execution_id}</Descriptions.Item>
                <Descriptions.Item label="创建时间">
                  {new Date(approval.created_at).toLocaleString("zh-CN")}
                </Descriptions.Item>
              </Descriptions>
            </Card>
          ))}
        </Space>
      )}
    </div>
  );
}
