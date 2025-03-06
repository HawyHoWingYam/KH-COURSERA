// src/App.js
import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { CartProvider } from './context/CartContext';

// Import page components
import LandingPage from './components/landing/LandingPage';
import ProductListingPage from './components/products/ProductListingPage';
import ShoppingCartPage from './components/cart/ShoppingCartPage';

function App() {
  return (
    <Router>
      <CartProvider>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/products" element={<ProductListingPage />} />
          <Route path="/cart" element={<ShoppingCartPage />} />
        </Routes>
      </CartProvider>
    </Router>
  );
}

export default App;