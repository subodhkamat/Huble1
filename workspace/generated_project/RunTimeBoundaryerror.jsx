import React from "react";

export default class RuntimeErrorBoundary extends React.Component {
  constructor(props) {
    super(props);

    this.state = {
      hasError: false,
    };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error, info) {
    window.__buildAIReportError?.(
      error,
      info.componentStack
    );
  }

  render() {
    if (this.state.hasError) {
      return (
        <div role="alert" style={{ padding: "24px" }}>
          <h2>Something went wrong</h2>
          <p>A component failed to render. Check the BuildAI error report.</p>
        </div>
      );
    }

    return this.props.children;
  }
}