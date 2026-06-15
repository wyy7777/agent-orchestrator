import React, { useEffect, useState, useCallback } from "react";
import { Typography, Card, Space, Tag, Button, message, Empty, Descriptions, Popconfirm, Row, Col, Checkbox, Tooltip, Tabs } from "antd";
import { ReloadOutlined, CheckOutlined, CloseOutlined, ClockCircleOutlined, ThunderboltOutlined, UndoOutlined } from "@ant-design/icons";
import { approvalApi } from "@/lib/api";
import type { ApprovalItem } from "@/lib/api";

const { Title, Text } = Typography;

export default function ApprovalsPage() {
  const [approvals, setApprovals] = useState<ApprovalItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [activeTab, setActiveTab] = useState("pending");

  useEffect(() => {
    const checkMobile = () => setIsMobile(window.innerWidth < 768);
    checkMobile();
    window.addEventListener("resize", checkMobile);
    return () => window.removeEventListener("resize", checkMobile);
  }, []);

  const load = async (status = activeTab, signal?: AbortSignal) => {
    setLoading(true);
    try {
      const res = await approvalApi.list(status, 0, 50, signal);
      if (signal?.aborted) return;
      setApprovals(res.items);
      setSelectedIds([]);
    } catch (err) {
      if (!signal?.aborted) message.error("加载失败");
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  };

  useEffect(() => {
    const controller = new AbortController();
    load(activeTab, controller.signal);
    return () => controller.abort();
  }, [activeTab]);

  const handleRefresh = () => load(activeTab);

  const handleDecide = async (id: string, status: "approved" | "rejected") => {
    try {
      await approvalApi.decide(id, { status });
      message.success(status === "approved" ? "已批准" : "已拒绝");
      load(activeTab);
    } catch (err) {
      message.error((err as Error).message);
    }
  };

  const handleRevoke = async (id: string) => {
    try {
      await approvalApi.revoke(id, "管理员撤销");
      message.success("审批已撤销，任务已恢复");
      load(activeTab);
    } catch (err) {
      message.error((err as Error).message);
    }
  };

  const handleBatchApprove = async () => {
    if (selectedIds.length === 0) {
      message.warning("请先选择要审批的项目");
      return;
    }
    try {
      await Promise.all(selectedIds.map((id) => approvalApi.decide(id, { status: "approved" })));
      message.success(`已批量批准 ${selectedIds.length} 个项目`);
      load(activeTab);
    } catch {
      message.error("批量审批失败");
    }
  };

  const handleSelectAll = (checked: boolean) => {
    setSelectedIds(checked ? approvals.map((a) => a.id) : []);
  };

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.key === "a" && !e.shiftKey) {
        e.preventDefault();
        handleSelectAll(true);
      }
      if (e.ctrlKey && e.key === "Enter") {
        e.preventDefault();
        if (selectedIds.length > 0) handleBatchApprove();
      }
      if (e.key === "r" && !e.ctrlKey && !e.metaKey) {
        const target = e.target as HTMLElement;
        if (target.tagName !== "INPUT" && target.tagName !== "TEXTAREA") handleRefresh();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [selectedIds, approvals, activeTab]);

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]);
  };

  const getStatusTag = (a: ApprovalItem) => {
    if (a.revoked_at) return <Tag color="default">已撤销</Tag>;
    if (a.status === "approved") return <Tag color="success">已批准</Tag>;
    if (a.status === "rejected") return <Tag color="error">已拒绝</Tag>;
    return <Tag color="warning">待审批</Tag>;
  };

  const isPendingTab = activeTab === "pending";

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 24 }}>
        <Title level={3}>审批管理</Title>
        <Space>
          {isPendingTab && selectedIds.length > 0 && (
            <Tooltip title="Ctrl+Enter 批量批准">
              <Button type="primary" icon={<ThunderboltOutlined />} onClick={handleBatchApprove}>
                批量批准 ({selectedIds.length})
              </Button>
            </Tooltip>
          )}
          <Button icon={<ReloadOutlined />} onClick={handleRefresh}>刷新</Button>
        </Space>
      </div>

      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          { key: "pending", label: "待审批" },
          { key: "approved", label: "已批准" },
          { key: "rejected", label: "已拒绝" },
          { key: "revoked", label: "已撤销" },
        ]}
      />

      {loading ? (
        <Card loading />
      ) : approvals.length === 0 ? (
        <Empty description={isPendingTab ? "暂无待审批" : "暂无记录"} />
      ) : (
        <>
          {isPendingTab && (
            <Card size="small" style={{ marginBottom: 12 }}>
              <Checkbox
                checked={selectedIds.length === approvals.length}
                indeterminate={selectedIds.length > 0 && selectedIds.length < approvals.length}
                onChange={(e) => handleSelectAll(e.target.checked)}
              >
                全选 ({approvals.length} 项)
              </Checkbox>
              <Text type="secondary" style={{ marginLeft: 16 }}>
                快捷键: Ctrl+A 全选 | Ctrl+Enter 批量批准 | R 刷新
              </Text>
            </Card>
          )}

          <Space direction="vertical" style={{ width: "100%", marginTop: 12 }} size="middle">
            {approvals.map((approval) => (
              <Card
                key={approval.id}
                size="small"
                style={{
                  border: selectedIds.includes(approval.id) ? "1px solid #1677ff" : undefined,
                }}
                title={
                  <Space>
                    {isPendingTab && (
                      <Checkbox
                        checked={selectedIds.includes(approval.id)}
                        onChange={() => toggleSelect(approval.id)}
                      />
                    )}
                    {getStatusTag(approval)}
                    <Text>审批 ID: {approval.id.substring(0, 8)}...</Text>
                  </Space>
                }
              >
                <Descriptions column={isMobile ? 1 : 2} size="small">
                  <Descriptions.Item label="审批 ID">{approval.id}</Descriptions.Item>
                  <Descriptions.Item label="步骤执行 ID">{approval.step_execution_id}</Descriptions.Item>
                  {approval.approver && (
                    <Descriptions.Item label="审批人">{approval.approver}</Descriptions.Item>
                  )}
                  {approval.comment && (
                    <Descriptions.Item label="备注">{approval.comment}</Descriptions.Item>
                  )}
                  {approval.revoked_at && (
                    <Descriptions.Item label="撤销原因">{approval.revoke_reason || "-"}</Descriptions.Item>
                  )}
                  <Descriptions.Item label="创建时间">
                    <ClockCircleOutlined /> {new Date(approval.created_at).toLocaleString("zh-CN")}
                  </Descriptions.Item>
                </Descriptions>

                {/* 操作按钮 */}
                <Row gutter={12} style={{ marginTop: 16 }}>
                  {isPendingTab ? (
                    <>
                      <Col span={12}>
                        <Popconfirm
                          title="确定批准吗？"
                          onConfirm={() => handleDecide(approval.id, "approved")}
                          okText="批准"
                          cancelText="取消"
                        >
                          <Button type="primary" icon={<CheckOutlined />} block size={isMobile ? "large" : "middle"}>
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
                          <Button danger icon={<CloseOutlined />} block size={isMobile ? "large" : "middle"}>
                            拒绝
                          </Button>
                        </Popconfirm>
                      </Col>
                    </>
                  ) : !approval.revoked_at && activeTab !== "revoked" ? (
                    <Col span={24}>
                      <Popconfirm
                        title="确认撤销此审批？任务将恢复为待处理状态。"
                        onConfirm={() => handleRevoke(approval.id)}
                        okText="撤销"
                        cancelText="取消"
                        okButtonProps={{ danger: true }}
                      >
                        <Button icon={<UndoOutlined />} block size={isMobile ? "large" : "middle"}>
                          撤销审批
                        </Button>
                      </Popconfirm>
                    </Col>
                  ) : null}
                </Row>
              </Card>
            ))}
          </Space>
        </>
      )}
    </div>
  );
}
