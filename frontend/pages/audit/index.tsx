import React, { useEffect, useState } from "react";
import {
  Typography, Card, Table, Button, DatePicker, Select, Space, message, Tag, Tooltip, Empty,
} from "antd";
import {
  DownloadOutlined, FileTextOutlined, ReloadOutlined, SafetyCertificateOutlined,
} from "@ant-design/icons";
import { auditApi } from "@/lib/api";
import type { AuditReportItem } from "@/lib/api";

const { Title, Text } = Typography;
const { RangePicker } = DatePicker;

export default function AuditPage() {
  const [reports, setReports] = useState<AuditReportItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [dateRange, setDateRange] = useState<[any, any] | null>(null);
  const [format, setFormat] = useState("csv");

  const load = async (signal?: AbortSignal) => {
    setLoading(true);
    try {
      const res = await auditApi.listReports(signal);
      if (signal?.aborted) return;
      setReports(res.items);
    } catch (err) {
      if (!signal?.aborted) message.error("加载报告列表失败");
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  };

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, []);

  const handleGenerate = async () => {
    if (!dateRange || !dateRange[0] || !dateRange[1]) {
      message.warning("请选择日期范围");
      return;
    }
    setGenerating(true);
    try {
      const startDate = dateRange[0].format("YYYY-MM-DD");
      const endDate = dateRange[1].format("YYYY-MM-DD");
      const result = await auditApi.generateReport(startDate, endDate, format);
      message.success(`报告已下载 (SHA-256: ${result.sha256.substring(0, 12)}...)`);
      load();
    } catch (err) {
      message.error((err as Error).message);
    } finally {
      setGenerating(false);
    }
  };

  const columns = [
    {
      title: "生成时间",
      dataIndex: "created_at",
      key: "created_at",
      render: (v: string) => v ? new Date(v).toLocaleString("zh-CN") : "-",
    },
    {
      title: "日期范围",
      key: "range",
      render: (_: any, r: AuditReportItem) => (
        <Text>
          {r.start_date ? new Date(r.start_date).toLocaleDateString("zh-CN") : "-"}
          {" ~ "}
          {r.end_date ? new Date(r.end_date).toLocaleDateString("zh-CN") : "-"}
        </Text>
      ),
    },
    {
      title: "格式",
      dataIndex: "format",
      key: "format",
      render: (v: string) => <Tag>{v.toUpperCase()}</Tag>,
    },
    {
      title: "大小",
      dataIndex: "size_bytes",
      key: "size_bytes",
      render: (v: number) => v ? `${(v / 1024).toFixed(1)} KB` : "-",
    },
    {
      title: "SHA-256",
      dataIndex: "sha256",
      key: "sha256",
      render: (v: string) => (
        <Tooltip title={v}>
          <Text code copyable={{ text: v }}>
            {v ? `${v.substring(0, 16)}...` : "-"}
          </Text>
        </Tooltip>
      ),
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <Title level={3}>
        <SafetyCertificateOutlined style={{ marginRight: 8 }} />
        审计报告
      </Title>
      <Text type="secondary" style={{ display: "block", marginBottom: 24 }}>
        生成合规审计报告（EU AI Act），含 SHA-256 防篡改签名。支持 CSV 和详细 CSV（步骤级）格式。
      </Text>

      <Card style={{ marginBottom: 24 }}>
        <Space wrap size="middle">
          <RangePicker
            value={dateRange}
            onChange={(dates) => setDateRange(dates)}
            placeholder={["起始日期", "截止日期"]}
          />
          <Select value={format} onChange={setFormat} style={{ width: 160 }}>
            <Select.Option value="csv">任务摘要 (CSV)</Select.Option>
            <Select.Option value="detailed_csv">步骤详情 (Detailed CSV)</Select.Option>
          </Select>
          <Button
            type="primary"
            icon={<DownloadOutlined />}
            loading={generating}
            onClick={handleGenerate}
          >
            生成并下载
          </Button>
          <Button icon={<ReloadOutlined />} onClick={() => load()}>
            刷新列表
          </Button>
        </Space>
      </Card>

      <Card title={<><FileTextOutlined /> 历史报告</>}>
        <Table
          dataSource={reports}
          columns={columns}
          rowKey="id"
          loading={loading}
          pagination={false}
          locale={{ emptyText: <Empty description="暂无报告，选择日期范围并点击"生成并下载"" /> }}
        />
      </Card>
    </div>
  );
}
