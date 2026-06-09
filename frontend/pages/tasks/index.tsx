import React, { useEffect, useState, useCallback, useRef } from "react";
import {
  Typography,
  Table,
  Tag,
  Button,
  message,
  Space,
  Select,
  Empty,
  Input,
  DatePicker,
  Card,
  Pagination,
} from "antd";
import {
  ReloadOutlined,
  RocketOutlined,
  SearchOutlined,
  SortAscendingOutlined,
  SortDescendingOutlined,
} from "@ant-design/icons";
import { useRouter } from "next/router";
import { taskApi, workflowApi } from "@/lib/api";
import type { TaskItem, WorkflowItem } from "@/lib/api";
import { statusColors } from "@/lib/constants";
import dayjs from "dayjs";

const { Title } = Typography;
const { RangePicker } = DatePicker;

const STATUS_OPTIONS = [
  { label: "全部", value: "" },
  { label: "等待中", value: "pending" },
  { label: "运行中", value: "running" },
  { label: "暂停", value: "paused" },
  { label: "已完成", value: "completed" },
  { label: "失败", value: "failed" },
];

const SORT_OPTIONS = [
  { label: "创建时间", value: "created_at" },
  { label: "开始时间", value: "started_at" },
  { label: "完成时间", value: "completed_at" },
  { label: "Token 消耗", value: "tokens_used" },
];

interface SearchParams {
  q: string;
  status: string;
  date_from: string;
  date_to: string;
  sort_by: string;
  sort_order: string;
  page: number;
  page_size: number;
}

const DEFAULT_PARAMS: SearchParams = {
  q: "",
  status: "",
  date_from: "",
  date_to: "",
  sort_by: "created_at",
  sort_order: "desc",
  page: 1,
  page_size: 10,
};

function paramsToQuery(params: SearchParams): Record<string, string> {
  const query: Record<string, string> = {};
  if (params.q) query.q = params.q;
  if (params.status) query.status = params.status;
  if (params.date_from) query.date_from = params.date_from;
  if (params.date_to) query.date_to = params.date_to;
  if (params.sort_by !== DEFAULT_PARAMS.sort_by) query.sort_by = params.sort_by;
  if (params.sort_order !== DEFAULT_PARAMS.sort_order) query.sort_order = params.sort_order;
  if (params.page !== 1) query.page = String(params.page);
  if (params.page_size !== 10) query.page_size = String(params.page_size);
  return query;
}

function queryToParams(query: Record<string, string | string[] | undefined>): SearchParams {
  return {
    q: typeof query.q === "string" ? query.q : DEFAULT_PARAMS.q,
    status: typeof query.status === "string" ? query.status : DEFAULT_PARAMS.status,
    date_from: typeof query.date_from === "string" ? query.date_from : DEFAULT_PARAMS.date_from,
    date_to: typeof query.date_to === "string" ? query.date_to : DEFAULT_PARAMS.date_to,
    sort_by: typeof query.sort_by === "string" ? query.sort_by : DEFAULT_PARAMS.sort_by,
    sort_order: typeof query.sort_order === "string" ? query.sort_order : DEFAULT_PARAMS.sort_order,
    page: typeof query.page === "string" ? Number(query.page) || 1 : DEFAULT_PARAMS.page,
    page_size: typeof query.page_size === "string" ? Number(query.page_size) || 10 : DEFAULT_PARAMS.page_size,
  };
}

