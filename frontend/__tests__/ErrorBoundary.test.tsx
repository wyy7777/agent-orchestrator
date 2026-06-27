/**
 * Tests for ErrorBoundary component.
 */
import React from "react";
import { render, screen } from "@testing-library/react";
import { ErrorBoundary } from "@/components/ErrorBoundary";

// Mock antd components used by ErrorBoundary
jest.mock("antd", () => {
  const Result = ({
    status,
    title,
    subTitle,
    extra,
  }: {
    status?: string;
    title?: React.ReactNode;
    subTitle?: React.ReactNode;
    extra?: React.ReactNode;
  }) => (
    <div data-testid="antd-result" data-status={status}>
      <div data-testid="result-title">{title}</div>
      <div data-testid="result-subtitle">{subTitle}</div>
      {extra && <div data-testid="result-extra">{extra}</div>}
    </div>
  );

  const Button = ({
    children,
    onClick,
    ...props
  }: {
    children?: React.ReactNode;
    onClick?: () => void;
    [key: string]: unknown;
  }) => (
    <button data-testid="antd-button" onClick={onClick} {...props}>
      {children}
    </button>
  );

  return { Result, Button };
});

// A component that throws on render
function BuggyComponent({ shouldThrow = false }: { shouldThrow?: boolean }) {
  if (shouldThrow) {
    throw new Error("Test crash!");
  }
  return <div>Normal content</div>;
}

describe("ErrorBoundary", () => {
  // Suppress console.error for these tests (React logs caught errors in development)
  let consoleSpy: jest.SpyInstance;

  beforeEach(() => {
    consoleSpy = jest.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    consoleSpy.mockRestore();
  });

  it("renders children when there is no error", () => {
    render(
      <ErrorBoundary>
        <div data-testid="child">Hello World</div>
      </ErrorBoundary>
    );

    expect(screen.getByTestId("child")).toHaveTextContent("Hello World");
  });

  it("renders error UI when a child component throws", () => {
    render(
      <ErrorBoundary>
        <BuggyComponent shouldThrow />
      </ErrorBoundary>
    );

    // Should show error title
    expect(screen.getByTestId("result-title")).toHaveTextContent("页面出错了");
    expect(screen.getByTestId("result-subtitle")).toHaveTextContent("Test crash!");
  });

  it("shows the error message from the thrown error", () => {
    render(
      <ErrorBoundary>
        <BuggyComponent shouldThrow />
      </ErrorBoundary>
    );

    expect(screen.getByText("Test crash!")).toBeInTheDocument();
  });

  it("shows a refresh button when error occurs", () => {
    render(
      <ErrorBoundary>
        <BuggyComponent shouldThrow />
      </ErrorBoundary>
    );

    expect(screen.getByText("刷新页面")).toBeInTheDocument();
  });

  it("swallows the error (doesn't crash the test)", () => {
    // This test verifies that ErrorBoundary catches errors gracefully
    expect(() => {
      render(
        <ErrorBoundary>
          <BuggyComponent shouldThrow />
        </ErrorBoundary>
      );
    }).not.toThrow();
  });
});
