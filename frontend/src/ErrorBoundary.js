import React from 'react';

/**
 * Error Boundary - Catches React component errors and displays fallback UI
 * Prevents entire app from crashing on component errors
 */
class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    this.setState({
      error: error,
      errorInfo: errorInfo
    });

    // Log error only in development
    if (process.env.NODE_ENV === 'development' && process.env.REACT_APP_DEBUG === 'true') {
      console.error('Error caught by boundary:', error, errorInfo);
    }
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={styles.container}>
          <div style={styles.errorBox}>
            <h1 style={styles.title}>⚠️ Something Went Wrong</h1>
            <p style={styles.message}>
              An unexpected error occurred. Please try refreshing the page.
            </p>
            
            {process.env.NODE_ENV === 'development' && this.state.error && (
              <details style={styles.details}>
                <summary style={styles.summary}>Error Details (Development Only)</summary>
                <pre style={styles.stackTrace}>
                  {this.state.error.toString()}
                  {'\n\n'}
                  {this.state.errorInfo?.componentStack}
                </pre>
              </details>
            )}

            <button type="button" onClick={this.handleReset} style={styles.button}>
              Try Again
            </button>
            <button
              type="button"
              onClick={() => { window.location.href = '/'; }}
              style={{ ...styles.button, ...styles.secondaryButton }}
            >
              Go to Home
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

const styles = {
  container: {
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    minHeight: '100vh',
    backgroundColor: '#f5f5f5',
    padding: '20px',
  },
  errorBox: {
    backgroundColor: 'white',
    borderRadius: '8px',
    boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
    padding: '40px',
    maxWidth: '600px',
    textAlign: 'center',
  },
  title: {
    color: '#d32f2f',
    fontSize: '24px',
    marginBottom: '16px',
    marginTop: 0,
  },
  message: {
    color: '#666',
    fontSize: '16px',
    marginBottom: '24px',
    lineHeight: '1.5',
  },
  details: {
    textAlign: 'left',
    backgroundColor: '#f9f9f9',
    borderRadius: '4px',
    padding: '12px',
    marginBottom: '24px',
    border: '1px solid #ddd',
  },
  summary: {
    cursor: 'pointer',
    fontWeight: 'bold',
    color: '#1976d2',
    marginBottom: '8px',
  },
  stackTrace: {
    overflow: 'auto',
    backgroundColor: '#fff',
    padding: '12px',
    borderRadius: '4px',
    fontSize: '12px',
    fontFamily: 'monospace',
    color: '#d32f2f',
    maxHeight: '300px',
    margin: '8px 0 0 0',
  },
  button: {
    backgroundColor: '#1976d2',
    color: 'white',
    border: 'none',
    borderRadius: '4px',
    padding: '10px 24px',
    fontSize: '16px',
    cursor: 'pointer',
    marginRight: '12px',
    marginTop: '12px',
  },
  secondaryButton: {
    backgroundColor: '#666',
    marginRight: 0,
  },
};

export default ErrorBoundary;