export default function TaskListPage() {
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [workflows, setWorkflows] = useState<Record<string, WorkflowItem>>({});
  const [params, setParams] = useState<SearchParams>(DEFAULT_PARAMS);
  const router = useRouter();
  const initializedRef = useRef(false);

  // 表单临时状态（输入中未提交）
  const [searchInput, setSearchInput] = useState("");
  const [statusInput, setStatusInput] = useState("");
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs | null, dayjs.Dayjs | null]>([null, null]);

  // 从 URL query 初始化状态
  useEffect(() => {
    if (!router.isReady) return;
    const parsed = queryToParams(router.query);
    setParams(parsed);
    setSearchInput(parsed.q);
    setStatusInput(parsed.status);
    setDateRange([
      parsed.date_from ? dayjs(parsed.date_from) : null,
      parsed.date_to ? dayjs(parsed.date_to) : null,
    ]);
    initializedRef.current = true;
  }, [router.isReady, router.query]);

  // 监听浏览器前进后退（popstate）
  useEffect(() => {
    const handleRouteChange = (url: string) => {
      const urlObj = new URL(url, window.location.origin);
      const parsed = queryToParams(Object.fromEntries(urlObj.searchParams.entries()));
      setParams(parsed);
      setSearchInput(parsed.q);
      setStatusInput(parsed.status);
      setDateRange([
        parsed.date_from ? dayjs(parsed.date_from) : null,
        parsed.date_to ? dayjs(parsed.date_to) : null,
      ]);
    };
    router.events.on("routeChangeComplete", handleRouteChange);
    return () => router.events.off("routeChangeComplete", handleRouteChange);
  }, [router.events]);

  // 加载工作流列表（一次性）
  useEffect(() => {
    workflowApi.list(0, 100).then((wfRes) => {
      const wfMap: Record<string, WorkflowItem> = {};
      wfRes.items.forEach((w) => (wfMap[w.id] = w));
      setWorkflows(wfMap);
    });
  }, []);

  const load = useCallback(async (p: SearchParams) => {
    setLoading(true);
    try {
      const res = await taskApi.list({
        q: p.q || undefined,
        status: p.status || undefined,
        date_from: p.date_from || undefined,
        date_to: p.date_to || undefined,
        sort_by: p.sort_by,
        sort_order: p.sort_order,
        page: p.page,
        page_size: p.page_size,
      });
      setTasks(res.items);
      setTotal(res.total);
    } catch {
      message.error("加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  // params 变化时请求数据
  useEffect(() => {
    if (!initializedRef.current) return;
    load(params);
  }, [params, load]);

  // 同步 params 到 URL query
  const pushParams = useCallback(
    (next: SearchParams) => {
      setParams(next);
      router.push({ pathname: "/tasks", query: paramsToQuery(next) }, undefined, { shallow: true });
    },
    [router],
  );

  // 执行搜索
  const handleSearch = () => {
    pushParams({
      ...params,
      q: searchInput,
      status: statusInput,
      date_from: dateRange[0] ? dateRange[0].format("YYYY-MM-DD") : "",
      date_to: dateRange[1] ? dateRange[1].format("YYYY-MM-DD") : "",
      page: 1,
    });
  };

  // 重置搜索
  const handleReset = () => {
    setSearchInput("");
    setStatusInput("");
    setDateRange([null, null]);
    pushParams(DEFAULT_PARAMS);
  };

  // 排序字段切换
  const handleSortByChange = (value: string) => {
    pushParams({ ...params, sort_by: value, page: 1 });
  };

  // 排序方向切换
  const toggleSortOrder = () => {
    pushParams({ ...params, sort_order: params.sort_order === "asc" ? "desc" : "asc", page: 1 });
  };

  // 分页
  const handlePageChange = (page: number, pageSize: number) => {
    pushParams({ ...params, page, page_size: pageSize });
  };

  return (
    <div>
      <Title level={3} style={{ marginBottom: 16 }}>
        任务列表
      </Title>

      {/* 搜索栏 */}
      <Card size="small" style={{ marginBottom: 16 }}>
        <Space wrap size="middle" style={{ width: "100%" }}>
          <Input
            placeholder="搜索任务ID / 工作流名称 / 错误信息"
            prefix={<SearchOutlined />}
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            onPressEnter={handleSearch}
            style={{ width: 300 }}
            allowClear
          />
          <Select
            placeholder="状态筛选"
            value={statusInput || undefined}
            onChange={(v) => setStatusInput(v || "")}
            allowClear
            style={{ width: 130 }}
            options={STATUS_OPTIONS}
          />
          <RangePicker
            value={dateRange as [dayjs.Dayjs, dayjs.Dayjs] | null}
            onChange={(dates) =>
              setDateRange(dates ? [dates[0], dates[1]] : [null, null])
            }
            placeholder={["开始日期", "结束日期"]}
          />
          <Button type="primary" icon={<SearchOutlined />} onClick={handleSearch}>
            搜索
          </Button>
          <Button onClick={handleReset}>重置</Button>
        </Space>
      </Card>

      {/* 排序与刷新 */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 16,
        }}
      >
        <Space size="middle">
          <span style={{ color: "#666" }}>排序：</span>
          <Select
            value={params.sort_by}
            onChange={handleSortByChange}
            style={{ width: 140 }}
            options={SORT_OPTIONS}
          />
          <Button
            icon={
              params.sort_order === "asc" ? (
                <SortAscendingOutlined />
              ) : (
                <SortDescendingOutlined />
              )
            }
            onClick={toggleSortOrder}
          >
            {params.sort_order === "asc" ? "升序" : "降序"}
          </Button>
        </Space>
        <Button icon={<ReloadOutlined />} onClick={() => load(params)}>
          刷新
        </Button>
      </div>

      {tasks.length === 0 && !loading ? (
        <Empty description="还没有任务">
          <Button
            type="primary"
            icon={<RocketOutlined />}
            onClick={() => router.push("/workflows")}
          >
            去创建任务
          </Button>
        </Empty>
      ) : (
        <Table
          dataSource={tasks}
          rowKey="id"
          loading={loading}
          pagination={false}
          columns={[
            {
              title: "任务 ID",
              dataIndex: "id",
              render: (id: string) => (
                <Button type="link" onClick={() => router.push(`/tasks/detail?id=${id}`)}>
                  {id.substring(0, 8)}...
                </Button>
              ),
            },
            {
              title: "工作流",
              dataIndex: "workflow_id",
              render: (wfId: string) => workflows[wfId]?.name || wfId.substring(0, 8),
            },
            {
              title: "状态",
              dataIndex: "status",
              render: (status: string) => <Tag color={statusColors[status]}>{status}</Tag>,
            },
            {
              title: "当前步骤",
              dataIndex: "current_step_index",
              render: (v: number, record: TaskItem) =>
                `${v + 1} / ${record.step_executions?.length || 0}`,
            },
            {
              title: "Token 消耗",
              dataIndex: "total_tokens_used",
              render: (v: number) => v.toLocaleString(),
              sorter: true,
            },
            {
              title: "创建时间",
              dataIndex: "created_at",
              render: (v: string) => new Date(v).toLocaleString("zh-CN"),
            },
            {
              title: "操作",
              render: (_: unknown, record: TaskItem) => (
                <Button
                  size="small"
                  onClick={() => router.push(`/tasks/detail?id=${record.id}`)}
                >
                  详情
                </Button>
              ),
            },
          ]}
        />
      )}

      {/* 分页 */}
      <div style={{ marginTop: 16, display: "flex", justifyContent: "flex-end" }}>
        <Pagination
          current={params.page}
          total={total}
          pageSize={params.page_size}
          showSizeChanger
          showQuickJumper
          showTotal={(t) => `共 ${t} 条`}
          pageSizeOptions={["10", "20", "50"]}
          onChange={handlePageChange}
        />
      </div>
    </div>
  );
}

