// src/components/cart/CartSummary.js
import React from 'react';
import Button from '../common/Button';
import { useCart } from '../../context/CartContext';
import styles from '../../styles/Cart.module.css';

const CartSummary = () => {
  const { cartCount, cartTotal } = useCart();
  
  const handleCheckout = () => {
    alert('Checkout functionality coming soon!');
  };

  return (
    <div className={styles.cartSummary}>
      <h2 className={styles.summaryTitle}>Order Summary</h2>
      <div className={styles.summaryItem}>
        <span>Total Items:</span>
        <span>{cartCount}</span>
      </div>
      <div className={styles.summaryItem}>
        <span>Total Price:</span>
        <span>${cartTotal.toFixed(2)}</span>
      </div>
      <Button 
        onClick={handleCheckout}
        variant="primary"
        size="large"
        fullWidth
      >
        Checkout
      </Button>
    </div>
  );
};

export default CartSummary;