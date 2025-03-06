// Updated index.js
import React from 'react';
import ReactDOM from 'react-dom';
import './styles/global.css';
import App from './App';
import ErrorBoundary from './components/common/ErrorBoundary';

ReactDOM.render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </React.StrictMode>,
  document.getElementById('root')
);