import React, { useEffect, useState } from "react";
import {
  Typography, Table, Button, Space, Tag, message, Popconfirm, Card, Empty, Row, Col, Spin,
} from "antd";
import {
  PlusOutlined, DeleteOutlined, EditOutlined, PlayCircleOutlined, ImportOutlined,
} from "@ant-design/icons";
import { useRouter } from "next/router";
import { workflowApi } from "@/lib/api";
import type { WorkflowItem } from "@/lib/api";

const { Title, Text, Paragraph } = Typography;

export default function WorkflowListPage() {
  const [workflows, setWorkflows] = useState<WorkflowItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [templates, setTemplates] = useState<Array<{ name: string; description: string; index: number }>>([]);
  const [importing, setImporting] = useState<number | null>(null);
  const router = useRouter();

  const load = async (p = page) => {
    setLoading(true);
    try {
      const res = await workflowApi.list((p - 1) * 10, 10);
      setWorkflows(res.items);
      setTotal(res.total);

      if (res.total === 0) {
        const tpl = await workflowApi.templates();
        setTemplates(tpl.map((t, i) => ({ ...t, index: i })));
      }
    } catch (err) {
      message.error("加载失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load(1);
  }, []);

  const handleImport = async (index: number) => {
    setImporting(index);
    try {
      await workflowApi.importTemplate(index);
      message.success("模板导入成功");
      load(1);
    } catch (err) {
      message.error((err as Error).message);
    } finally {
      setImporting(null);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await workflowApi.delete(id);
      message.success("已删除");
      load();
    } catch (err) {
      message.error((err as Error).message);
    }
  };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 24 }}>
        <Title level={3}>工作流管理</Title>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => router.push("/workflows/new")}
        >
          新建工作流
        </Button>
      </div>

      {workflows.length === 0 && !loading && templates.length > 0 ? (
        <div>
          <Card style={{ marginBottom: 24, textAlign: "center" }}>
            <Empty
              description={
                <div>
                  <Title level={4}>还没有工作流</Title>
                  <Paragraph type="secondary">
                    选择一个模板快速开始，或自己创建一个工作流
                  </Paragraph>
                </div>
              }
            >
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={() => router.push("/workflows/new")}
                style={{ marginRight: 16 }}
              >
                自己创建
              </Button>
            </Empty>
          </Card>

          <Title level={4}>快速开始 - 选择模板</Title>
          <Row gutter={16} style={{ marginTop: 16 }}>
            {templates.map((tpl) => (
              <Col span={8} key={tpl.index}>
                <Card
                  hoverable
                  actions={[
                    <Button
                      key="import"
                      type="link"
                      icon={<ImportOutlined />}
                      loading={importing === tpl.index}
                      onClick={() => handleImport(tpl.index)}
                    >
                      一键导入
                    </Button>,
                  ]}
                >
                  <Card.Meta
                    title={tpl.name}
                    description={tpl.description}
                  />
                </Card>
              </Col>
            ))}
          </Row>
        </div>
      ) : (
        <Table
          dataSource={workflows}
          rowKey="id"
          loading={loading}
          pagination={{
            current: page,
            total,
            pageSize: 10,
            onChange: (p) => { setPage(p); load(p); },
          }}
          columns={[
            {
              title: "名称",
              dataIndex: "name",
              render: (name: string, record: WorkflowItem) => (
                <Button
                  type="link"
                  onClick={() => router.push(`/workflows/detail?id=${record.id}`)}
                >
                  {name}
                </Button>
              ),
            },
            {
              title: "描述",
              dataIndex: "description",
              ellipsis: true,
              render: (v: string | null) => v || "-",
            },
            {
              title: "版本",
              dataIndex: "version",
              width: 80,
              render: (v: number) => <Tag>v{v}</Tag>,
            },
            {
              title: "更新时间",
              dataIndex: "updated_at",
              render: (v: string) => new Date(v).toLocaleString("zh-CN"),
            },
            {
              title: "操作",
              width: 200,
              render: (_: unknown, record: WorkflowItem) => (
                <Space>
                  <Button
                    size="small"
                    icon={<EditOutlined />}
                    onClick={() => router.push(`/workflows/detail?id=${record.id}`)}
                  >
                    编辑
                  </Button>
                  <Popconfirm
                    title="确定删除此工作流吗？"
                    onConfirm={() => handleDelete(record.id)}
                  >
                    <Button size="small" danger icon={<DeleteOutlined />}>
                      删除
                    </Button>
                  </Popconfirm>
                </Space>
              ),
            },
          ]}
        />
      )}
    </div>
  );
}

